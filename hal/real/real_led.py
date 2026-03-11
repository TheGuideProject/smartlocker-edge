"""
Real LED Driver - WS2812B (NeoPixel) LED Strip

Controls a WS2812B addressable LED strip connected to the Raspberry Pi.
Each LED corresponds to a shelf slot and shows status colors/patterns.

Hardware setup:
  - WS2812B data line connected to a PWM-capable GPIO pin (default: GPIO 18)
  - Power: 5V supply (do NOT power many LEDs from RPi 5V pin alone)
  - Optional: level shifter from RPi 3.3V logic to 5V data line

Required library (install on RPi):
  sudo pip install rpi_ws281x

Alternative library:
  pip install adafruit-circuitpython-neopixel
  (also needs: pip install adafruit-blinka)

NOTE: rpi_ws281x requires root access (sudo) for PWM/DMA control.

Graceful fallback: if rpi_ws281x is not installed (e.g., on Windows or a dev
machine), all methods log warnings and return safely without crashing.
"""

import logging
import threading
import time
from typing import Dict, Tuple, Optional

from hal.interfaces import LEDDriverInterface, LEDColor, LEDPattern

logger = logging.getLogger("smartlocker.sensor")

# ---------- Graceful import with fallback ----------
try:
    from rpi_ws281x import PixelStrip, Color
    HAS_WS281X = True
except ImportError:
    HAS_WS281X = False
    PixelStrip = None  # type: ignore[assignment, misc]
    Color = None  # type: ignore[assignment, misc]
    logger.warning(
        "[REAL LED] rpi_ws281x library not installed. "
        "LED strip will be non-functional. Install with: sudo pip install rpi_ws281x"
    )


