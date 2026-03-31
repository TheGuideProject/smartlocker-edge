"""
Fake Buzzer Driver (TEST mode)

Simulates buzzer sounds by printing to console.
"""

import logging
from typing import Optional

from hal.interfaces import BuzzerDriverInterface, BuzzerPattern

logger = logging.getLogger("smartlocker.sensor")

# Emoji representations for console feedback
_PATTERN_DISPLAY = {
    BuzzerPattern.CONFIRM: "BEEP (confirm)",
    BuzzerPattern.WARNING: "BEEP-BEEP (warning)",
    BuzzerPattern.ERROR: "BZZZZZ (error)",
    BuzzerPattern.TARGET_REACHED: "BEEP-beep-BEEP (target reached)",
    BuzzerPattern.TICK: "tick",
    BuzzerPattern.ALARM: "BZZZ-BZZZ-BZZZ (ALARM LOOP)",
    BuzzerPattern.POUR_STEADY: "bip (pour steady)",
    BuzzerPattern.POUR_CLOSE: "bip-bip (pour close)",
    BuzzerPattern.POUR_TARGET: "BEEEEEP (pour target)",
}


class FakeBuzzerDriver(BuzzerDriverInterface):
    """
    Simulated buzzer that prints sound events to console.

    Usage:
        driver = FakeBuzzerDriver()
        driver.initialize()
        driver.play(BuzzerPattern.CONFIRM)
        # Console output: [FAKE BUZZER] BEEP (confirm)
    """

    def __init__(self):
        self._initialized = False
        self._last_pattern: Optional[BuzzerPattern] = None
        self._playing = False

    def initialize(self) -> bool:
        self._initialized = True
        logger.info("[FAKE BUZZER] Initialized")
        return True

    def play(self, pattern: BuzzerPattern) -> None:
        self._last_pattern = pattern
        self._playing = True
        display = _PATTERN_DISPLAY.get(pattern, pattern.value)
        logger.info(f"[FAKE BUZZER] {display}")

    def stop(self) -> None:
        self._playing = False
        logger.info("[FAKE BUZZER] Stopped")

    def shutdown(self) -> None:
        self.stop()
        self._initialized = False
        logger.info("[FAKE BUZZER] Shutdown")

    # ---- TEST-ONLY METHODS ----

    def get_last_pattern(self) -> Optional[BuzzerPattern]:
        """Get the last played pattern (for test assertions)."""
        return self._last_pattern

    def is_playing(self) -> bool:
        """Check if buzzer is currently playing."""
        return self._playing
