"""
Fake RFID Driver (TEST mode)

Simulates RFID/NFC tag detection without real hardware.
You can configure which tags are "present" on which readers,
and simulate removing/placing cans by calling add_tag() / remove_tag().
"""

import logging
import time
from typing import List, Dict, Optional

from hal.interfaces import RFIDDriverInterface, TagReading

logger = logging.getLogger("smartlocker.sensor")


class FakeRFIDDriver(RFIDDriverInterface):
    """
    Simulated RFID reader for testing.

    Usage:
        driver = FakeRFIDDriver(reader_ids=["shelf1_slot1", "shelf1_slot2", "shelf1_slot3"])
        driver.initialize()

        # Simulate placing a can on slot 1
        driver.add_tag("shelf1_slot1", "TAG-001")

        # Poll to detect it
        tags = driver.poll_tags()  # Returns [TagReading(tag_id="TAG-001", ...)]

        # Simulate removing the can
        driver.remove_tag("shelf1_slot1")

        tags = driver.poll_tags()  # Returns []
    """

    def __init__(self, reader_ids: Optional[List[str]] = None):
        # Default readers: one shelf with 4 slots
        self._reader_ids = reader_ids or [
            "shelf1_slot1", "shelf1_slot2", "shelf1_slot3", "shelf1_slot4"
        ]
        # Map reader_id -> tag_id (None = no tag present)
        self._tags: Dict[str, Optional[str]] = {rid: None for rid in self._reader_ids}
        self._initialized = False

    def initialize(self) -> bool:
        self._initialized = True
        logger.info(f"[FAKE RFID] Initialized with readers: {self._reader_ids}")
        return True

    def poll_tags(self) -> List[TagReading]:
        if not self._initialized:
            return []
        readings = []
        for reader_id, tag_id in self._tags.items():
            if tag_id is not None:
                readings.append(TagReading(
                    tag_id=tag_id,
                    reader_id=reader_id,
                    signal_strength=85,  # Simulated good signal
                    timestamp=time.time(),
                ))
        return readings

    def get_reader_ids(self) -> List[str]:
        return list(self._reader_ids)

    def is_healthy(self) -> bool:
        return self._initialized

    def shutdown(self) -> None:
        self._initialized = False
        logger.info("[FAKE RFID] Shutdown")

    # ---- TEST-ONLY METHODS (not in interface) ----

    def add_tag(self, reader_id: str, tag_id: str) -> None:
        """Simulate placing a tagged can on a reader slot."""
        if reader_id not in self._tags:
            raise ValueError(f"Unknown reader: {reader_id}. Available: {list(self._tags.keys())}")
        self._tags[reader_id] = tag_id
        logger.info(f"[FAKE RFID] Tag '{tag_id}' placed on '{reader_id}'")

    def remove_tag(self, reader_id: str) -> None:
        """Simulate removing a can from a reader slot."""
        if reader_id not in self._tags:
            raise ValueError(f"Unknown reader: {reader_id}")
        old_tag = self._tags[reader_id]
        self._tags[reader_id] = None
        logger.info(f"[FAKE RFID] Tag '{old_tag}' removed from '{reader_id}'")

    def set_all_tags(self, tag_map: Dict[str, Optional[str]]) -> None:
        """Set all tags at once. Useful for loading a test scenario."""
        for reader_id, tag_id in tag_map.items():
            if reader_id in self._tags:
                self._tags[reader_id] = tag_id

    def get_current_state(self) -> Dict[str, Optional[str]]:
        """Return current tag state (for debugging)."""
        return dict(self._tags)
