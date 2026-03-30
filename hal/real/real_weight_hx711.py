"""
Real Weight Driver - HX711 Load Cell Amplifier Direct GPIO

Reads HX711 ADC directly from Raspberry Pi GPIO pins (no Arduino needed).
Supports multiple channels via separate HX711 modules.
Uses lgpio directly for RPi5 + Python 3.13 compatibility.

IMPORTANT: GPIO bit-banging runs in a dedicated background thread
to avoid timing issues with the Qt event loop. The main thread
only reads cached values.

Hardware:
  - HX711 VCC -> 3.3V, GND -> GND
  - Shelf:  DT=GPIO5,  SCK=GPIO6
  - Mixing: DT=GPIO23, SCK=GPIO24

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
    import lgpio
    HAS_GPIO = True
except ImportError:
    HAS_GPIO = False
    lgpio = None
    logger.warning("[HX711] lgpio not available. Weight driver non-functional.")


class HX711Channel:
    """Single HX711 channel with calibration."""

    def __init__(self, name: str, dt_pin: int, sck_pin: int, gpio_handle: int = -1):
        self.name = name
        self.dt_pin = dt_pin
        self.sck_pin = sck_pin
        self._h = gpio_handle
        self.offset = 0       # Raw value at zero load
        self.scale = 9.81     # Raw units per gram (calibrated 2026-03-30)
        self.inverted = True  # True = raw values DECREASE with weight
        self._last_raw = 0
        self._last_grams = 0.0
        self._readings_buffer = []
        self._stable = False

    def setup_gpio(self):
        lgpio.gpio_claim_output(self._h, self.sck_pin, 0)
        lgpio.gpio_claim_input(self._h, self.dt_pin)

    def read_raw(self) -> Optional[int]:
        """Read raw 24-bit value from HX711."""
        if not HAS_GPIO or self._h < 0:
            return None

        try:
            # Wait for HX711 to be ready (DT goes LOW)
            timeout = time.time() + 2.0
            while lgpio.gpio_read(self._h, self.dt_pin):
                if time.time() > timeout:
                    logger.warning(f"[HX711] Timeout waiting for {self.name}")
                    return None

            # Read 24 bits
            count = 0
            for _ in range(24):
                lgpio.gpio_write(self._h, self.sck_pin, 1)
                count = count << 1
                lgpio.gpio_write(self._h, self.sck_pin, 0)
                if lgpio.gpio_read(self._h, self.dt_pin):
                    count += 1

            # 25th pulse for gain 128 on channel A
            lgpio.gpio_write(self._h, self.sck_pin, 1)
            lgpio.gpio_write(self._h, self.sck_pin, 0)

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
    Direct HX711 weight driver -- reads load cells via RPi GPIO.
    Uses lgpio for RPi5 compatibility. No Arduino needed.

    Weight reading runs in a dedicated background thread to avoid
    timing conflicts with the Qt event loop.
    """

    def __init__(self):
        self._channels: Dict[str, HX711Channel] = {}
        self._initialized = False
        self._lock = threading.Lock()
        self._gpio_handle = -1

        # Background reader thread
        self._reader_thread: Optional[threading.Thread] = None
        self._reader_running = False
        self._cached_readings: Dict[str, WeightReading] = {}
        self._tare_request: Optional[str] = None  # Channel name to tare
        self._tare_done = threading.Event()

    def initialize(self) -> bool:
        if not HAS_GPIO:
            logger.warning("[HX711] Cannot initialize: lgpio not available.")
            return False

        try:
            # Open GPIO chip (0 works on RPi5)
            self._gpio_handle = lgpio.gpiochip_open(0)

            # Channel configuration from settings
            from config import settings
            shelf_dt = getattr(settings, 'HX711_SHELF_DT', 5)
            shelf_sck = getattr(settings, 'HX711_SHELF_SCK', 6)
            mix_dt = getattr(settings, 'HX711_MIX_DT', 23)
            mix_sck = getattr(settings, 'HX711_MIX_SCK', 24)

            self._channels = {
                "shelf1": HX711Channel("shelf1", dt_pin=shelf_dt, sck_pin=shelf_sck,
                                       gpio_handle=self._gpio_handle),
                "mixing_scale": HX711Channel("mixing_scale", dt_pin=mix_dt, sck_pin=mix_sck,
                                             gpio_handle=self._gpio_handle),
            }

            # Apply calibration values (calibrated 2026-03-30 with 2kg reference)
            shelf_scale = getattr(settings, 'HX711_SHELF_SCALE', 9.81)
            mix_scale = getattr(settings, 'HX711_MIX_SCALE', 20.69)
            self._channels["shelf1"].scale = shelf_scale
            self._channels["shelf1"].inverted = True
            self._channels["mixing_scale"].scale = mix_scale
            self._channels["mixing_scale"].inverted = True

            for ch in self._channels.values():
                ch.setup_gpio()

            # Auto-tare on startup (reads current load as zero reference)
            time.sleep(0.5)
            for ch in self._channels.values():
                ch.tare(samples=10)

            # Initialize cached readings
            for name in self._channels:
                self._cached_readings[name] = WeightReading(
                    grams=0.0, channel=name, stable=False,
                    raw_value=0, timestamp=time.time(),
                )

            self._initialized = True

            # Start background reader thread
            self._reader_running = True
            self._reader_thread = threading.Thread(
                target=self._reader_loop, daemon=True, name="HX711-reader"
            )
            self._reader_thread.start()

            logger.info(f"[HX711] Initialized {len(self._channels)} channels: {list(self._channels.keys())}")
            return True

        except Exception as e:
            logger.error(f"[HX711] Init failed: {e}")
            self._initialized = False
            return False

    def _reader_loop(self):
        """Background thread: continuously reads all channels and caches results."""
        logger.info("[HX711] Background reader thread started")
        while self._reader_running:
            # Check for tare request
            tare_ch = self._tare_request
            if tare_ch:
                self._tare_request = None
                ch = self._channels.get(tare_ch)
                if ch:
                    ch.tare(samples=10)
                self._tare_done.set()

            # Read all channels
            for name, ch in self._channels.items():
                if not self._reader_running:
                    break
                try:
                    grams = ch.read_grams(samples=3)
                    self._cached_readings[name] = WeightReading(
                        grams=round(grams, 1),
                        channel=name,
                        stable=ch._stable,
                        raw_value=ch._last_raw,
                        timestamp=time.time(),
                    )
                except Exception as e:
                    logger.error(f"[HX711] Reader error on {name}: {e}")

            # Small sleep between full cycles
            time.sleep(0.1)

        logger.info("[HX711] Background reader thread stopped")

    def read_weight(self, channel: str) -> WeightReading:
        if not self._initialized:
            return WeightReading(grams=0.0, channel=channel, stable=False)

        # Return cached reading from background thread (non-blocking!)
        cached = self._cached_readings.get(channel)
        if cached:
            return cached

        return WeightReading(grams=0.0, channel=channel, stable=False)

    def tare(self, channel: str) -> bool:
        if not self._initialized:
            return False

        ch = self._channels.get(channel)
        if not ch:
            return False

        # Request tare from background thread
        self._tare_done.clear()
        self._tare_request = channel
        # Wait for background thread to complete the tare (max 5s)
        return self._tare_done.wait(timeout=5.0)

    def get_channels(self) -> List[str]:
        return list(self._channels.keys())

    def is_healthy(self) -> bool:
        if not self._initialized or not HAS_GPIO:
            return False
        # Check if we have recent readings (less than 5 seconds old)
        now = time.time()
        for name, reading in self._cached_readings.items():
            if reading.timestamp and (now - reading.timestamp) < 5.0:
                continue
            else:
                return False
        return True

    def shutdown(self) -> None:
        self._reader_running = False
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=3.0)

        self._initialized = False
        if HAS_GPIO and self._gpio_handle >= 0:
            try:
                for ch in self._channels.values():
                    try:
                        lgpio.gpio_free(self._gpio_handle, ch.dt_pin)
                        lgpio.gpio_free(self._gpio_handle, ch.sck_pin)
                    except Exception:
                        pass
                lgpio.gpiochip_close(self._gpio_handle)
            except Exception:
                pass
        logger.info("[HX711] Shutdown")
