"""
Real LED Driver - Bar Graph + Shelf Indicators via Arduino Nano

Controls:
  - KYX-B10BGYR-4 bar graph (10 segments: 4 green, 3 yellow, 3 red)
    Used as weight progress indicator during mixing.
  - 4x Red panel-mount indicator LEDs (one per shelf slot)
    Show which slot needs attention.

LED behavior:
  - Product ON shelf    → LED OFF (all good)
  - Product REMOVED     → LED ON solid (alert)
  - Mixing guidance     → LED BLINK_SLOW (pick this one)
  - Error / wrong slot  → LED BLINK_FAST

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
import threading
from typing import Dict, Optional

from hal.interfaces import LEDDriverInterface, LEDColor, LEDPattern

logger = logging.getLogger("smartlocker.sensor")

# Blink thread tick interval (100ms)
_TICK_S = 0.10

# Blink rates (in ticks)
_BLINK_SLOW_TICKS = 5   # 500ms on / 500ms off = 1 Hz
_BLINK_FAST_TICKS = 2   # 200ms on / 200ms off = 2.5 Hz

# Minimum interval between serial commands for bar graph
_BAR_THROTTLE_S = 0.15


class RealLEDDriverArduino(LEDDriverInterface):
    """
    LED driver for bar graph + shelf indicators via Arduino serial bridge.

    Shelf LEDs are single-color RED. Blink patterns are handled by a
    software background thread that toggles Arduino GPIO pins.

    Thread-safe: set_slot/clear_slot can be called from any thread.
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

        # Slot configuration: slot_id -> (on: bool, pattern: LEDPattern)
        self._slot_config: Dict[str, tuple] = {}
        self._config_lock = threading.Lock()

        # Blink thread state
        self._blink_thread: Optional[threading.Thread] = None
        self._blink_running = False
        self._hw_state: Dict[int, bool] = {}  # led_index -> currently on?

        # Bar graph throttle
        self._last_bar_time = 0.0

    def set_weight_driver(self, weight_driver) -> None:
        """Inject the weight driver that owns the Arduino serial connection."""
        self._weight_driver = weight_driver

    def initialize(self) -> bool:
        """Initialize LED driver and start blink thread."""
        if self._weight_driver is None:
            logger.warning("[ARDUINO LED] No weight driver set.")
            return False

        # Test: turn everything off
        resp = self._weight_driver.send_command({"cmd": "led_off"})
        if resp and "ok" in resp:
            logger.info("[ARDUINO LED] Connected — bar graph + 4 shelf LEDs")
            self._initialized = True
            self._start_blink_thread()
            return True
        else:
            logger.warning("[ARDUINO LED] No response from Arduino — LED init FAILED")
            self._initialized = False
            return False

    # ============================================================
    # BLINK ANIMATION THREAD
    # ============================================================

    def _start_blink_thread(self):
        """Start background thread for blink patterns."""
        if self._blink_thread and self._blink_thread.is_alive():
            return
        self._blink_running = True
        self._blink_thread = threading.Thread(
            target=self._blink_loop, name="led-blink", daemon=True
        )
        self._blink_thread.start()
        logger.info("[ARDUINO LED] Blink thread started")

    def _blink_loop(self):
        """Background loop: handle blink patterns by toggling Arduino GPIOs."""
        tick = 0
        while self._blink_running:
            time.sleep(_TICK_S)
            tick += 1

            with self._config_lock:
                configs = list(self._slot_config.items())

            for slot_id, (on, pattern) in configs:
                led_index = self._slot_map.get(slot_id)
                if led_index is None:
                    continue

                if not on:
                    # Should be OFF
                    if self._hw_state.get(led_index, False):
                        self._send_hw(led_index, False)
                    continue

                if pattern == LEDPattern.SOLID:
                    # Ensure it's ON (send once)
                    if not self._hw_state.get(led_index, False):
                        self._send_hw(led_index, True)

                elif pattern == LEDPattern.BLINK_SLOW:
                    if tick % _BLINK_SLOW_TICKS == 0:
                        current = self._hw_state.get(led_index, False)
                        self._send_hw(led_index, not current)

                elif pattern == LEDPattern.BLINK_FAST:
                    if tick % _BLINK_FAST_TICKS == 0:
                        current = self._hw_state.get(led_index, False)
                        self._send_hw(led_index, not current)

                elif pattern == LEDPattern.PULSE:
                    # Pulse = blink slow for simple hardware
                    if tick % _BLINK_SLOW_TICKS == 0:
                        current = self._hw_state.get(led_index, False)
                        self._send_hw(led_index, not current)

    def _send_hw(self, led_index: int, on: bool):
        """Send a single slot command to Arduino. Updates hw_state."""
        self._hw_state[led_index] = on
        if self._weight_driver:
            try:
                self._weight_driver.send_command({
                    "cmd": "slot", "idx": led_index, "on": 1 if on else 0,
                })
            except Exception:
                pass  # Don't crash blink thread on serial error

    # ============================================================
    # SHELF SLOT LEDs (required by LEDDriverInterface)
    # ============================================================

    def set_slot(self, slot_id: str, color: LEDColor,
                 pattern: LEDPattern = LEDPattern.SOLID) -> None:
        """Set a shelf slot LED state.

        Since LEDs are single-color RED, color just maps to on/off.
        Pattern (SOLID, BLINK_SLOW, BLINK_FAST) is handled by the blink thread.
        Thread-safe.
        """
        if not self._initialized:
            return

        if slot_id not in self._slot_map:
            return

        on = color != LEDColor.OFF

        with self._config_lock:
            self._slot_config[slot_id] = (on, pattern)

    def clear_slot(self, slot_id: str) -> None:
        """Turn off a shelf slot LED."""
        if slot_id not in self._slot_map:
            return

        with self._config_lock:
            self._slot_config[slot_id] = (False, LEDPattern.SOLID)

        # Immediately send off (don't wait for blink thread tick)
        led_index = self._slot_map.get(slot_id)
        if led_index is not None:
            self._send_hw(led_index, False)

    def clear_all(self) -> None:
        """Turn off all LEDs (bar + slots)."""
        with self._config_lock:
            self._slot_config.clear()
        self._hw_state.clear()
        if self._weight_driver:
            self._weight_driver.send_command({"cmd": "led_off"})

    def shutdown(self) -> None:
        """Stop blink thread and turn off all LEDs."""
        self._blink_running = False
        if self._blink_thread and self._blink_thread.is_alive():
            self._blink_thread.join(timeout=2.0)
        self.clear_all()
        self._initialized = False
        logger.info("[ARDUINO LED] Shutdown")

    # ============================================================
    # BAR GRAPH - Weight progress indicator
    # ============================================================

    def set_balance_bar(self, percentage: float) -> None:
        """Set the bar graph to show weight progress during mixing."""
        if not self._weight_driver:
            return

        pct = max(0, min(int(percentage), 100))

        # Throttle bar updates
        now = time.monotonic()
        if (now - self._last_bar_time) < _BAR_THROTTLE_S:
            return
        self._last_bar_time = now

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
    # CONVENIENCE METHODS
    # ============================================================

    def set_slot_stock_level(self, slot_id: str, percentage: float) -> None:
        """Turn shelf LED on/off based on stock level.
        LED ON = stock below 20% (warning!)
        LED OFF = stock OK
        """
        if percentage <= 0:
            self.clear_slot(slot_id)
        elif percentage < 20:
            self.set_slot(slot_id, LEDColor.RED, LEDPattern.SOLID)
        else:
            self.clear_slot(slot_id)

    def set_all_slots_off(self) -> None:
        """Turn off all shelf LEDs."""
        with self._config_lock:
            self._slot_config.clear()
        self._hw_state.clear()
        if self._weight_driver:
            self._weight_driver.send_command({"cmd": "slot_all", "on": 0})
