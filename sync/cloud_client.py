"""
Cloud Client - HTTP communication with SmartLocker Cloud Backend.

Handles:
- Device pairing (6-digit code → API key)
- Event sync (batch upload of local events)
- Config sync (download product catalog, recipes)
- Heartbeat (periodic status ping)

All operations are retry-safe and offline-tolerant.
"""

import json
import time
import logging
import os
from typing import Optional, Dict, Any, List, Tuple
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from config import settings

logger = logging.getLogger("smartlocker.cloud")


class CloudClient:
    """
    HTTP client for SmartLocker Cloud Backend.

    Uses only stdlib (urllib) to avoid extra dependencies on RPi.
    All methods return (success: bool, data: dict) tuples.
    """

    def __init__(self):
        self.cloud_url: str = ""
        self.api_key: str = ""
        self.device_uuid: str = ""
        self.device_id: str = settings.DEVICE_ID
        self.is_paired: bool = False

        # Device monitoring references (set by app after init)
        self._driver_status: Optional[Dict[str, str]] = None  # {"rfid": "real", ...}
        self._sensors = {}  # {"rfid": driver_ref, "weight": driver_ref, ...}
        self._start_time: float = time.time()
        self._db_ref = None  # Reference to Database for size/pending info

        # Try to load saved pairing
        self._load_pairing()

    # ============================================================
    # PAIRING
    # ============================================================

    def pair_with_code(self, cloud_url: str, pairing_code: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Pair this device with the cloud using a 6-digit code.

        Args:
            cloud_url: Cloud backend URL (e.g., "https://xxx.up.railway.app")
            pairing_code: 6-character alphanumeric code from admin

        Returns:
            (success, response_data) tuple
        """
        url = f"{cloud_url.rstrip('/')}/api/devices/pair"

        payload = {
            "pairing_code": pairing_code.strip().upper(),
            "device_id": self.device_id,
            "device_name": f"SmartLocker {self.device_id}",
            "software_version": "1.0.0",
        }

        success, data = self._http_post(url, payload)

        if success and data.get("success"):
            # Save pairing info
            self.cloud_url = cloud_url.rstrip("/")
            self.api_key = data["api_key"]
            self.device_uuid = data["device_uuid"]
            self.is_paired = True

            # Persist pairing to disk
            self._save_pairing(data)

            logger.info(
                f"Paired successfully! Vessel: {data.get('vessel_name')}, "
                f"Company: {data.get('company_name')}"
            )
            return True, data
        else:
            error_msg = data.get("detail", "Unknown error") if data else "Connection failed"
            logger.error(f"Pairing failed: {error_msg}")
            return False, data or {"detail": error_msg}

    # ============================================================
    # EVENT SYNC
    # ============================================================

    def sync_events(self, events: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """
        Upload a batch of events to the cloud.

        Args:
            events: List of event dicts from database

        Returns:
            (success, acked_event_ids) tuple
        """
        if not self.is_paired:
            logger.warning("Cannot sync events: device not paired")
            return False, []

        url = f"{self.cloud_url}/api/devices/{self.device_id}/events"

        # Convert local event format to cloud format
        cloud_events = []
        for event in events:
            cloud_events.append({
                "event_id": event["event_id"],
                "event_type": event["event_type"],
                "timestamp": event["timestamp"],
                "device_id": event.get("device_id", self.device_id),
                "shelf_id": event.get("shelf_id", ""),
                "slot_id": event.get("slot_id", ""),
                "tag_id": event.get("tag_id", ""),
                "session_id": event.get("session_id", ""),
                "user_name": event.get("user_name", ""),
                "data": json.loads(event.get("data_json", "{}")) if isinstance(event.get("data_json"), str) else event.get("data_json", {}),
                "confirmation": event.get("confirmation", "unconfirmed"),
                "sequence_num": event.get("sequence_num", 0),
            })

        payload = {"events": cloud_events}
        success, data = self._http_post(url, payload, auth=True)

        if success:
            acked_ids = data.get("event_ids", [])
            received = data.get("received", 0)
            duplicates = data.get("duplicates", 0)
            logger.info(f"Synced {received} events ({duplicates} duplicates)")
            return True, acked_ids
        else:
            logger.error(f"Event sync failed: {data}")
            return False, []

    # ============================================================
    # MONITORING SETUP
    # ============================================================

    def set_monitoring_refs(
        self,
        driver_status: Dict[str, str],
        sensors: Dict,
        db_ref=None,
    ) -> None:
        """
        Set references for device monitoring (called after init by the app).

        Args:
            driver_status: {"rfid": "real"|"fake", "weight": ..., "led": ..., "buzzer": ...}
            sensors: {"rfid": rfid_driver, "weight": weight_driver, ...}
            db_ref: Reference to Database instance for size/pending info
        """
        self._driver_status = driver_status
        self._sensors = sensors
        self._db_ref = db_ref
        self._start_time = time.time()
        logger.info(f"Monitoring refs set: drivers={driver_status}")

    def _collect_health_data(self) -> Dict[str, Any]:
        """Collect health status from all sensor drivers."""
        health = {}

        # RFID health
        rfid = self._sensors.get("rfid")
        if rfid:
            try:
                is_healthy = rfid.is_healthy()
                health["rfid"] = {
                    "status": "ok" if is_healthy else "error",
                    "message": "All readers responding" if is_healthy else "RFID reader not responding",
                    "readers": len(rfid.get_reader_ids()) if hasattr(rfid, 'get_reader_ids') else 0,
                }
            except Exception as e:
                health["rfid"] = {"status": "error", "message": str(e)}

        # Weight sensor health
        weight = self._sensors.get("weight")
        if weight:
            try:
                is_healthy = weight.is_healthy()
                channels = weight.get_channels() if hasattr(weight, 'get_channels') else []
                health["weight"] = {
                    "status": "ok" if is_healthy else "error",
                    "message": "All scales responding" if is_healthy else "Weight sensor error",
                    "channels": len(channels),
                }

                # Check for out-of-range readings on each channel
                for ch in channels:
                    try:
                        reading = weight.read_weight(ch)
                        if reading.grams < -100:
                            health[f"weight_{ch}"] = {
                                "status": "out_of_range",
                                "message": f"Negative reading on {ch}: {reading.grams}g",
                                "last_value": round(reading.grams, 1),
                            }
                        elif reading.grams > 50000:
                            health[f"weight_{ch}"] = {
                                "status": "out_of_range",
                                "message": f"Excessive reading on {ch}: {reading.grams}g",
                                "last_value": round(reading.grams, 1),
                            }
                    except Exception:
                        pass  # Individual channel read failure is not critical

            except Exception as e:
                health["weight"] = {"status": "error", "message": str(e)}

        return health

    def _collect_system_info(self, sync_queue_depth: int = 0) -> Dict[str, Any]:
        """Collect system information for heartbeat."""
        info = {
            "uptime_seconds": round(time.time() - self._start_time, 1),
            "events_pending_sync": sync_queue_depth,
        }

        # Try to get DB file size
        if self._db_ref:
            try:
                db_path = getattr(self._db_ref, 'db_path', None)
                if db_path and os.path.exists(db_path):
                    size_bytes = os.path.getsize(db_path)
                    info["db_size_mb"] = round(size_bytes / (1024 * 1024), 2)
            except Exception:
                pass

        return info

    # ============================================================
    # HEARTBEAT
    # ============================================================

    def send_heartbeat(self, uptime_hours: float = 0, sync_queue_depth: int = 0) -> bool:
        """Send a heartbeat with sensor health data to the cloud."""
        if not self.is_paired:
            return False

        url = f"{self.cloud_url}/api/devices/{self.device_id}/heartbeat"

        # Collect extended monitoring data
        health_data = self._collect_health_data()
        system_info = self._collect_system_info(sync_queue_depth)

        payload = {
            "software_version": "1.0.0",
            "uptime_hours": uptime_hours,
            "sync_queue_depth": sync_queue_depth,
            "driver_status": self._driver_status,
            "sensor_health": health_data,
            "system_info": system_info,
        }

        success, _ = self._http_post(url, payload, auth=True)
        if success:
            logger.debug("Heartbeat sent OK (with health data)")
        return success

    # ============================================================
    # HEALTH LOG SYNC (batch upload of offline health logs)
    # ============================================================

    def upload_health_logs(self, logs: list) -> bool:
        """
        Upload a batch of health logs to the cloud.
        Called by SyncEngine when network is available.

        Args:
            logs: List of dicts with keys: id, timestamp, sensor, status, message, value

        Returns:
            True if upload was successful
        """
        if not self.is_paired:
            return False

        url = f"{self.cloud_url}/api/devices/{self.device_id}/health-logs"
        payload = {"logs": logs}

        success, data = self._http_post(url, payload, auth=True, timeout=15)
        if success:
            received = data.get("received", 0)
            logger.info(f"Health logs uploaded: {received} entries")
        return success

    # ============================================================
    # INVENTORY SNAPSHOT SYNC
    # ============================================================

    def send_inventory_snapshot(self, slots_data: list) -> bool:
        """
        Send current slot state to cloud for reconciliation.

        Args:
            slots_data: List of dicts with slot state info
                        (from Database.get_inventory_snapshot())

        Returns:
            True if upload was successful
        """
        if not self.is_paired:
            return False

        url = f"{self.cloud_url}/api/devices/{self.device_id}/inventory-snapshot"
        payload = {
            "device_id": self.device_id,
            "timestamp": time.time(),
            "slots": slots_data,
        }

        success, data = self._http_post(url, payload, auth=True, timeout=15)
        if success:
            logger.info(f"Inventory snapshot sent: {len(slots_data)} slots")
        else:
            logger.warning(f"Inventory snapshot failed: {data}")
        return success

    # ============================================================
    # CONFIG SYNC
    # ============================================================

    def fetch_config(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Download latest config (products, recipes) from cloud.

        Returns:
            (success, config_data) tuple
        """
        if not self.is_paired:
            return False, {}

        url = f"{self.cloud_url}/api/devices/{self.device_id}/config"
        success, data = self._http_get(url, auth=True)

        if success:
            logger.info(
                f"Config fetched: {len(data.get('products', []))} products, "
                f"{len(data.get('recipes', []))} recipes"
            )
        return success, data

    # ============================================================
    # PAIRING PERSISTENCE
    # ============================================================

    def _save_pairing(self, pair_response: Dict[str, Any]) -> None:
        """Save pairing info to disk for persistence across reboots."""
        pairing_data = {
            "cloud_url": self.cloud_url,
            "api_key": self.api_key,
            "device_uuid": self.device_uuid,
            "device_id": self.device_id,
            "vessel_name": pair_response.get("vessel_name", ""),
            "vessel_imo": pair_response.get("vessel_imo", ""),
            "company_name": pair_response.get("company_name", ""),
            "fleet_name": pair_response.get("fleet_name", ""),
            "paired_at": time.time(),
        }

        filepath = settings.CLOUD_PAIRING_FILE
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)

        with open(filepath, "w") as f:
            json.dump(pairing_data, f, indent=2)

        logger.info(f"Pairing saved to {filepath}")

    def _load_pairing(self) -> bool:
        """Load pairing info from disk."""
        filepath = settings.CLOUD_PAIRING_FILE

        if not os.path.exists(filepath):
            logger.info("No pairing file found — device not paired")
            return False

        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            self.cloud_url = data["cloud_url"]
            self.api_key = data["api_key"]
            self.device_uuid = data["device_uuid"]
            self.device_id = data.get("device_id", settings.DEVICE_ID)
            self.is_paired = True

            logger.info(
                f"Loaded pairing: vessel={data.get('vessel_name')}, "
                f"company={data.get('company_name')}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to load pairing: {e}")
            return False

    def get_pairing_info(self) -> Optional[Dict[str, Any]]:
        """Get saved pairing info, or None if not paired."""
        filepath = settings.CLOUD_PAIRING_FILE
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except Exception:
            return None

    def unpair(self) -> None:
        """Remove pairing (factory reset cloud connection)."""
        filepath = settings.CLOUD_PAIRING_FILE
        if os.path.exists(filepath):
            os.remove(filepath)
        self.cloud_url = ""
        self.api_key = ""
        self.device_uuid = ""
        self.is_paired = False
        logger.info("Device unpaired from cloud")

    # ============================================================
    # HTTP HELPERS (stdlib only — no requests/httpx dependency)
    # ============================================================

    def _http_post(
        self, url: str, payload: dict, auth: bool = False, timeout: int = 30
    ) -> Tuple[bool, Dict[str, Any]]:
        """Make an HTTP POST request."""
        try:
            data = json.dumps(payload).encode("utf-8")
            req = Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("Accept", "application/json")

            if auth and self.api_key:
                req.add_header("X-API-Key", self.api_key)

            with urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
                return True, json.loads(body) if body else {}

        except HTTPError as e:
            try:
                body = e.read().decode("utf-8")
                error_data = json.loads(body)
            except Exception:
                error_data = {"detail": str(e), "status_code": e.code}
            logger.error(f"HTTP {e.code}: {url} — {error_data}")
            return False, error_data

        except URLError as e:
            logger.error(f"Connection error: {url} — {e.reason}")
            return False, {"detail": f"Connection error: {e.reason}"}

        except Exception as e:
            logger.error(f"Request error: {url} — {e}")
            return False, {"detail": str(e)}

    def _http_get(
        self, url: str, auth: bool = False, timeout: int = 30
    ) -> Tuple[bool, Dict[str, Any]]:
        """Make an HTTP GET request."""
        try:
            req = Request(url, method="GET")
            req.add_header("Accept", "application/json")

            if auth and self.api_key:
                req.add_header("X-API-Key", self.api_key)

            with urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
                return True, json.loads(body) if body else {}

        except HTTPError as e:
            try:
                body = e.read().decode("utf-8")
                error_data = json.loads(body)
            except Exception:
                error_data = {"detail": str(e), "status_code": e.code}
            logger.error(f"HTTP {e.code}: {url} — {error_data}")
            return False, error_data

        except URLError as e:
            logger.error(f"Connection error: {url} — {e.reason}")
            return False, {"detail": f"Connection error: {e.reason}"}

        except Exception as e:
            logger.error(f"Request error: {url} — {e}")
            return False, {"detail": str(e)}
