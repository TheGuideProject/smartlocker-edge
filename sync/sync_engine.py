"""
Sync Engine - Background cloud synchronization.

Runs in a separate thread and handles:
1. Periodic event sync (upload unsynced events to cloud)
2. Periodic config sync (download product/recipe updates)
3. Periodic heartbeat (keep device status "online" in cloud)

All operations are offline-tolerant: failures are logged and retried next cycle.
"""

import time
import json
import logging
import threading
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

    def __init__(self, db: Database, cloud: CloudClient):
        self.db = db
        self.cloud = cloud
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._last_sync_time = 0.0
        self._last_heartbeat_time = 0.0
        self._last_config_sync_time = 0.0
        self._start_time = time.time()

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
        logger.info("Sync engine started")

    def stop(self) -> None:
        """Stop the background sync thread."""
        self._running = False
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

    # ============================================================
    # SYNC LOOP
    # ============================================================

    def _sync_loop(self) -> None:
        """Main sync loop (runs in background thread)."""
        logger.info("Sync loop started")

        # Initial sync on startup
        time.sleep(5)  # Wait for system to stabilize
        self._do_event_sync()
        self._do_heartbeat()
        self._do_config_sync()

        while self._running:
            try:
                now = time.time()

                # Event sync
                if now - self._last_sync_time >= settings.SYNC_INTERVAL_S:
                    self._do_event_sync()
                    self._last_sync_time = now

                # Heartbeat
                if now - self._last_heartbeat_time >= settings.HEARTBEAT_INTERVAL_S:
                    self._do_heartbeat()
                    self._last_heartbeat_time = now

                # Config sync (every 30 minutes)
                if now - self._last_config_sync_time >= 1800:
                    self._do_config_sync()
                    self._last_config_sync_time = now

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

            logger.info(f"Syncing {len(events)} events to cloud...")
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

            # Update products
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

            logger.info(f"Config synced: {len(products)} products, {len(recipes)} recipes")

        except Exception as e:
            logger.error(f"Config sync error: {e}")

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
        }
