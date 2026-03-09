"""
Alarm Manager - Central alarm handling for SmartLocker Edge.

Manages alarm lifecycle: raise -> active -> acknowledged -> resolved
Persists alarms to SQLite. Syncs to cloud via event bus.
Calls UI callback for critical alarms (full-screen overlay).
"""

import time
import uuid
import logging
from typing import List, Dict, Any, Optional, Callable
from core.error_codes import ErrorCode, get_error_by_code
from core.event_types import Event, EventType

logger = logging.getLogger("smartlocker.alarm")


class Alarm:
    """Single alarm instance."""

    def __init__(self, error_code: ErrorCode, details: str = "", source: str = ""):
        self.alarm_id = str(uuid.uuid4())
        self.error_code = error_code
        self.details = details
        self.source = source  # e.g. "shelf1_slot2", "system"
        self.raised_at = time.time()
        self.acknowledged_at = None
        self.resolved_at = None
        self.support_requested = False
        self.support_requested_at = None
        self.status = "active"  # active, acknowledged, resolved

    def to_dict(self) -> dict:
        return {
            "alarm_id": self.alarm_id,
            "error_code": self.error_code.code,
            "error_title": self.error_code.title,
            "severity": self.error_code.severity,
            "category": self.error_code.category,
            "details": self.details,
            "source": self.source,
            "raised_at": self.raised_at,
            "acknowledged_at": self.acknowledged_at,
            "resolved_at": self.resolved_at,
            "support_requested": self.support_requested,
            "status": self.status,
        }


