"""
Real LED Driver — Individual Red LEDs via RPi GPIO

Simple GPIO-driven red LEDs, one per shelf slot.
Each LED is wired: GPIO pin → 150Ω resistor → LED(+) → LED(−) → GND.

LEDs are single-color (red), so the LEDColor parameter controls ON/OFF only:
  - Any color except OFF → LED ON
  - LEDColor.OFF → LED OFF

Blink patterns (BLINK_SLOW, BLINK_FAST, PULSE) are handled by a background
thread toggling the GPIO pins at the appropriate frequency.

GPIO assignments (all free on RPi 5):
  Slot 1 → GPIO 17  (pin 11)
  Slot 2 → GPIO 27  (pin 13)
  Slot 3 → GPIO 22  (pin 15)
  Slot 4 → GPIO 25  (pin 22)
  Slot 5 → GPIO 12  (pin 32)
  Slot 6 → GPIO 16  (pin 36)

Configurable via settings.py LED_GPIO_SLOT_PINS dict.
"""

import time
import logging
import threading
from typing import Dict, Optional, Tuple

from hal.interfaces import LEDDriverInterface, LEDColor, LEDPattern

logger = logging.getLogger("smartlocker.sensor")

# Default GPIO pin assignments per slot (BCM numbering)
DEFAULT_SLOT_PINS: Dict[str, int] = {
    "shelf1_slot1": 17,
    "shelf1_slot2": 27,
    "shelf1_slot3": 22,
    "shelf1_slot4": 25,
    "shelf1_slot5": 12,
    "shelf1_slot6": 16,
}

# Blink timing (seconds)
_BLINK_SLOW_PERIOD = 1.0     # 1 Hz (0.5s on, 0.5s off)
_BLINK_FAST_PERIOD = 0.33    # ~3 Hz
_ANIM_TICK = 0.05            # 50ms animation resolution