class RealLEDDriver(LEDDriverInterface):
    """
    Real WS2812B LED strip driver using rpi_ws281x.

    Maps logical slot IDs (e.g., "shelf1_slot1") to physical LED indices
    on the strip. Supports solid colors and blinking patterns.
    """

    def __init__(self):
        from config.settings import LED_COUNT, LED_GPIO_PIN, LED_BRIGHTNESS
        self._led_count = LED_COUNT
        self._gpio_pin = LED_GPIO_PIN
        self._brightness = LED_BRIGHTNESS
        self._strip = None
        self._initialized = False

        # Map slot IDs to LED indices (customize for your physical setup)
        self._slot_map: Dict[str, int] = {
            "shelf1_slot1": 0,
            "shelf1_slot2": 1,
            "shelf1_slot3": 2,
            "shelf1_slot4": 3,
        }

        # Track current state for pattern animation
        self._state: Dict[str, Tuple[LEDColor, LEDPattern]] = {}

        # Pattern animation thread
        self._animation_thread: Optional[threading.Thread] = None
        self._animation_running = False

    def initialize(self) -> bool:
        """
        Initialize the WS2812B LED strip via rpi_ws281x.
        Returns True if the strip is initialized, False on error.
        If the library is not installed, returns False and logs a warning.
        """
        if not HAS_WS281X:
            logger.warning(
                "[REAL LED] Cannot initialize: rpi_ws281x library not available. "
                "All LED operations will be no-ops."
            )
            self._initialized = False
            return False

        try:
            self._strip = PixelStrip(
                num=self._led_count,
                pin=self._gpio_pin,
                freq_hz=800000,      # LED signal frequency (800kHz for WS2812B)
                dma=10,              # DMA channel (10 avoids conflicts)
                invert=False,        # True if using NPN transistor level shift
                brightness=self._brightness,
                channel=0,           # PWM channel (0 for GPIO 18, 1 for GPIO 13)
            )
            self._strip.begin()

            # Turn all LEDs off initially
            for i in range(self._led_count):
                self._strip.setPixelColor(i, Color(0, 0, 0))
            self._strip.show()

            # Start the animation thread for blink/pulse patterns
            self._animation_running = True
            self._animation_thread = threading.Thread(
                target=self._animation_loop,
                daemon=True,
            )
            self._animation_thread.start()

            self._initialized = True
            logger.info(
                f"[REAL LED] WS2812B strip initialized: "
                f"{self._led_count} LEDs on GPIO {self._gpio_pin}"
            )
            return True

        except Exception as e:
            logger.error(f"[REAL LED] Failed to initialize LED strip: {e}")
            self._initialized = False
            return False

    def set_slot(self, slot_id: str, color: LEDColor,
                 pattern: LEDPattern = LEDPattern.SOLID) -> None:
        """
        Set color and pattern for a specific slot's LED.
        Maps the slot_id to a physical LED index and sets the color.
        """
        if not self._initialized or not HAS_WS281X:
            if not HAS_WS281X:
                logger.warning(f"[REAL LED] No-op set_slot('{slot_id}'): library not available")
            return

        self._state[slot_id] = (color, pattern)

        led_index = self._slot_map.get(slot_id)
        if led_index is None:
            logger.warning(f"[REAL LED] Unknown slot '{slot_id}', no LED mapping")
            return

        try:
            r, g, b = color.value
            if pattern == LEDPattern.SOLID:
                self._strip.setPixelColor(led_index, Color(r, g, b))
                self._strip.show()
            # For blink/pulse patterns, the animation thread handles updates
            logger.info(f"[REAL LED] {slot_id} (LED {led_index}) -> {color.name} ({pattern.value})")

        except Exception as e:
            logger.error(f"[REAL LED] Error setting slot '{slot_id}': {e}")

    def clear_slot(self, slot_id: str) -> None:
        """Turn off the LED for a specific slot."""
        self._state.pop(slot_id, None)
        self.set_slot(slot_id, LEDColor.OFF, LEDPattern.SOLID)

    def clear_all(self) -> None:
        """Turn off all LEDs on the strip."""
        self._state.clear()

        if not self._initialized or not HAS_WS281X:
            if not HAS_WS281X:
                logger.warning("[REAL LED] No-op clear_all(): library not available")
            return

        try:
            for i in range(self._led_count):
                self._strip.setPixelColor(i, Color(0, 0, 0))
            self._strip.show()
            logger.info("[REAL LED] All LEDs cleared")

        except Exception as e:
            logger.error(f"[REAL LED] Error clearing LEDs: {e}")

    def shutdown(self) -> None:
        """Turn off all LEDs and release hardware."""
        self._animation_running = False
        if self._animation_thread and self._animation_thread.is_alive():
            self._animation_thread.join(timeout=2.0)

        self.clear_all()
        self._strip = None
        self._initialized = False
        logger.info("[REAL LED] Shutdown")

    # ---- INTERNAL: Animation loop for blink/pulse patterns ----

    def _animation_loop(self) -> None:
        """
        Background thread that updates LEDs for non-SOLID patterns.
        Runs at ~30 Hz and toggles LEDs for BLINK_SLOW, BLINK_FAST,
        and smoothly fades for PULSE.
        """
        tick = 0
        while self._animation_running:
            try:
                needs_show = False
                for slot_id, (color, pattern) in list(self._state.items()):
                    led_index = self._slot_map.get(slot_id)
                    if led_index is None:
                        continue

                    r, g, b = color.value

                    if pattern == LEDPattern.BLINK_SLOW:
                        # ~1 Hz: toggle every 15 ticks at 30 Hz
                        on = (tick % 30) < 15
                        if on:
                            self._strip.setPixelColor(led_index, Color(r, g, b))
                        else:
                            self._strip.setPixelColor(led_index, Color(0, 0, 0))
                        needs_show = True

                    elif pattern == LEDPattern.BLINK_FAST:
                        # ~3 Hz: toggle every 5 ticks at 30 Hz
                        on = (tick % 10) < 5
                        if on:
                            self._strip.setPixelColor(led_index, Color(r, g, b))
                        else:
                            self._strip.setPixelColor(led_index, Color(0, 0, 0))
                        needs_show = True

                    elif pattern == LEDPattern.PULSE:
                        # Smooth sine-wave fade over ~2 seconds (60 ticks)
                        import math
                        phase = (tick % 60) / 60.0
                        brightness = (math.sin(phase * 2 * math.pi - math.pi / 2) + 1) / 2
                        pr = int(r * brightness)
                        pg = int(g * brightness)
                        pb = int(b * brightness)
                        self._strip.setPixelColor(led_index, Color(pr, pg, pb))
                        needs_show = True

                    # SOLID is handled in set_slot directly, no animation needed

                if needs_show and self._strip is not None:
                    self._strip.show()

            except Exception as e:
                logger.error(f"[REAL LED] Animation loop error: {e}")

            tick += 1
            time.sleep(1.0 / 30.0)  # ~30 Hz