class AlarmManager:
    """Central alarm management."""

    def __init__(self, event_bus, db):
        self.event_bus = event_bus
        self.db = db
        self._active_alarms: List[Alarm] = []
        self._alarm_history: List[Alarm] = []

        # UI callbacks (set by app.py)
        self.on_critical_alarm: Optional[Callable] = None
        self.on_alarm_cleared: Optional[Callable] = None
        self.on_support_requested: Optional[Callable] = None

        # Dedup: don't raise same error code within cooldown period
        self._last_raised: Dict[str, float] = {}
        self.COOLDOWN_S = 60  # Don't re-raise same alarm within 60s

    def raise_alarm(self, error_code: ErrorCode, details: str = "",
                    source: str = "") -> Optional[Alarm]:
        """Raise a new alarm. Returns Alarm if raised, None if deduped."""
        # Dedup check
        now = time.time()
        key = f"{error_code.code}:{source}"
        if key in self._last_raised and (now - self._last_raised[key]) < self.COOLDOWN_S:
            return None
        self._last_raised[key] = now

        alarm = Alarm(error_code, details, source)
        self._active_alarms.append(alarm)

        # Persist to DB
        self.db.save_alarm(alarm.to_dict())

        # Publish event for cloud sync
        self.event_bus.publish(Event(
            event_type=EventType.ALARM_RAISED,
            data=alarm.to_dict(),
        ))

        logger.warning(
            f"ALARM RAISED: {error_code.code} - {error_code.title} "
            f"[{error_code.severity}] {details}"
        )

        # Call UI callback for critical alarms
        if error_code.severity == "critical" and self.on_critical_alarm:
            self.on_critical_alarm(alarm)

        return alarm

    def acknowledge_alarm(self, alarm_id: str) -> bool:
        """User acknowledges seeing the alarm."""
        for alarm in self._active_alarms:
            if alarm.alarm_id == alarm_id:
                alarm.acknowledged_at = time.time()
                alarm.status = "acknowledged"
                self.db.update_alarm(alarm_id, {
                    "acknowledged_at": alarm.acknowledged_at,
                    "status": "acknowledged",
                })
                self.event_bus.publish(Event(
                    event_type=EventType.ALARM_ACKNOWLEDGED,
                    data={
                        "alarm_id": alarm_id,
                        "error_code": alarm.error_code.code,
                    },
                ))
                return True
        return False

    def resolve_alarm(self, alarm_id: str) -> bool:
        """Mark alarm as resolved."""
        for alarm in self._active_alarms[:]:
            if alarm.alarm_id == alarm_id:
                alarm.resolved_at = time.time()
                alarm.status = "resolved"
                self._active_alarms.remove(alarm)
                self._alarm_history.append(alarm)
                self.db.update_alarm(alarm_id, {
                    "resolved_at": alarm.resolved_at,
                    "status": "resolved",
                })
                self.event_bus.publish(Event(
                    event_type=EventType.ALARM_RESOLVED,
                    data={
                        "alarm_id": alarm_id,
                        "error_code": alarm.error_code.code,
                    },
                ))
                if self.on_alarm_cleared:
                    self.on_alarm_cleared(alarm)
                return True
        return False

    def resolve_by_code(self, error_code: ErrorCode, source: str = "") -> int:
        """
        Resolve all active alarms with given error code
        (and optionally source). Returns count resolved.
        """
        count = 0
        for alarm in self._active_alarms[:]:
            if alarm.error_code == error_code:
                if source and alarm.source != source:
                    continue
                self.resolve_alarm(alarm.alarm_id)
                count += 1
        return count

    def request_support(self, alarm_id: str, user_name: str = "") -> bool:
        """Request PPG support for an alarm."""
        for alarm in self._active_alarms + self._alarm_history:
            if alarm.alarm_id == alarm_id:
                alarm.support_requested = True
                alarm.support_requested_at = time.time()
                self.db.update_alarm(alarm_id, {
                    "support_requested": True,
                    "support_requested_at": alarm.support_requested_at,
                })
                # Publish support request event for cloud sync
                self.event_bus.publish(Event(
                    event_type=EventType.SUPPORT_REQUESTED,
                    data={
                        "alarm_id": alarm_id,
                        "error_code": alarm.error_code.code,
                        "error_title": alarm.error_code.title,
                        "details": alarm.details,
                        "user_name": user_name,
                    },
                ))
                logger.info(f"SUPPORT REQUESTED: {alarm.error_code.code} by {user_name}")
                if self.on_support_requested:
                    self.on_support_requested(alarm)
                return True
        return False

    def get_active_alarms(self) -> List[Dict]:
        """Get all active (unresolved) alarms."""
        return [a.to_dict() for a in self._active_alarms]

    def get_critical_alarms(self) -> List[Dict]:
        """Get active critical alarms."""
        return [
            a.to_dict() for a in self._active_alarms
            if a.error_code.severity == "critical"
        ]

    def get_alarm_history(self, limit: int = 50) -> List[Dict]:
        """Get recent alarm history from DB."""
        return self.db.get_alarm_history(limit)

    def has_critical(self) -> bool:
        """Check if any critical alarms are active."""
        return any(a.error_code.severity == "critical" for a in self._active_alarms)

    def active_count(self) -> int:
        """Return count of currently active alarms."""
        return len(self._active_alarms)

    # --- Simulation methods (for TEST mode) ---

    def simulate_alarm(self, error_code_str: str,
                       details: str = "") -> Optional[Alarm]:
        """Simulate an alarm by error code string (e.g. 'E001')."""
        ec = get_error_by_code(error_code_str)
        if ec:
            return self.raise_alarm(
                ec,
                details=details or "SIMULATED",
                source="simulation",
            )
        return None

    def simulate_demo_sequence(self):
        """Run a demo sequence of alarms for testing."""
        import threading

        def _run():
            time.sleep(1)
            self.simulate_alarm("E021", "CPU at 72\u00b0C")
            time.sleep(3)
            self.simulate_alarm("E066", "SIGMACOVER 280 below 25%")
            time.sleep(3)
            self.simulate_alarm("E001", "RFID reader on shelf1 not responding")
            time.sleep(3)
            self.simulate_alarm("E020", "CPU at 85\u00b0C - CRITICAL")

        threading.Thread(target=_run, daemon=True).start()

    def simulate_all_categories(self):
        """Simulate one alarm from each category."""
        self.simulate_alarm("E001", "RFID reader disconnected from USB")
        self.simulate_alarm("E020", "CPU temperature 85\u00b0C")
        self.simulate_alarm("E040", "Database locked for 30 seconds")
        self.simulate_alarm("E060", "Can removed from slot 2 without session")
        self.simulate_alarm("E081", "SIGMACOVER 280 pot-life expired")

    def clear_all(self):
        """Clear all alarms (for testing)."""
        for alarm in self._active_alarms[:]:
            self.resolve_alarm(alarm.alarm_id)
        self._alarm_history.clear()
