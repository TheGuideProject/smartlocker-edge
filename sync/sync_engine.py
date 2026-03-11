"""
Sync Engine - Background cloud synchronization.

Runs in a separate thread and handles:
1. Periodic event sync (upload unsynced events to cloud)
2. Periodic config sync (download product/recipe updates)
3. Periodic heartbeat (keep device status "online" in cloud)

All operations are offline-tolerant: failures are logged and retried next cycle.
"""

import os
import time
import json
import logging
import threading
import subprocess
from typing import Optional

from config import settings
from persistence.database import Database
from sync.cloud_client import CloudClient

logger = logging.getLogger("smartlocker.sync")


class SyncEngine:
    """
    Background sync engine.

    Usage:
        engine = SyncEngine(database, cloud_client)
        engine.start()  # Starts background thread
        ...
        engine.stop()   # Stops background thread
    """

    # Health snapshot interval: every 5 minutes (300 seconds)
    HEALTH_LOG_INTERVAL_S = 300

    # Config sync interval: every 2 minutes (check for OTA, products, recipes)
    CONFIG_SYNC_INTERVAL_S = 120

    # Inventory snapshot sync interval: every 5 minutes
    INVENTORY_SYNC_INTERVAL_S = 300

    # Mixing session sync interval: every 60 seconds
    MIXING_SESSION_SYNC_INTERVAL_S = 60

    def __init__(self, db: Database, cloud: CloudClient):
        self.db = db
        self.cloud = cloud
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._last_sync_time = 0.0
        self._last_heartbeat_time = 0.0
        self._last_config_sync_time = 0.0
        self._last_health_log_time = 0.0
        self._last_inventory_sync_time = 0.0
        self._last_mixing_session_sync_time = 0.0
        self._start_time = time.time()

        try:
            from sync.update_manager import UpdateManager
            self._update_manager = UpdateManager(cloud, db)
        except Exception as e:
            logger.warning(f"UpdateManager not available: {e}")
            self._update_manager = None

        # WebSocket real-time client
        self._realtime = None
        if cloud.is_paired and getattr(settings, 'WS_ENABLED', False):
            try:
                from sync.realtime_client import RealtimeClient
                self._realtime = RealtimeClient(
                    cloud_url=cloud.cloud_url,
                    api_key=cloud.api_key,
                    device_id=cloud.device_id,
                )
                self._realtime.on_command = self._handle_ws_command
                self._realtime.on_ack = self._handle_ws_ack
                self._realtime.on_connect = self._on_ws_connect
                self._realtime.on_disconnect = self._on_ws_disconnect
                logger.info("WebSocket real-time client initialized")
            except Exception as e:
                logger.warning(f"WebSocket client not available: {e}")
                self._realtime = None

    def start(self) -> None:
        """Start the background sync thread."""
        if not self.cloud.is_paired:
            logger.info("Sync engine not started: device not paired")
            return

        if self._running:
            logger.warning("Sync engine already running")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._sync_loop,
            name="SyncEngine",
            daemon=True,
        )
        self._thread.start()
        if self._realtime:
            self._realtime.start()
        logger.info("Sync engine started")

    def stop(self) -> None:
        """Stop the background sync thread."""
        self._running = False
        if self._realtime:
            self._realtime.stop()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("Sync engine stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    def force_sync(self) -> None:
        """Force an immediate sync cycle (called from UI or events)."""
        self._last_sync_time = 0  # Reset timer to trigger immediate sync
        self._last_heartbeat_time = 0  # Also trigger heartbeat (updates cloud status)

    # ============================================================
    # SYNC LOOP
    # ============================================================

    def _wait_for_network(self, timeout_s: int = 90, check_interval_s: int = 3) -> bool:
        """
        Wait for network connectivity before starting sync.
        Tries to reach the cloud URL. Returns True if connected, False if timed out.
        Essential after RPi reboot — network.target doesn't guarantee internet is ready.
        """
        import urllib.request
        import urllib.error

        # Build a simple check URL from cloud URL
        check_url = self.cloud.cloud_url.rstrip("/") + "/health"
        deadline = time.time() + timeout_s
        attempt = 0

        logger.info(f"Waiting for network connectivity (timeout={timeout_s}s)...")

        while self._running and time.time() < deadline:
            attempt += 1
            try:
                req = urllib.request.Request(check_url, method="GET")
                req.add_header("User-Agent", "SmartLocker-Edge")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status < 500:
                        logger.info(f"Network ready after {attempt} attempt(s)")
                        return True
            except urllib.error.URLError as e:
                logger.debug(f"Network check #{attempt} failed: {e.reason}")
            except Exception as e:
                logger.debug(f"Network check #{attempt} failed: {e}")

            # Sleep in small chunks so we can stop quickly
            sleep_end = time.time() + check_interval_s
            while self._running and time.time() < sleep_end:
                time.sleep(0.5)

        logger.warning(f"Network not available after {timeout_s}s — starting sync anyway (will retry)")
        return False

    def _sync_loop(self) -> None:
        """Main sync loop (runs in background thread)."""
        logger.info("Sync loop started")

        # Wait for network connectivity (critical after RPi reboot)
        self._wait_for_network(timeout_s=90, check_interval_s=3)

        # Startup heartbeat with retry (network may still be flaky)
        startup_ok = False
        for attempt in range(3):
            if not self._running:
                return
            try:
                self._do_heartbeat()
                logger.info("Startup heartbeat sent")
                startup_ok = True
                break
            except Exception as e:
                logger.warning(f"Startup heartbeat attempt {attempt+1}/3 failed: {e}")
                time.sleep(5)

        # Initial sync on startup
        time.sleep(3)  # Brief stabilization wait
        try:
            self._do_event_sync()
        except Exception as e:
            logger.warning(f"Initial event sync failed: {e}")
        try:
            self._do_heartbeat()
        except Exception as e:
            logger.warning(f"Initial heartbeat failed: {e}")
        try:
            self._do_config_sync()
        except Exception as e:
            logger.warning(f"Initial config sync failed: {e}")
        self._log_health_snapshot()  # Initial health snapshot (always local)

        while self._running:
            try:
                now = time.time()

                # Event sync
                event_interval = getattr(settings, 'WS_FALLBACK_EVENT_INTERVAL_S', 120) if (self._realtime and self._realtime.is_connected) else settings.SYNC_INTERVAL_S
                if now - self._last_sync_time >= event_interval:
                    self._do_event_sync()
                    self._do_health_sync()  # Upload buffered health logs
                    self._last_sync_time = now

                # Heartbeat
                if now - self._last_heartbeat_time >= settings.HEARTBEAT_INTERVAL_S:
                    self._do_heartbeat()
                    self._last_heartbeat_time = now

                # Config sync (every 2 minutes — fast OTA + product updates)
                config_interval = getattr(settings, 'WS_FALLBACK_CONFIG_INTERVAL_S', 600) if (self._realtime and self._realtime.is_connected) else self.CONFIG_SYNC_INTERVAL_S
                if now - self._last_config_sync_time >= config_interval:
                    self._do_config_sync()
                    self._last_config_sync_time = now

                # Inventory snapshot sync (every 5 minutes)
                if now - self._last_inventory_sync_time >= self.INVENTORY_SYNC_INTERVAL_S:
                    self._do_inventory_sync()
                    self._last_inventory_sync_time = now

                # Mixing session sync (every 60 seconds)
                if now - self._last_mixing_session_sync_time >= self.MIXING_SESSION_SYNC_INTERVAL_S:
                    self._do_mixing_session_sync()
                    self._last_mixing_session_sync_time = now

                # Health snapshot every 5 minutes (REGARDLESS of network)
                if now - self._last_health_log_time >= self.HEALTH_LOG_INTERVAL_S:
                    self._log_health_snapshot()
                    self._last_health_log_time = now

                # Sleep between checks (short so we can stop quickly)
                time.sleep(5)

            except Exception as e:
                logger.error(f"Sync loop error: {e}")
                time.sleep(30)  # Back off on error

        logger.info("Sync loop stopped")

    # ============================================================
    # SYNC OPERATIONS
    # ============================================================

    def _do_event_sync(self) -> None:
        """Upload unsynced events to cloud."""
        try:
            events = self.db.get_unsynced_events(limit=settings.SYNC_BATCH_SIZE)
            if not events:
                logger.debug("No events to sync")
                return

            # Try WebSocket first
            if self._realtime and self._realtime.is_connected:
                cloud_events = self._convert_events_for_cloud(events)
                if self._realtime.send_events(cloud_events):
                    logger.info(f"Sent {len(events)} events via WebSocket")
                    return  # Ack will come async via on_ack callback

            # Fallback to HTTP
            logger.info(f"Syncing {len(events)} events to cloud via HTTP...")
            success, acked_ids = self.cloud.sync_events(events)

            if success and acked_ids:
                self.db.mark_events_synced(acked_ids)
                logger.info(f"Synced and acked {len(acked_ids)} events")
            elif not success:
                logger.warning("Event sync failed, will retry next cycle")

        except Exception as e:
            logger.error(f"Event sync error: {e}")

    def _do_heartbeat(self) -> None:
        """Send heartbeat to cloud."""
        try:
            # Always read fresh VERSION from file (important after OTA update)
            from sync.update_manager import read_version
            current_version = read_version()
            logger.debug(f"Heartbeat version: {current_version}")

            uptime_hours = (time.time() - self._start_time) / 3600
            unsynced = self.db.get_event_count(synced=False)

            self.cloud.send_heartbeat(
                uptime_hours=round(uptime_hours, 2),
                sync_queue_depth=unsynced,
            )
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")

    def _do_config_sync(self) -> None:
        """Download latest config from cloud and update local catalog."""
        try:
            success, config = self.cloud.fetch_config()
            if not success:
                logger.warning("Config sync failed, will retry later")
                return

            # Update products (including colors)
            products = config.get("products", [])
            for p in products:
                self.db.upsert_product({
                    "product_id": p["id"],
                    "ppg_code": p.get("ppg_code", ""),
                    "name": p["name"],
                    "product_type": p["product_type"],
                    "density_g_per_ml": p.get("density_g_per_ml", 1.0),
                    "pot_life_minutes": p.get("pot_life_minutes"),
                    "hazard_class": p.get("hazard_class", ""),
                    "can_sizes_ml": p.get("can_sizes_ml", []),
                    "can_tare_weight_g": p.get("can_tare_weight_g", {}),
                    "colors_json": p.get("colors_json", []),
                })

            # Update recipes
            recipes = config.get("recipes", [])
            for r in recipes:
                self.db.upsert_recipe({
                    "recipe_id": r["id"],
                    "name": r["name"],
                    "base_product_id": r["base_product_id"],
                    "hardener_product_id": r["hardener_product_id"],
                    "ratio_base": r["ratio_base"],
                    "ratio_hardener": r["ratio_hardener"],
                    "tolerance_pct": r.get("tolerance_pct", 5.0),
                    "thinner_pct_brush": r.get("thinner_pct_brush", 5.0),
                    "thinner_pct_roller": r.get("thinner_pct_roller", 5.0),
                    "thinner_pct_spray": r.get("thinner_pct_spray", 10.0),
                    "recommended_thinner_id": r.get("recommended_thinner_id"),
                    "pot_life_minutes": r.get("pot_life_minutes", 480),
                })

            # Save maintenance chart if included
            chart = config.get("maintenance_chart")
            if chart:
                self.db.save_maintenance_chart(chart)
                logger.info(f"Maintenance chart synced: {chart.get('vessel_name', '?')}")

            # Save vessel inventory from cloud
            vessel_inv = config.get("vessel_inventory")
            if vessel_inv is not None:
                self.db.clear_vessel_stock()
                for item in vessel_inv:
                    self.db.upsert_vessel_stock(item)
                logger.info(f"Vessel inventory synced: {len(vessel_inv)} products")

            # Update admin password if sent from cloud
            new_password = config.get("admin_password")
            if new_password:
                import hashlib
                hash_str = hashlib.sha256(new_password.encode()).hexdigest()
                self.db.set_admin_password_hash(hash_str)
                logger.info("Admin password updated from cloud")

            # Update slot count if changed
            slot_count = config.get("slot_count")
            if slot_count and isinstance(slot_count, int) and slot_count >= 1:
                self.db.save_config("slot_count", str(slot_count))
                logger.info(f"Slot count updated from cloud: {slot_count}")

            logger.info(f"Config synced: {len(products)} products, {len(recipes)} recipes")

            # Check for OTA update command
            update_cmd = config.get("update")
            if update_cmd and self._update_manager:
                update_info = self._update_manager.check_update(config)
                if update_info:
                    logger.info(f"OTA update starting: -> v{update_info.get('version', '?')}")
                    # Force a heartbeat with current version BEFORE restart
                    try:
                        self._do_heartbeat()
                    except Exception:
                        pass
                    success, error = self._update_manager.apply_update(update_info)
                    if not success:
                        logger.error(f"OTA update failed: {error}")
                    # If success, app restarts and we never get here

        except Exception as e:
            logger.error(f"Config sync error: {e}")

    # ============================================================
    # INVENTORY SNAPSHOT SYNC
    # ============================================================

    def _do_inventory_sync(self) -> None:
        """Send current slot state to cloud for reconciliation."""
        try:
            slots_data = self.db.get_inventory_snapshot()
            if not slots_data:
                logger.debug("No slot state data to sync")
                return

            # Convert sqlite3.Row-compatible dicts to plain serializable dicts
            clean_slots = []
            for slot in slots_data:
                clean_slots.append({
                    "slot_id": slot.get("slot_id", ""),
                    "status": slot.get("status", "empty"),
                    "current_tag_id": slot.get("current_tag_id"),
                    "current_product_id": slot.get("current_product_id"),
                    "weight_when_placed_g": slot.get("weight_when_placed_g", 0.0),
                    "weight_current_g": slot.get("weight_current_g", 0.0),
                    "last_change_at": slot.get("last_change_at"),
                    "product_name": slot.get("product_name"),
                    "product_type": slot.get("product_type"),
                    "batch_number": slot.get("batch_number"),
                    "can_size_ml": slot.get("can_size_ml"),
                })

            success = self.cloud.send_inventory_snapshot(clean_slots)
            if success:
                logger.info(f"Inventory snapshot synced: {len(clean_slots)} slots")
            else:
                logger.warning("Inventory snapshot sync failed, will retry next cycle")
        except Exception as e:
            logger.error(f"Inventory sync error: {e}")

    # ============================================================
    # MIXING SESSION SYNC
    # ============================================================

    def _do_mixing_session_sync(self) -> None:
        """Upload unsynced mixing sessions to cloud."""
        try:
            sessions = self.db.get_unsynced_mixing_sessions(limit=20)
            if not sessions:
                logger.debug("No mixing sessions to sync")
                return

            # Try WebSocket first
            if self._realtime and self._realtime.is_connected:
                cloud_sessions = self._convert_sessions_for_cloud(sessions)
                if self._realtime.send_mixing_sessions(cloud_sessions):
                    logger.info(f"Sent {len(sessions)} mixing sessions via WebSocket")
                    return  # Ack will come async via on_ack callback

            # Fallback to HTTP
            logger.info(f"Syncing {len(sessions)} mixing sessions to cloud via HTTP...")
            success, acked_ids = self.cloud.sync_mixing_sessions(sessions)

            if success and acked_ids:
                self.db.mark_mixing_sessions_synced(acked_ids)
                logger.info(f"Synced and acked {len(acked_ids)} mixing sessions")
            elif not success:
                logger.warning("Mixing session sync failed, will retry next cycle")
        except Exception as e:
            logger.error(f"Mixing session sync error: {e}")

    # ============================================================
    # HEALTH LOGGING (offline-tolerant)
    # ============================================================

    def _log_health_snapshot(self) -> None:
        """
        Take a health snapshot of all sensors and store locally.
        Called every 5 minutes REGARDLESS of network status.
        """
        try:
            health = self.cloud._collect_health_data() if hasattr(self.cloud, '_collect_health_data') else {}

            if not health:
                logger.debug("No health data to log (no sensors configured)")
                return

            for sensor_name, sensor_data in health.items():
                if not isinstance(sensor_data, dict):
                    continue
                status = sensor_data.get('status', 'unknown')
                message = sensor_data.get('message', '')
                value = json.dumps(sensor_data.get('details', '')) if sensor_data.get('details') else ''
                self.db.log_sensor_health(sensor_name, status, message, value)

            logger.debug(f"Health snapshot logged: {len(health)} sensors")
        except Exception as e:
            logger.error(f"Health snapshot error: {e}")

    def _do_health_sync(self) -> None:
        """Upload buffered health logs to cloud when online."""
        try:
            pending = self.db.get_pending_health_logs(limit=500)
            if not pending:
                return

            success = self.cloud.upload_health_logs(pending)
            if success:
                ids = [log['id'] for log in pending]
                self.db.mark_health_logs_synced(ids)
                self.db.cleanup_old_health_logs(days=30)
                logger.info(f"Health logs synced: {len(pending)} entries")
        except Exception as e:
            logger.warning(f"Health sync failed: {e}")

    # ============================================================
    # CLOUD FORMAT CONVERTERS
    # ============================================================

    def _convert_events_for_cloud(self, events: list) -> list:
        """Convert local event dicts to cloud format (same as CloudClient.sync_events)."""
        cloud_events = []
        for event in events:
            cloud_events.append({
                "event_id": event["event_id"],
                "event_type": event["event_type"],
                "timestamp": event["timestamp"],
                "device_id": event.get("device_id", self.cloud.device_id),
                "shelf_id": event.get("shelf_id", ""),
                "slot_id": event.get("slot_id", ""),
                "tag_id": event.get("tag_id", ""),
                "session_id": event.get("session_id", ""),
                "user_name": event.get("user_name", ""),
                "data": json.loads(event.get("data_json", "{}")) if isinstance(event.get("data_json"), str) else event.get("data_json", {}),
                "confirmation": event.get("confirmation", "unconfirmed"),
                "sequence_num": event.get("sequence_num", 0),
            })
        return cloud_events

    def _convert_sessions_for_cloud(self, sessions: list) -> list:
        """Convert local mixing session dicts to cloud format (same as CloudClient.sync_mixing_sessions)."""
        cloud_sessions = []
        for s in sessions:
            cloud_sessions.append({
                "session_id": s["session_id"],
                "recipe_id": s.get("recipe_id", ""),
                "job_id": s.get("job_id", ""),
                "user_name": s.get("user_name", ""),
                "started_at": s.get("started_at", 0),
                "completed_at": s.get("completed_at", 0),
                "base_product_id": s.get("base_product_id", ""),
                "base_tag_id": s.get("base_tag_id", ""),
                "base_weight_target_g": s.get("base_weight_target_g", 0),
                "base_weight_actual_g": s.get("base_weight_actual_g", 0),
                "hardener_product_id": s.get("hardener_product_id", ""),
                "hardener_tag_id": s.get("hardener_tag_id", ""),
                "hardener_weight_target_g": s.get("hardener_weight_target_g", 0),
                "hardener_weight_actual_g": s.get("hardener_weight_actual_g", 0),
                "thinner_product_id": s.get("thinner_product_id", ""),
                "thinner_weight_g": s.get("thinner_weight_g", 0),
                "ratio_achieved": s.get("ratio_achieved", 0),
                "ratio_in_spec": bool(s.get("ratio_in_spec", 0)),
                "override_reason": s.get("override_reason", ""),
                "application_method": s.get("application_method", "brush"),
                "pot_life_started_at": s.get("pot_life_started_at", 0),
                "pot_life_expires_at": s.get("pot_life_expires_at", 0),
                "status": s.get("status", "completed"),
                "confirmation": s.get("confirmation", "confirmed"),
            })
        return cloud_sessions

    # ============================================================
    # WEBSOCKET CALLBACKS
    # ============================================================

    def _handle_ws_command(self, msg: dict):
        """Handle incoming command from cloud via WebSocket."""
        cmd_type = msg.get("command_type", "")
        payload = msg.get("payload", {})

        try:
            if cmd_type == "product_sync":
                products = payload.get("products", [])
                for p in products:
                    self.db.upsert_product({
                        "product_id": p.get("id", ""),
                        "ppg_code": p.get("ppg_code", ""),
                        "name": p.get("name", ""),
                        "product_type": p.get("product_type", ""),
                        "density_g_per_ml": p.get("density_g_per_ml", 1.0),
                        "pot_life_minutes": p.get("pot_life_minutes"),
                        "hazard_class": p.get("hazard_class", ""),
                        "can_sizes_ml": p.get("can_sizes_ml", []),
                        "can_tare_weight_g": p.get("can_tare_weight_g", {}),
                    })
                logger.info(f"[WS] Product sync: {len(products)} products updated")

            elif cmd_type == "recipe_sync":
                recipes = payload.get("recipes", [])
                for r in recipes:
                    self.db.upsert_recipe({
                        "recipe_id": r.get("id", ""),
                        "name": r.get("name", ""),
                        "base_product_id": r.get("base_product_id", ""),
                        "hardener_product_id": r.get("hardener_product_id", ""),
                        "ratio_base": r.get("ratio_base", 1),
                        "ratio_hardener": r.get("ratio_hardener", 1),
                        "tolerance_pct": r.get("tolerance_pct", 5.0),
                        "thinner_pct_brush": r.get("thinner_pct_brush", 5.0),
                        "thinner_pct_roller": r.get("thinner_pct_roller", 5.0),
                        "thinner_pct_spray": r.get("thinner_pct_spray", 10.0),
                        "recommended_thinner_id": r.get("recommended_thinner_id"),
                        "pot_life_minutes": r.get("pot_life_minutes", 480),
                    })
                logger.info(f"[WS] Recipe sync: {len(recipes)} recipes updated")

            elif cmd_type == "config_update":
                # Full config payload — reuse existing config sync logic
                self._do_config_sync()

            elif cmd_type == "ota_update":
                if self._update_manager:
                    update_info = {"update": payload}
                    self._update_manager.check_and_apply(update_info)

            elif cmd_type == "force_sync":
                self.force_sync()

            elif cmd_type == "restart_app":
                logger.info("[WS] Received restart_app command from cloud")
                self._restart_application()

            elif cmd_type == "reboot_device":
                logger.info("[WS] Received reboot_device command from cloud")
                self._reboot_device()

            else:
                logger.warning(f"[WS] Unknown command type: {cmd_type}")

        except Exception as e:
            logger.error(f"[WS] Error handling command {cmd_type}: {e}")

    def _handle_ws_ack(self, msg: dict):
        """Handle ack from cloud for events/sessions we sent via WebSocket."""
        try:
            if "event_ids" in msg:
                self.db.mark_events_synced(msg["event_ids"])
                logger.debug(f"[WS] Acked {len(msg['event_ids'])} events")
            if "session_ids" in msg:
                self.db.mark_mixing_sessions_synced(msg["session_ids"])
                logger.debug(f"[WS] Acked {len(msg['session_ids'])} mixing sessions")
        except Exception as e:
            logger.error(f"[WS] Error handling ack: {e}")

    def _on_ws_connect(self):
        """Called when WebSocket connects."""
        logger.info("[WS] Connected to cloud -- switching to real-time mode")

    def _on_ws_disconnect(self):
        """Called when WebSocket disconnects."""
        logger.info("[WS] Disconnected from cloud -- falling back to HTTP polling")
        # Reset timers to trigger immediate HTTP sync
        self._last_sync_time = 0
        self._last_heartbeat_time = 0
        self._last_config_sync_time = 0

    # ============================================================
    # REMOTE CONTROL — restart / reboot
    # ============================================================

    def _restart_application(self):
        """
        Restart the SmartLocker application.
        Uses sys.exit() — systemd Restart=always will restart the service automatically.
        """
        import sys
        logger.info("Restarting SmartLocker application (systemd will auto-restart)...")

        # Give time for the WS ack to be sent
        time.sleep(1)

        # Try graceful Kivy shutdown first
        try:
            from kivy.app import App
            app = App.get_running_app()
            if app:
                from kivy.clock import Clock
                Clock.schedule_once(lambda dt: app.stop(), 0.5)
                time.sleep(2)
        except Exception:
            pass

        # Force exit — systemd Restart=always will bring us back
        os._exit(0)

    def _reboot_device(self):
        """
        Reboot the entire Raspberry Pi device.
        Requires sudo privileges (configured in sudoers or running as root).
        """
        logger.info("Rebooting device in 3 seconds...")

        # Give time for WS ack + log flush
        time.sleep(3)

        try:
            subprocess.run(["sudo", "reboot"], check=True)
        except Exception as e:
            logger.error(f"Reboot failed: {e}")
            # Fallback: try systemctl
            try:
                subprocess.run(["sudo", "systemctl", "reboot"], check=True)
            except Exception as e2:
                logger.error(f"Reboot fallback also failed: {e2}")

    # ============================================================
    # STATUS
    # ============================================================

    def get_status(self) -> dict:
        """Get sync engine status for UI display."""
        unsynced = 0
        total = 0
        try:
            unsynced = self.db.get_event_count(synced=False)
            total = self.db.get_event_count()
        except Exception:
            pass

        pairing = self.cloud.get_pairing_info()

        return {
            "is_paired": self.cloud.is_paired,
            "is_syncing": self._running,
            "cloud_url": self.cloud.cloud_url,
            "vessel_name": pairing.get("vessel_name", "") if pairing else "",
            "company_name": pairing.get("company_name", "") if pairing else "",
            "events_total": total,
            "events_unsynced": unsynced,
            "events_synced": total - unsynced,
            "last_sync": self._last_sync_time,
            "uptime_hours": round((time.time() - self._start_time) / 3600, 2),
            "ws_connected": self._realtime.is_connected if self._realtime else False,
        }