class RealLEDDriverGPIO(LEDDriverInterface):
    """
    Direct GPIO LED driver for individual red indicator LEDs.

    Each slot has one red LED connected to a GPIO pin via a 150Ω resistor.
    The driver supports SOLID, BLINK_SLOW, and BLINK_FAST patterns via a
    background thread.
    """

    def __init__(self, slot_pins: Optional[Dict[str, int]] = None):
        self._slot_pins: Dict[str, int] = slot_pins or {}
        self._chip = None  # lgpio chip handle
        self._initialized = False

        # Active slot states: slot_id → (on: bool, pattern: LEDPattern)
        self._states: Dict[str, Tuple[bool, LEDPattern]] = {}

        # Animation thread
        self._anim_thread: Optional[threading.Thread] = None
        self._anim_running = False
        self._lock = threading.Lock()

    def initialize(self) -> bool:
        """Open GPIO chip and configure all slot pins as outputs."""
        # Load pin config from settings if not provided
        if not self._slot_pins:
            try:
                from config.settings import LED_GPIO_SLOT_PINS
                self._slot_pins = dict(LED_GPIO_SLOT_PINS)
            except (ImportError, AttributeError):
                self._slot_pins = dict(DEFAULT_SLOT_PINS)

        try:
            import lgpio
            self._lgpio = lgpio
        except ImportError:
            logger.error("[GPIO LED] lgpio not installed — pip install lgpio")
            return False

        try:
            self._chip = lgpio.gpiochip_open(0)
        except Exception as e:
            logger.error(f"[GPIO LED] Failed to open GPIO chip: {e}")
            return False

        # Configure each pin as output, initially LOW (off)
        ok_count = 0
        for slot_id, pin in self._slot_pins.items():
            try:
                lgpio.gpio_claim_output(self._chip, pin, 0)
                ok_count += 1
            except Exception as e:
                logger.warning(f"[GPIO LED] Failed to claim GPIO {pin} for {slot_id}: {e}")

        if ok_count == 0:
            logger.error("[GPIO LED] No GPIO pins claimed — init FAILED")
            return False

        # Start animation thread for blink patterns
        self._anim_running = True
        self._anim_thread = threading.Thread(
            target=self._animation_loop, daemon=True, name="led-gpio-anim"
        )
        self._anim_thread.start()

        self._initialized = True
        logger.info(
            f"[GPIO LED] Initialized — {ok_count} slot LEDs on GPIO "
            f"{list(self._slot_pins.values())[:ok_count]}"
        )
        return True

    # ================================================================
    # LEDDriverInterface
    # ================================================================

    def set_slot(self, slot_id: str, color: LEDColor,
                 pattern: LEDPattern = LEDPattern.SOLID) -> None:
        """Turn on/off a slot LED. Color is ignored (LEDs are red) — any color = ON."""
        if not self._initialized:
            return

        pin = self._slot_pins.get(slot_id)
        if pin is None:
            return  # Unknown slot — silently ignore

        on = color != LEDColor.OFF

        with self._lock:
            if on:
                self._states[slot_id] = (True, pattern)
                # For SOLID, set immediately
                if pattern == LEDPattern.SOLID:
                    self._gpio_write(pin, 1)
            else:
                self._states.pop(slot_id, None)
                self._gpio_write(pin, 0)

    def clear_slot(self, slot_id: str) -> None:
        """Turn off a specific slot LED."""
        self.set_slot(slot_id, LEDColor.OFF)

    def clear_all(self) -> None:
        """Turn off all slot LEDs."""
        with self._lock:
            self._states.clear()
            for slot_id, pin in self._slot_pins.items():
                self._gpio_write(pin, 0)

    def shutdown(self) -> None:
        """Turn off all LEDs and release GPIO resources."""
        self._anim_running = False
        if self._anim_thread and self._anim_thread.is_alive():
            self._anim_thread.join(timeout=1.0)

        self.clear_all()

        if self._chip is not None:
            try:
                # Free all claimed pins
                for pin in self._slot_pins.values():
                    try:
                        self._lgpio.gpio_free(self._chip, pin)
                    except Exception:
                        pass
                self._lgpio.gpiochip_close(self._chip)
            except Exception:
                pass
            self._chip = None

        self._initialized = False
        logger.info("[GPIO LED] Shutdown")

    # ================================================================
    # Animation thread — handles BLINK patterns
    # ================================================================

    def _animation_loop(self):
        """Background thread that toggles blinking LEDs."""
        tick = 0
        while self._anim_running:
            time.sleep(_ANIM_TICK)
            tick += 1

            with self._lock:
                for slot_id, (on, pattern) in list(self._states.items()):
                    if not on:
                        continue

                    pin = self._slot_pins.get(slot_id)
                    if pin is None:
                        continue

                    if pattern == LEDPattern.SOLID:
                        # Already set, nothing to animate
                        continue

                    elif pattern == LEDPattern.BLINK_SLOW:
                        # Toggle every 0.5s = 10 ticks at 50ms
                        period_ticks = int(_BLINK_SLOW_PERIOD / _ANIM_TICK)
                        half = period_ticks // 2
                        state = 1 if (tick % period_ticks) < half else 0
                        self._gpio_write(pin, state)

                    elif pattern == LEDPattern.BLINK_FAST:
                        # Toggle every ~0.165s ≈ 3.3 ticks at 50ms
                        period_ticks = max(2, int(_BLINK_FAST_PERIOD / _ANIM_TICK))
                        half = period_ticks // 2
                        state = 1 if (tick % period_ticks) < half else 0
                        self._gpio_write(pin, state)

                    elif pattern == LEDPattern.PULSE:
                        # Pulse → treat as blink_slow for single-color LEDs
                        period_ticks = int(_BLINK_SLOW_PERIOD / _ANIM_TICK)
                        half = period_ticks // 2
                        state = 1 if (tick % period_ticks) < half else 0
                        self._gpio_write(pin, state)

    # ================================================================
    # Internal helpers
    # ================================================================

    def _gpio_write(self, pin: int, value: int) -> None:
        """Write a GPIO pin value (0 or 1). Suppresses errors."""
        if self._chip is None:
            return
        try:
            self._lgpio.gpio_write(self._chip, pin, value)
        except Exception:
            pass

    # ================================================================
    # Convenience (match Arduino driver extras, optional)
    # ================================================================

    def get_slot_pins(self) -> Dict[str, int]:
        """Return the current slot→GPIO pin mapping."""
        return dict(self._slot_pins)

    def get_state(self, slot_id: str) -> Optional[Tuple[bool, str]]:
        """Return (on, pattern_name) for a slot, or None."""
        st = self._states.get(slot_id)
        if st:
            return (st[0], st[1].value)
        return None
