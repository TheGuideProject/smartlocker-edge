"""
Real LED Driver - WS2812B via Arduino Nano Serial Bridge

Controls WS2812B addressable LEDs connected to the Arduino Nano.
Shares the same serial connection as the weight driver.

LED layout (configured in Arduino firmware):
  - LED 0..3  = Shelf slot indicators (under cans)
  - LED 4..11 = Balance bar (weight progress during mixing)

The Arduino handles all LED timing/animation. This driver just
sends high-level commands.

Commands sent to Arduino:
  {"cmd":"led","idx":0,"r":0,"g":255,"b":0}          // single LED
  {"cmd":"led_range","from":0,"to":4,"r":255,"g":0,"b":0}  // range
  {"cmd":"led_off"}                                    // all off
  {"cmd":"led_bar","pct":75,"r":0,"g":255,"b":0}     // balance bar %
  {"cmd":"led_bright","val":50}                        // brightness 0-255

Graceful fallback: if Arduino weight driver not available, all ops are no-ops.
"""

import logging
import threading
import time
from typing import Dict, Tuple, Optional

from hal.interfaces import LEDDriverInterface, LEDColor, LEDPattern

logger = logging.getLogger("smartlocker.sensor")


class RealLEDDriverArduino(LEDDriverInterface):
    """
    LED driver that sends commands to Arduino Nano via shared serial.

    Requires a RealWeightDriver instance (which owns the serial connection).
    Call set_weight_driver() after both drivers are created.
    """

    def __init__(self):
        self._weight_driver = None  # Set after construction
        self._initialized = False

        # Map slot IDs to physical LED indices on the Arduino chain
        self._slot_map: Dict[str, int] = {
            "shelf1_slot1": 0,
            "shelf1_slot2": 1,
            "shelf1_slot3": 2,
            "shelf1_slot4": 3,
        }

        # Track current state for pattern animation
        self._state: Dict[str, Tuple[LEDColor, LEDPattern]] = {}

        # Animation thread for blink/pulse (runs on Python side)
        self._animation_thread: Optional[threading.Thread] = None
        self._animation_running = False

    def set_weight_driver(self, weight_driver) -> None:
        """
        Inject the weight driver that owns the Arduino serial connection.
        Must be called before initialize().
        """
        self._weight_driver = weight_driver

    def initialize(self) -> bool:
        """Initialize LED driver. Requires weight driver to be connected."""
        if self._weight_driver is None:
            logger.warning("[ARDUINO LED] No weight driver set. Call set_weight_driver() first.")
            return False

        # Test communication
        resp = self._weight_driver.send_command({"cmd": "led_off"})
        if resp and "ok" in resp:
            logger.info("[ARDUINO LED] Connected via Arduino serial bridge")
            self._initialized = True

            # Start animation thread
            self._animation_running = True
            self._animation_thread = threading.Thread(
                target=self._animation_loop, daemon=True,
                name="Arduino-LED-anim",
            )
            self._animation_thread.start()

            return True
        else:
            logger.warning("[ARDUINO LED] Arduino not responding to LED commands")
            # Still mark as initialized — LEDs are optional
            self._initialized = True
            return True

    def set_slot(self, slot_id: str, color: LEDColor,
                 pattern: LEDPattern = LEDPattern.SOLID) -> None:
        """Set color and pattern for a shelf slot LED."""
        if not self._initialized or not self._weight_driver:
            return

        self._state[slot_id] = (color, pattern)

        led_index = self._slot_map.get(slot_id)
        if led_index is None:
            logger.warning(f"[ARDUINO LED] Unknown slot '{slot_id}'")
            return

        r, g, b = color.value
        if pattern == LEDPattern.SOLID:
            self._weight_driver.send_command({
                "cmd": "led", "idx": led_index,
                "r": r, "g": g, "b": b,
            })
        # Blink/pulse patterns handled by animation thread

    def clear_slot(self, slot_id: str) -> None:
        """Turn off LED for a specific slot."""
        self._state.pop(slot_id, None)
        led_index = self._slot_map.get(slot_id)
        if led_index is not None and self._weight_driver:
            self._weight_driver.send_command({
                "cmd": "led", "idx": led_index,
                "r": 0, "g": 0, "b": 0,
            })

    def clear_all(self) -> None:
        """Turn off all LEDs."""
        self._state.clear()
        if self._weight_driver:
            self._weight_driver.send_command({"cmd": "led_off"})

    def shutdown(self) -> None:
        """Turn off all LEDs and stop animation."""
        self._animation_running = False
        if self._animation_thread and self._animation_thread.is_alive():
            self._animation_thread.join(timeout=2.0)

        self.clear_all()
        self._initialized = False
        logger.info("[ARDUINO LED] Shutdown")

    # ============================================================
    # BALANCE BAR - Weight progress indicator
    # ============================================================

    def set_balance_bar(self, percentage: float, color: LEDColor = LEDColor.GREEN) -> None:
        """
        Set the balance bar to show weight progress during mixing.

        Args:
            percentage: 0-100 (can exceed 100 for overpour)
            color: LED color for the filled portion
        """
        if not self._weight_driver:
            return

        pct = max(0, min(int(percentage), 100))
        r, g, b = color.value
        self._weight_driver.send_command({
            "cmd": "led_bar", "pct": pct,
            "r": r, "g": g, "b": b,
        })

    def set_balance_bar_smart(self, percentage: float) -> None:
        """
        Smart balance bar: auto-selects color based on progress.

          0-80%  = GREEN  (pouring, on track)
         80-95%  = YELLOW (getting close)
         95-100% = GREEN  (target zone, perfect)
         >100%   = RED    (overpour!)
        """
        if percentage <= 80:
            self.set_balance_bar(percentage, LEDColor.GREEN)
        elif percentage <= 95:
            self.set_balance_bar(percentage, LEDColor.YELLOW)
        elif percentage <= 102:
            self.set_balance_bar(min(percentage, 100), LEDColor.GREEN)
        else:
            self.set_balance_bar(100, LEDColor.RED)

    def clear_balance_bar(self) -> None:
        """Turn off the balance bar."""
        if self._weight_driver:
            self._weight_driver.send_command({
                "cmd": "led_bar", "pct": 0,
                "r": 0, "g": 0, "b": 0,
            })

    # ============================================================
    # SHELF STOCK INDICATORS
    # ============================================================

    def set_slot_stock_level(self, slot_id: str, percentage: float) -> None:
        """
        Set slot LED color based on remaining stock percentage.

          >50%  = GREEN
          20-50% = YELLOW
          <20%  = RED
          0%    = OFF
        """
        if percentage <= 0:
            self.clear_slot(slot_id)
        elif percentage < 20:
            self.set_slot(slot_id, LEDColor.RED, LEDPattern.SOLID)
        elif percentage < 50:
            self.set_slot(slot_id, LEDColor.YELLOW, LEDPattern.SOLID)
        else:
            self.set_slot(slot_id, LEDColor.GREEN, LEDPattern.SOLID)

    # ============================================================
    # ANIMATION THREAD (blink/pulse patterns)
    # ============================================================

    def _animation_loop(self) -> None:
        """Background thread for blink/pulse patterns."""
        tick = 0
        while self._animation_running:
            try:
                for slot_id, (color, pattern) in list(self._state.items()):
                    led_index = self._slot_map.get(slot_id)
                    if led_index is None:
                        continue

                    r, g, b = color.value

                    if pattern == LEDPattern.BLINK_SLOW:
                        on = (tick % 30) < 15
                        self._weight_driver.send_command({
                            "cmd": "led", "idx": led_index,
                            "r": r if on else 0,
                            "g": g if on else 0,
                            "b": b if on else 0,
                        })

                    elif pattern == LEDPattern.BLINK_FAST:
                        on = (tick % 10) < 5
                        self._weight_driver.send_command({
                            "cmd": "led", "idx": led_index,
                            "r": r if on else 0,
                            "g": g if on else 0,
                            "b": b if on else 0,
                        })

                    elif pattern == LEDPattern.PULSE:
                        import math
                        phase = (tick % 60) / 60.0
                        brightness = (math.sin(phase * 2 * math.pi - math.pi / 2) + 1) / 2
                        self._weight_driver.send_command({
                            "cmd": "led", "idx": led_index,
                            "r": int(r * brightness),
                            "g": int(g * brightness),
                            "b": int(b * brightness),
                        })

            except Exception as e:
                logger.error(f"[ARDUINO LED] Animation error: {e}")

            tick += 1
            time.sleep(1.0 / 30.0)
