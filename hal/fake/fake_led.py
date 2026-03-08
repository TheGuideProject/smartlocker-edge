"""
Fake LED Driver (TEST mode)

Simulates LED slot indicators by printing state to console.
Useful for debugging UI/logic without physical LED hardware.
"""

import logging
from typing import Dict, Tuple

from hal.interfaces import LEDDriverInterface, LEDColor, LEDPattern

logger = logging.getLogger("smartlocker.sensor")


class FakeLEDDriver(LEDDriverInterface):
    """
    Simulated LED driver that prints LED states to the console.

    Usage:
        driver = FakeLEDDriver()
        driver.initialize()
        driver.set_slot("shelf1_slot1", LEDColor.GREEN, LEDPattern.SOLID)
        # Console output: [FAKE LED] shelf1_slot1 -> GREEN (solid)
    """

    def __init__(self):
        # Track state: slot_id -> (color, pattern)
        self._state: Dict[str, Tuple[LEDColor, LEDPattern]] = {}
        self._initialized = False

    def initialize(self) -> bool:
        self._initialized = True
        logger.info("[FAKE LED] Initialized")
        return True

    def set_slot(self, slot_id: str, color: LEDColor,
                 pattern: LEDPattern = LEDPattern.SOLID) -> None:
        self._state[slot_id] = (color, pattern)
        logger.info(f"[FAKE LED] {slot_id} -> {color.name} ({pattern.value})")

    def clear_slot(self, slot_id: str) -> None:
        self._state[slot_id] = (LEDColor.OFF, LEDPattern.SOLID)
        logger.info(f"[FAKE LED] {slot_id} -> OFF")

    def clear_all(self) -> None:
        for slot_id in list(self._state.keys()):
            self._state[slot_id] = (LEDColor.OFF, LEDPattern.SOLID)
        logger.info("[FAKE LED] All LEDs cleared")

    def shutdown(self) -> None:
        self.clear_all()
        self._initialized = False
        logger.info("[FAKE LED] Shutdown")

    # ---- TEST-ONLY METHODS ----

    def get_state(self, slot_id: str) -> Tuple[LEDColor, LEDPattern]:
        """Get current LED state for a slot (for test assertions)."""
        return self._state.get(slot_id, (LEDColor.OFF, LEDPattern.SOLID))

    def get_all_states(self) -> Dict[str, Tuple[LEDColor, LEDPattern]]:
        """Get all LED states (for debugging)."""
        return dict(self._state)
