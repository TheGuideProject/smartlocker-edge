"""
Real LED Driver - Bar Graph + Shelf Indicators via Arduino Nano

Controls:
  - KYX-B10BGYR-4 bar graph (10 segments: 4 green, 3 yellow, 3 red)
    Used as weight progress indicator during mixing.
  - 4x Red panel-mount indicator LEDs (one per shelf slot)
    Show which slot is active or has low stock.

Shares the serial connection with the Arduino weight driver.

Commands sent to Arduino:
  {"cmd":"bar","pct":75}          // fill bar to 75%
  {"cmd":"bar","seg":7}           // light first 7 segments
  {"cmd":"bar_off"}               // bar all off
  {"cmd":"slot","idx":0,"on":1}   // shelf LED 0 on
  {"cmd":"slot","idx":2,"on":0}   // shelf LED 2 off
  {"cmd":"slot_all","on":0}       // all shelf LEDs off
  {"cmd":"led_off"}               // everything off
"""

import time
import logging
from typing import Dict, Optional

from hal.interfaces import LEDDriverInterface, LEDColor, LEDPattern

logger = logging.getLogger("smartlocker.sensor")

# Minimum interval between serial commands per slot (seconds).
# Prevents UI button spam from flooding Arduino serial buffer.
_THROTTLE_S = 0.10


class RealLEDDriverArduino(LEDDriverInterface):
    """
    LED driver for bar graph + shelf indicators via Arduino serial bridge.

    The bar graph has fixed colors per segment (green/yellow/red),
    so LEDColor is mapped to on/off behavior. The shelf LEDs are
    single-color (red) and simply toggle on/off.

    Includes per-slot throttle (100ms) to prevent serial flood when
    buttons are tapped rapidly on the touchscreen.
    """

    def __init__(self):
        self._weight_driver = None
        self._initialized = False

        # Map slot IDs to physical LED indices (0-3)
        self._slot_map: Dict[str, int] = {
            "shelf1_slot1": 0,
            "shelf1_slot2": 1,
            "shelf1_slot3": 2,
            "shelf1_slot4": 3,
        }

        # Track slot states for blink animation
        self._slot_states: Dict[str, bool] = {}

        # Per-slot throttle timestamps
        self._last_cmd: Dict[str, float] = {}

    def set_weight_driver(self, weight_driver) -> None:
        """Inject the weight driver that owns the Arduino serial connection."""
        self._weight_driver = weight_driver

    def initialize(self) -> bool:
        """Initialize LED driver."""
        if self._weight_driver is None:
            logger.warning("[ARDUINO LED] No weight driver set.")
            return False

        # Test: turn everything off
        resp = self._weight_driver.send_command({"cmd": "led_off"})
        if resp and "ok" in resp:
            logger.info("[ARDUINO LED] Connected — bar graph + 4 shelf LEDs")
            self._initialized = True
            return True
        else:
            logger.warning("[ARDUINO LED] No response from Arduino — LED init FAILED")
            self._initialized = False
            return False

    # ============================================================
    # SHELF SLOT LEDs (required by LEDDriverInterface)
    # ============================================================

    def set_slot(self, slot_id: str, color: LEDColor,
                 pattern: LEDPattern = LEDPattern.SOLID) -> None:
        """Turn on/off a shelf slot LED. Color is ignored (LEDs are red).

        Throttled: commands for the same slot within 100ms are silently dropped
        to prevent serial buffer overflow from rapid UI taps.
        """
        if not self._initialized or not self._weight_driver:
            return

        led_index = self._slot_map.get(slot_id)
        if led_index is None:
            return  # unknown slot — silently ignore

        # LED is ON for any color except OFF
        on = 1 if color != LEDColor.OFF else 0

        # Throttle: skip if same slot was commanded less than 100ms ago
        now = time.monotonic()
        last = self._last_cmd.get(slot_id, 0.0)
        if (now - last) < _THROTTLE_S:
            return
        self._last_cmd[slot_id] = now

        self._slot_states[slot_id] = bool(on)

        self._weight_driver.send_command({
            "cmd": "slot", "idx": led_index, "on": on,
        })

    def clear_slot(self, slot_id: str) -> None:
        """Turn off a shelf slot LED."""
        self._slot_states.pop(slot_id, None)
        led_index = self._slot_map.get(slot_id)
        if led_index is not None and self._weight_driver:
            self._weight_driver.send_command({
                "cmd": "slot", "idx": led_index, "on": 0,
            })

    def clear_all(self) -> None:
        """Turn off all LEDs (bar + slots)."""
        self._slot_states.clear()
        if self._weight_driver:
            self._weight_driver.send_command({"cmd": "led_off"})

    def shutdown(self) -> None:
        """Turn off all LEDs."""
        self.clear_all()
        self._initialized = False
        logger.info("[ARDUINO LED] Shutdown")

    # ============================================================
    # BAR GRAPH - Weight progress indicator
    # ============================================================

    def set_balance_bar(self, percentage: float) -> None:
        """
        Set the bar graph to show weight progress during mixing.

        The bar has built-in colors:
          seg 0-3  = GREEN  (0-40%)
          seg 4-6  = YELLOW (40-70%)
          seg 7-9  = RED    (70-100%)

        Args:
            percentage: 0-100 (clamped)
        """
        if not self._weight_driver:
            return

        pct = max(0, min(int(percentage), 100))

        # Throttle bar updates (300ms refresh from mixing screen)
        now = time.monotonic()
        if (now - self._last_cmd.get("_bar", 0.0)) < _THROTTLE_S:
            return
        self._last_cmd["_bar"] = now

        self._weight_driver.send_command({"cmd": "bar", "pct": pct})

    def set_balance_segments(self, count: int) -> None:
        """Set exact number of bar segments lit (0-10)."""
        if not self._weight_driver:
            return

        seg = max(0, min(count, 10))
        self._weight_driver.send_command({"cmd": "bar", "seg": seg})

    def clear_balance_bar(self) -> None:
        """Turn off the bar graph."""
        if self._weight_driver:
            self._weight_driver.send_command({"cmd": "bar_off"})

    # ============================================================
    # SHELF STOCK INDICATORS (convenience methods)
    # ============================================================

    def set_slot_stock_level(self, slot_id: str, percentage: float) -> None:
        """
        Turn shelf LED on/off based on stock level.
        LED ON = stock below 20% (warning!)
        LED OFF = stock OK
        """
        if percentage <= 0:
            self.clear_slot(slot_id)
        elif percentage < 20:
            # Low stock: LED ON (blinking would need a timer, keep simple)
            self.set_slot(slot_id, LEDColor.RED, LEDPattern.SOLID)
        else:
            # Stock OK: LED OFF
            self.clear_slot(slot_id)

    def set_all_slots_off(self) -> None:
        """Turn off all shelf LEDs."""
        self._slot_states.clear()
        if self._weight_driver:
            self._weight_driver.send_command({"cmd": "slot_all", "on": 0})
