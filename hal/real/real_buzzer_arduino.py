"""
Real Buzzer Driver - Piezo via Arduino Nano Serial Bridge

Controls a piezo buzzer connected to the Arduino Nano (pin A0).
Shares the serial connection with the weight driver.

Commands sent to Arduino:
  {"cmd":"buzz","pattern":"confirm"}   // named pattern
  {"cmd":"buzz","pattern":"warning"}
  {"cmd":"buzz","pattern":"error"}
  {"cmd":"buzz","pattern":"tick"}
  {"cmd":"buzz","pattern":"target"}
  {"cmd":"buzz","pattern":"alarm"}
  {"cmd":"buzz","freq":1000,"dur":200} // custom tone
  {"cmd":"buzz_off"}                   // stop buzzer
"""

import logging
from hal.interfaces import BuzzerDriverInterface, BuzzerPattern

logger = logging.getLogger("smartlocker.sensor")

# Map BuzzerPattern enum to Arduino pattern names
_PATTERN_MAP = {
    BuzzerPattern.CONFIRM: "confirm",
    BuzzerPattern.WARNING: "warning",
    BuzzerPattern.ERROR: "error",
    BuzzerPattern.TICK: "tick",
    BuzzerPattern.TARGET_REACHED: "target",
    BuzzerPattern.ALARM: "alarm",
    BuzzerPattern.POUR_STEADY: "tick",     # reuse tick for steady pour
    BuzzerPattern.POUR_CLOSE: "warning",   # reuse warning for close
    BuzzerPattern.POUR_TARGET: "target",   # reuse target
}


class RealBuzzerDriverArduino(BuzzerDriverInterface):
    """
    Buzzer driver that sends commands to Arduino Nano via shared serial.

    Requires a RealWeightDriver instance (which owns the serial connection).
    Call set_weight_driver() after both drivers are created.
    """

    def __init__(self):
        self._weight_driver = None
        self._initialized = False

    def set_weight_driver(self, weight_driver) -> None:
        """Inject the weight driver that owns the Arduino serial connection."""
        self._weight_driver = weight_driver

    def initialize(self) -> bool:
        if self._weight_driver is None:
            logger.warning("[ARDUINO BUZZER] No weight driver set.")
            return False

        # Test with a quick tick
        resp = self._weight_driver.send_command({"cmd": "buzz", "pattern": "tick"})
        if resp and "ok" in resp:
            logger.info("[ARDUINO BUZZER] Connected via Arduino serial bridge")
            self._initialized = True
            return True
        else:
            logger.warning("[ARDUINO BUZZER] No response, continuing anyway")
            self._initialized = True
            return True

    def play(self, pattern: BuzzerPattern) -> None:
        if not self._initialized or not self._weight_driver:
            return

        arduino_pattern = _PATTERN_MAP.get(pattern, "tick")
        self._weight_driver.send_command({
            "cmd": "buzz", "pattern": arduino_pattern,
        })

    def play_tone(self, frequency: int, duration_ms: int) -> None:
        """Play a custom tone (frequency in Hz, duration in ms)."""
        if not self._initialized or not self._weight_driver:
            return
        self._weight_driver.send_command({
            "cmd": "buzz", "freq": frequency, "dur": duration_ms,
        })

    def stop(self) -> None:
        if self._weight_driver:
            self._weight_driver.send_command({"cmd": "buzz_off"})

    def shutdown(self) -> None:
        self.stop()
        self._initialized = False
        logger.info("[ARDUINO BUZZER] Shutdown")
