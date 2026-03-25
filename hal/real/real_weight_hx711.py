"""
Real Weight Driver - HX711 Load Cell Amplifier Direct GPIO

Reads HX711 ADC directly from Raspberry Pi GPIO pins (no Arduino needed).
Supports multiple channels via separate HX711 modules.

Hardware:
  - HX711 VCC → 3.3V, GND → GND
  - HX711 DT (DOUT) → configurable GPIO (default: GPIO 5)
  - HX711 SCK (CLK) → configurable GPIO (default: GPIO 6)

Calibration:
  offset = raw reading at zero load (tare value)
  scale  = raw units per gram (calculated from known weight)

Graceful fallback on Windows/non-RPi.
"""

import logging
import time
import threading
from typing import List, Dict, Optional

from hal.interfaces import WeightDriverInterface, WeightReading

logger = logging.getLogger("smartlocker.sensor")

try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except ImportError:
    HAS_GPIO = False
    GPIO = None
    logger.warning("[HX711] RPi.GPIO not available. Weight driver non-functional.")


class HX711Channel:
    """Single HX711 channel with calibration."""

    def __init__(self, name: str, dt_pin: int, sck_pin: int):
        self.name = name
        self.dt_pin = dt_pin
        self.sck_pin = sck_pin
        self.offset = 0       # Raw value at zero load
        self.scale = 23.45    # Raw units per gram (calibrated 2026-03-25)
        self.inverted = True  # True = raw values DECREASE with weight
        self._last_raw = 0
        self._last_grams = 0.0
        self._readings_buffer = []
        self._stable = False

    def setup_gpio(self):
        GPIO.setup(self.sck_pin, GPIO.OUT)
        GPIO.setup(self.dt_pin, GPIO.IN)
        GPIO.output(self.sck_pin, False)

    def read_raw(self) -> Optional[int]:
        """Read raw 24-bit value from HX711."""
        if not HAS_GPIO:
            return None

        try:
            # Wait for HX711 to be ready (DT goes LOW)
            timeout = time.time() + 2.0
            while GPIO.input(self.dt_pin):
                if time.time() > timeout:
                    logger.warning(f"[HX711] Timeout waiting for {self.name}")
                    return None

            # Read 24 bits
            count = 0
            for _ in range(24):
                GPIO.output(self.sck_pin, True)
                count = count << 1
                GPIO.output(self.sck_pin, False)
                if GPIO.input(self.dt_pin):
                    count += 1

            # 25th pulse for gain 128 on channel A
            GPIO.output(self.sck_pin, True)
            GPIO.output(self.sck_pin, False)

            # Convert to signed
            if count & 0x800000:
                count -= 0x1000000

            self._last_raw = count
            return count

        except Exception as e:
            logger.error(f"[HX711] Read error on {self.name}: {e}")
            return None

    def read_averaged(self, samples: int = 5) -> Optional[int]:
        """Read multiple samples and return average."""
        values = []
        for _ in range(samples):
            val = self.read_raw()
            if val is not None:
                values.append(val)
            time.sleep(0.05)

        if not values:
            return None

        # Remove outliers (drop min and max if enough samples)
        if len(values) >= 4:
            values.sort()
            values = values[1:-1]

        return int(sum(values) / len(values))

    def read_grams(self, samples: int = 3) -> float:
        """Read weight in grams using calibration."""
        raw = self.read_averaged(samples)
        if raw is None:
            return self._last_grams

        if self.inverted:
            grams = (self.offset - raw) / self.scale if self.scale != 0 else 0.0
        else:
            grams = (raw - self.offset) / self.scale if self.scale != 0 else 0.0
        grams = max(0.0, grams)

        # Check stability
        self._readings_buffer.append(grams)
        if len(self._readings_buffer) > 10:
            self._readings_buffer = self._readings_buffer[-10:]

        if len(self._readings_buffer) >= 3:
            recent = self._readings_buffer[-3:]
            spread = max(recent) - min(recent)
            self._stable = spread < 10  # Stable if within 10g
        else:
            self._stable = False

        self._last_grams = grams
        return grams

    def tare(self, samples: int = 10) -> bool:
        """Set current weight as zero reference."""
        raw = self.read_averaged(samples)
        if raw is not None:
            self.offset = raw
            self._readings_buffer.clear()
            self._last_grams = 0.0
            logger.info(f"[HX711] Tared {self.name}: offset={self.offset}")
            return True
        return False


class RealWeightDriverHX711(WeightDriverInterface):
    """
    Direct HX711 weight driver — reads load cells via RPi GPIO.
    No Arduino needed.
    """

    def __init__(self):
        # Default: single channel for shelf1
        self._channels: Dict[str, HX711Channel] = {}
        self._initialized = False
        self._lock = threading.Lock()

    def initialize(self) -> bool:
        if not HAS_GPIO:
            logger.warning("[HX711] Cannot initialize: RPi.GPIO not available.")
            return False

        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            # Default channel configuration
            # shelf1: DT=GPIO5, SCK=GPIO6
            self._channels = {
                "shelf1": HX711Channel("shelf1", dt_pin=5, sck_pin=6),
                "mixing_scale": HX711Channel("mixing_scale", dt_pin=5, sck_pin=6),
            }

            for ch in self._channels.values():
                ch.setup_gpio()

            # Auto-tare on startup
            time.sleep(0.5)
            for ch in self._channels.values():
                ch.tare(samples=10)

            self._initialized = True
            logger.info(f"[HX711] Initialized {len(self._channels)} channels: {list(self._channels.keys())}")
            return True

        except Exception as e:
            logger.error(f"[HX711] Init failed: {e}")
            self._initialized = False
            return False

    def read_weight(self, channel: str) -> WeightReading:
        if not self._initialized:
            return WeightReading(grams=0.0, channel=channel, stable=False)

        ch = self._channels.get(channel)
        if not ch:
            return WeightReading(grams=0.0, channel=channel, stable=False)

        with self._lock:
            grams = ch.read_grams(samples=3)

        return WeightReading(
            grams=round(grams, 1),
            channel=channel,
            stable=ch._stable,
            raw_value=ch._last_raw,
            timestamp=time.time(),
        )

    def tare(self, channel: str) -> bool:
        if not self._initialized:
            return False

        ch = self._channels.get(channel)
        if not ch:
            return False

        with self._lock:
            return ch.tare(samples=10)

    def get_channels(self) -> List[str]:
        return list(self._channels.keys())

    def is_healthy(self) -> bool:
        if not self._initialized or not HAS_GPIO:
            return False
        # Quick check: can we read a value?
        for ch in self._channels.values():
            raw = ch.read_raw()
            if raw is None:
                return False
        return True

    def shutdown(self) -> None:
        self._initialized = False
        if HAS_GPIO:
            try:
                GPIO.cleanup()
            except Exception:
                pass
        logger.info("[HX711] Shutdown")
