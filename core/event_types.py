"""
Event Type Definitions

Every action in the system generates an event. Events are:
  1. Saved to the local SQLite event log
  2. Queued for cloud sync
  3. Broadcast to UI and other subscribers via the event bus
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any, Dict
import time
import uuid


class EventType(Enum):
    """All possible event types in the system."""

    # Inventory events
    CAN_PLACED = "can_placed"
    CAN_REMOVED = "can_removed"
    CAN_RETURNED = "can_returned"
    WEIGHT_CHANGED = "weight_changed"
    UNAUTHORIZED_REMOVAL = "unauthorized_removal"
    CAN_WRONG_SLOT = "can_wrong_slot"
    CAN_CONSUMED = "can_consumed"           # Timeout: can not returned

    # Mixing events
    MIX_SESSION_STARTED = "mix_session_started"
    MIX_BASE_WEIGHED = "mix_base_weighed"
    MIX_HARDENER_WEIGHED = "mix_hardener_weighed"
    MIX_THINNER_ADDED = "mix_thinner_added"
    MIX_COMPLETED = "mix_completed"
    MIX_OUT_OF_SPEC = "mix_out_of_spec"
    MIX_OVERRIDE = "mix_override"
    MIX_ABORTED = "mix_aborted"
    POT_LIFE_WARNING = "pot_life_warning"
    POT_LIFE_EXPIRED = "pot_life_expired"

    # Stock events
    STOCK_LOW = "stock_low"
    STOCK_CRITICAL = "stock_critical"
    CONSUMPTION_RECORDED = "consumption_recorded"

    # System events
    DEVICE_BOOT = "device_boot"
    SYNC_COMPLETED = "sync_completed"
    SYNC_FAILED = "sync_failed"
    SENSOR_ERROR = "sensor_error"
    CONFIG_UPDATED = "config_updated"
    CALIBRATION_DONE = "calibration_done"


@dataclass
class Event:
    """
    A single event in the system.

    Every event has a unique UUID, a type, a timestamp, and a data payload.
    Events are immutable once created (append-only log).
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = EventType.DEVICE_BOOT
    timestamp: float = field(default_factory=time.time)

    # Context
    device_id: str = ""
    shelf_id: str = ""
    slot_id: str = ""
    tag_id: str = ""
    session_id: str = ""
    user_name: str = ""

    # Flexible data payload (serialized to JSON for storage/sync)
    data: Dict[str, Any] = field(default_factory=dict)

    # Tracking
    confirmation: str = "unconfirmed"  # "confirmed" or "unconfirmed"
    synced: bool = False               # Has this been sent to cloud?
    sequence_num: int = 0              # Auto-incremented for ordering

    def to_dict(self) -> Dict[str, Any]:
        """Serialize event to dictionary (for JSON storage)."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "device_id": self.device_id,
            "shelf_id": self.shelf_id,
            "slot_id": self.slot_id,
            "tag_id": self.tag_id,
            "session_id": self.session_id,
            "user_name": self.user_name,
            "data": self.data,
            "confirmation": self.confirmation,
            "synced": self.synced,
            "sequence_num": self.sequence_num,
        }
