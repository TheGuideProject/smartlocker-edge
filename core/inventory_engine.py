"""
Inventory Engine

Tracks what is on each shelf slot by combining RFID tag readings
and weight measurements. Detects when cans are placed, removed,
returned, or consumed.

This is the core brain for inventory tracking.
"""

import logging
import time
from typing import Dict, List, Optional, Set, TYPE_CHECKING

from config import settings
from core.models import Slot, Shelf, SlotStatus, EventConfirmation
from core.event_types import Event, EventType
from core.event_bus import EventBus
from hal.interfaces import (
    RFIDDriverInterface, WeightDriverInterface,
    LEDDriverInterface, BuzzerDriverInterface,
    LEDColor, LEDPattern, BuzzerPattern, TagReading, WeightReading,
)

if TYPE_CHECKING:
    from persistence.database import Database

logger = logging.getLogger("smartlocker")


class InventoryEngine:
    """
    Manages inventory state across all shelves and slots.

    Main loop (called repeatedly by the application):
      1. Poll RFID readers for tag presence
      2. Read shelf weights
      3. Compare current state with previous state
      4. Detect changes (can placed, removed, returned)
      5. Publish events via the event bus
      6. Update LED indicators

    Works identically in TEST and LIVE mode (uses HAL interfaces).
    """

    def __init__(
        self,
        rfid: RFIDDriverInterface,
        weight: WeightDriverInterface,
        led: LEDDriverInterface,
        buzzer: BuzzerDriverInterface,
        event_bus: EventBus,
        shelves: Optional[List[Shelf]] = None,
    ):
        self.rfid = rfid
        self.weight = weight
        self.led = led
        self.buzzer = buzzer
        self.event_bus = event_bus

        # Database reference (set via set_database after init)
        # Must be declared BEFORE _build_default_shelves() which reads it
        self._db: Optional['Database'] = None

        # Build default shelf/slot configuration if not provided
        if shelves is None:
            shelves = self._build_default_shelves()
        self.shelves = {s.shelf_id: s for s in shelves}

        # Quick lookup: reader_id -> slot
        self._reader_to_slot: Dict[str, Slot] = {}
        for shelf in shelves:
            for slot in shelf.slots:
                self._reader_to_slot[slot.rfid_reader_id] = slot

        # Track which tags were seen in the PREVIOUS poll cycle
        self._previous_tags: Set[str] = set()

        # Track removal times for timeout logic
        self._removal_times: Dict[str, float] = {}  # slot_id -> removal timestamp

        # Whether there's an active touchscreen session (set by mixing engine)
        self.active_session = False

    def set_database(self, db: 'Database') -> None:
        """Set the database reference for product lookups and slot state persistence."""
        self._db = db
        logger.info("InventoryEngine: database reference set")

    def _lookup_tag_info(self, tag_uid: str) -> Dict:
        """Look up product info for a tag from the database.
        Returns a dict with product_id, product_name, lot_number, can_size_ml
        or empty values if DB is unavailable or tag not found."""
        info = {
            "product_id": "",
            "product_name": "",
            "lot_number": "",
            "can_size_ml": 0,
        }
        if not self._db:
            return info
        try:
            tag_data = self._db.get_rfid_tag_info(tag_uid)
            if tag_data:
                info["product_id"] = tag_data.get("product_id") or ""
                info["product_name"] = tag_data.get("product_name") or ""
                info["lot_number"] = tag_data.get("batch_number") or ""
                info["can_size_ml"] = tag_data.get("can_size_ml") or 0
        except Exception as e:
            logger.warning(f"Failed to look up tag info for {tag_uid}: {e}")
        return info

    def _persist_slot_state(self, slot: Slot) -> None:
        """Persist the current slot state to the database."""
        if not self._db:
            return
        try:
            self._db.update_slot_state(
                slot_id=slot.slot_id,
                status=slot.status.value,
                current_tag_id=slot.current_tag_id,
                current_product_id=slot.current_product_id,
                weight_when_placed_g=slot.weight_when_placed_g,
                weight_current_g=slot.weight_current_g,
            )
        except Exception as e:
            logger.warning(f"Failed to persist slot state for {slot.slot_id}: {e}")

    def _build_default_shelves(self) -> List[Shelf]:
        """Create default shelf(s) with configurable slot count."""
        slot_count = getattr(settings, 'SLOT_COUNT', 4)

        # Try reading from local DB config (cloud-synced value)
        if self._db:
            try:
                db_val = self._db.get_config("slot_count")
                if db_val and db_val.isdigit():
                    slot_count = int(db_val)
            except Exception:
                pass

        slot_count = max(1, min(60, slot_count))

        slots = []
        for i in range(1, slot_count + 1):
            slots.append(Slot(
                slot_id=f"shelf1_slot{i}",
                shelf_id="shelf1",
                position=i,
                rfid_reader_id=f"shelf1_slot{i}",
                led_index=i - 1,
            ))
        return [Shelf(
            shelf_id="shelf1",
            position=1,
            weight_channel="shelf1",
            slots=slots,
        )]

    def rebuild_shelves(self) -> None:
        """Rebuild shelf/slot config from DB (call after set_database)."""
        shelves = self._build_default_shelves()
        self.shelves = {s.shelf_id: s for s in shelves}
        self._reader_to_slot = {}
        for shelf in shelves:
            for slot in shelf.slots:
                self._reader_to_slot[slot.rfid_reader_id] = slot
        logger.info(f"Shelves rebuilt: {len(self._reader_to_slot)} slots configured")

    def initialize(self) -> bool:
        """Initialize all hardware and set initial state."""
        ok = True
        ok = ok and self.rfid.initialize()
        ok = ok and self.weight.initialize()
        ok = ok and self.led.initialize()
        ok = ok and self.buzzer.initialize()

        if ok:
            self.led.clear_all()
            # Publish boot event
            self.event_bus.publish(Event(
                event_type=EventType.DEVICE_BOOT,
                device_id=settings.DEVICE_ID,
                data={"mode": settings.MODE},
            ))
            logger.info("InventoryEngine initialized successfully")
        else:
            logger.error("InventoryEngine initialization FAILED")

        return ok

    def poll(self) -> None:
        """
        Main polling cycle. Call this repeatedly (every RFID_POLL_INTERVAL_MS).

        Reads all sensors, detects changes, publishes events.
        """
        # 1. Poll RFID tags
        current_readings = self.rfid.poll_tags()
        current_tag_ids = {r.tag_id for r in current_readings}
        current_by_reader = {r.reader_id: r for r in current_readings}

        # 2. Detect newly appeared tags (can placed)
        new_tags = current_tag_ids - self._previous_tags
        for reading in current_readings:
            if reading.tag_id in new_tags:
                self._handle_tag_appeared(reading)

        # 3. Detect disappeared tags (can removed)
        gone_tags = self._previous_tags - current_tag_ids
        for tag_id in gone_tags:
            self._handle_tag_disappeared(tag_id)

        # 4. Check removal timeouts
        self._check_removal_timeouts()

        # 5. Read shelf weights (for logging and anomaly detection)
        for shelf in self.shelves.values():
            try:
                reading = self.weight.read_weight(shelf.weight_channel)
                self._process_weight_reading(shelf, reading)
            except Exception as e:
                logger.warning(f"Weight read failed for {shelf.shelf_id}: {e}")

        # Update previous state
        self._previous_tags = current_tag_ids

    def _handle_tag_appeared(self, reading: TagReading) -> None:
        """A new tag was detected — can was placed on a slot."""
        slot = self._reader_to_slot.get(reading.reader_id)
        if not slot:
            logger.warning(f"Tag {reading.tag_id} on unknown reader {reading.reader_id}")
            return

        # Check if this slot previously had a can removed (= can returned)
        was_removed = slot.status == SlotStatus.REMOVED

        # Save weight before placement for return consumption calc
        weight_at_removal_g = slot.weight_when_placed_g if was_removed else 0.0

        # Read current weight from the shelf
        current_weight_g = 0.0
        try:
            shelf = self.shelves.get(slot.shelf_id)
            if shelf:
                w = self.weight.read_weight(shelf.weight_channel)
                current_weight_g = w.grams
        except Exception as e:
            logger.warning(f"Weight read failed during tag appeared: {e}")

        # Look up product info from database
        tag_info = self._lookup_tag_info(reading.tag_id)

        # Update slot state
        old_tag = slot.current_tag_id
        slot.current_tag_id = reading.tag_id
        slot.current_product_id = tag_info["product_id"]
        slot.status = SlotStatus.OCCUPIED
        slot.last_change_time = time.time()
        slot.weight_current_g = current_weight_g

        # Remove from removal tracking
        self._removal_times.pop(slot.slot_id, None)

        if was_removed:
            # Can returned — read weight to estimate usage
            event_type = EventType.CAN_RETURNED
            self.buzzer.play(BuzzerPattern.CONFIRM)
            self.led.set_slot(slot.slot_id, LEDColor.GREEN, LEDPattern.SOLID)

            consumed_g = max(0.0, weight_at_removal_g - current_weight_g)

            event_data = {
                "reader_id": reading.reader_id,
                "signal_strength": reading.signal_strength,
                "previous_tag": old_tag,
                "tag_uid": reading.tag_id,
                "product_id": tag_info["product_id"],
                "product_name": tag_info["product_name"],
                "weight_at_removal_g": weight_at_removal_g,
                "weight_at_return_g": current_weight_g,
                "consumed_g": consumed_g,
                "slot_id": slot.slot_id,
            }

            # Update slot weight to current (after return)
            slot.weight_when_placed_g = current_weight_g
        else:
            # New can placed
            event_type = EventType.CAN_PLACED
            self.buzzer.play(BuzzerPattern.TICK)
            self.led.set_slot(slot.slot_id, LEDColor.GREEN, LEDPattern.SOLID)

            # Store weight at placement
            slot.weight_when_placed_g = current_weight_g

            event_data = {
                "reader_id": reading.reader_id,
                "signal_strength": reading.signal_strength,
                "previous_tag": old_tag,
                "tag_uid": reading.tag_id,
                "product_id": tag_info["product_id"],
                "product_name": tag_info["product_name"],
                "lot_number": tag_info["lot_number"],
                "can_size_ml": tag_info["can_size_ml"],
                "weight_g": current_weight_g,
                "slot_id": slot.slot_id,
            }

        # Check if can returned to wrong slot
        if was_removed and old_tag and reading.tag_id != old_tag:
            event_type = EventType.CAN_WRONG_SLOT
            self.led.set_slot(slot.slot_id, LEDColor.RED, LEDPattern.BLINK_FAST)
            self.buzzer.play(BuzzerPattern.WARNING)

        # Persist slot state to database
        self._persist_slot_state(slot)

        self.event_bus.publish(Event(
            event_type=event_type,
            device_id=settings.DEVICE_ID,
            shelf_id=slot.shelf_id,
            slot_id=slot.slot_id,
            tag_id=reading.tag_id,
            data=event_data,
            confirmation=(
                EventConfirmation.CONFIRMED.value if self.active_session
                else EventConfirmation.UNCONFIRMED.value
            ),
        ))

        # Clear LED after a short delay (in real system, use async timer)
        # For now, leave it on until next event

    def _handle_tag_disappeared(self, tag_id: str) -> None:
        """A tag is no longer detected — can was removed from a slot."""
        # Find which slot had this tag
        slot = None
        for s in self._reader_to_slot.values():
            if s.current_tag_id == tag_id:
                slot = s
                break

        if not slot:
            logger.debug(f"Tag {tag_id} disappeared but not tracked to any slot")
            return

        # Read current weight from shelf
        weight_before = slot.weight_when_placed_g
        try:
            shelf = self.shelves.get(slot.shelf_id)
            if shelf:
                w = self.weight.read_weight(shelf.weight_channel)
                weight_before = w.grams
                slot.weight_current_g = w.grams
        except Exception as e:
            logger.warning(f"Weight read failed during tag disappeared: {e}")

        # Store the weight at removal for consumption calculation on return
        slot.weight_when_placed_g = weight_before

        # Look up product info from database
        tag_info = self._lookup_tag_info(tag_id)

        # Update slot state
        slot.status = SlotStatus.REMOVED
        slot.last_change_time = time.time()

        # Start removal timer
        self._removal_times[slot.slot_id] = time.time()

        # Determine if this is authorized (active session) or unauthorized
        if self.active_session:
            event_type = EventType.CAN_REMOVED
            self.led.clear_slot(slot.slot_id)
        else:
            event_type = EventType.UNAUTHORIZED_REMOVAL
            self.led.set_slot(slot.slot_id, LEDColor.RED, LEDPattern.BLINK_FAST)
            self.buzzer.play(BuzzerPattern.ERROR)

        # Persist slot state to database
        self._persist_slot_state(slot)

        self.event_bus.publish(Event(
            event_type=event_type,
            device_id=settings.DEVICE_ID,
            shelf_id=slot.shelf_id,
            slot_id=slot.slot_id,
            tag_id=tag_id,
            data={
                "tag_uid": tag_id,
                "product_id": tag_info["product_id"],
                "product_name": tag_info["product_name"],
                "weight_at_removal_g": weight_before,
                "slot_id": slot.slot_id,
            },
            confirmation=(
                EventConfirmation.CONFIRMED.value if self.active_session
                else EventConfirmation.UNCONFIRMED.value
            ),
        ))

    def _check_removal_timeouts(self) -> None:
        """Check if any removed cans have been gone too long."""
        now = time.time()
        to_remove = []

        for slot_id, removed_at in self._removal_times.items():
            elapsed = now - removed_at

            slot = None
            for s in self._reader_to_slot.values():
                if s.slot_id == slot_id:
                    slot = s
                    break

            if not slot or slot.status != SlotStatus.REMOVED:
                to_remove.append(slot_id)
                continue

            if elapsed >= settings.CAN_REMOVAL_CONSUMED_TIMEOUT_S:
                # 12 hours: mark as consumed
                slot.status = SlotStatus.EMPTY
                slot.current_tag_id = None
                slot.current_product_id = None
                to_remove.append(slot_id)

                # Persist slot state
                self._persist_slot_state(slot)

                self.event_bus.publish(Event(
                    event_type=EventType.CAN_CONSUMED,
                    device_id=settings.DEVICE_ID,
                    slot_id=slot_id,
                    data={"elapsed_hours": elapsed / 3600},
                ))
                logger.info(f"Slot {slot_id}: can consumed (timeout {elapsed/3600:.1f}h)")

            elif elapsed >= settings.CAN_REMOVAL_TIMEOUT_S:
                # 4 hours: mark as in use elsewhere
                if slot.status != SlotStatus.IN_USE_ELSEWHERE:
                    slot.status = SlotStatus.IN_USE_ELSEWHERE
                    logger.info(f"Slot {slot_id}: can in use elsewhere ({elapsed/3600:.1f}h)")

        for slot_id in to_remove:
            self._removal_times.pop(slot_id, None)

    def _process_weight_reading(self, shelf: Shelf, reading: WeightReading) -> None:
        """Process a weight reading for anomaly detection and logging."""
        # For now, just store the reading.
        # Weight-based usage estimation is handled in usage_calculator.py
        pass

    # ---- PUBLIC API ----

    def get_slot(self, slot_id: str) -> Optional[Slot]:
        """Get a slot by ID."""
        return self._reader_to_slot.get(slot_id)

    def get_all_slots(self) -> List[Slot]:
        """Get all slots across all shelves."""
        return list(self._reader_to_slot.values())

    def get_occupied_slots(self) -> List[Slot]:
        """Get all slots that currently have a can."""
        return [s for s in self._reader_to_slot.values()
                if s.status == SlotStatus.OCCUPIED]

    def get_slot_for_tag(self, tag_id: str) -> Optional[Slot]:
        """Find which slot has a specific tag."""
        for slot in self._reader_to_slot.values():
            if slot.current_tag_id == tag_id:
                return slot
        return None

    def get_slot_id_for_product(self, product_id: str) -> Optional[str]:
        """Find slot_id containing a product."""
        for shelf in self.shelves.values():
            for slot in shelf.slots:
                if slot.current_product_id == product_id and slot.status == SlotStatus.OCCUPIED:
                    return slot.slot_id
        return None

    def get_slot_id_for_tag(self, tag_id: str) -> Optional[str]:
        """Find slot_id where a tag was last seen."""
        for shelf in self.shelves.values():
            for slot in shelf.slots:
                if slot.current_tag_id == tag_id:
                    return slot.slot_id
        return None

    def shutdown(self) -> None:
        """Clean shutdown of all hardware."""
        self.led.clear_all()
        self.rfid.shutdown()
        self.weight.shutdown()
        self.led.shutdown()
        self.buzzer.shutdown()
        logger.info("InventoryEngine shut down")
