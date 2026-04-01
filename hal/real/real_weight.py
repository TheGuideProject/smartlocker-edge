"""
Real Weight Driver - Arduino Nano HX711 Bridge via Serial

Communicates with an Arduino Nano that reads HX711 load cell amplifiers
and sends weight data as JSON lines over USB serial.

Hardware setup:
  - Arduino Nano connected to RPi via USB (appears as /dev/ttyUSB0)
  - Arduino runs smartlocker_nano.ino firmware
  - HX711 Shelf:  DT=D2, SCK=D3
  - HX711 Mix:    DT=D4, SCK=D5

Serial protocol (115200 baud, JSON lines):
  RPi -> Arduino:
    {"cmd":"read","ch":"shelf"}
    {"cmd":"read","ch":"mix"}
    {"cmd":"tare","ch":"shelf"}
    {"cmd":"tare","ch":"mix"}
    {"cmd":"tare","ch":"all"}
    {"cmd":"ping"}
    {"cmd":"cal","ch":"shelf","scale":9.81}

  Arduino -> RPi:
    {"ch":"shelf","g":1234.5,"raw":8388607,"stable":true}
    {"ch":"mix","g":567.8,"raw":4194303,"stable":false}
    {"status":"ok","fw":"1.0"}
    {"ok":"tare","ch":"shelf"}

Required library:
  pip install pyserial

Graceful fallback: if pyserial is not installed, all methods return safe defaults.
"""

import logging
import time
import json
import threading
from typing import List, Dict, Optional

from hal.interfaces import WeightDriverInterface, WeightReading

logger = logging.getLogger("smartlocker.sensor")

# ---------- Graceful import with fallback ----------
try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False
    serial = None  # type: ignore[assignment, misc]
    logger.warning(
        "[ARDUINO WEIGHT] pyserial not installed. "
        "Weight sensor will be non-functional. Install with: pip install pyserial"
    )


# Channel name mapping: internal names -> Arduino firmware names
_CH_MAP = {
    "shelf1": "shelf",
    "shelf": "shelf",
    "mixing_scale": "mix",
    "mix": "mix",
}


def _to_arduino_ch(channel: str) -> str:
    """Convert internal channel name to Arduino firmware channel name."""
    return _CH_MAP.get(channel, channel)


def _to_internal_ch(arduino_ch: str) -> str:
    """Convert Arduino firmware channel name back to internal name."""
    if arduino_ch == "shelf":
        return "shelf1"
    elif arduino_ch == "mix":
        return "mixing_scale"
    return arduino_ch


class RealWeightDriver(WeightDriverInterface):
    """
    Weight sensor driver using Arduino Nano as HX711 bridge.

    The Arduino reads two HX711 load cell amplifiers and communicates
    via USB serial with JSON messages. Supports continuous background
    reading for responsive UI updates.
    """

    def __init__(self, channels: Optional[List[str]] = None):
        from config.settings import WEIGHT_SERIAL_PORT, WEIGHT_SERIAL_BAUD
        self._port = WEIGHT_SERIAL_PORT
        self._baud = WEIGHT_SERIAL_BAUD
        self._channels = channels or ["shelf1", "mixing_scale"]
        self._serial: Optional[serial.Serial] = None  # type: ignore
        self._initialized = False
        self._lock = threading.Lock()

        # Cache of last readings per channel
        self._cached_readings: Dict[str, WeightReading] = {}

        # Background reader thread
        self._reader_thread: Optional[threading.Thread] = None
        self._reader_running = False

        # Tare request mechanism (same pattern as HX711 direct driver)
        self._tare_request: Optional[str] = None
        self._tare_done = threading.Event()
        self._tare_result = False

    def initialize(self) -> bool:
        """
        Open serial connection to the Arduino Nano.
        Auto-detects port if configured port fails.
        Sends a ping to verify communication.
        """
        if not HAS_SERIAL:
            logger.warning("[ARDUINO WEIGHT] Cannot initialize: pyserial not available.")
            self._initialized = False
            return False

        # Try configured port first, then auto-detect
        ports_to_try = [self._port]
        try:
            available = serial.tools.list_ports.comports()
            for p in available:
                # Arduino Nano typically shows as CH340 or FTDI
                if any(kw in (p.description or "").lower() for kw in ["ch340", "ftdi", "arduino", "usb serial"]):
                    if p.device not in ports_to_try:
                        ports_to_try.append(p.device)
                        logger.info(f"[ARDUINO WEIGHT] Found potential Arduino: {p.device} ({p.description})")
        except Exception:
            pass

        for port in ports_to_try:
            try:
                self._serial = serial.Serial(
                    port=port,
                    baudrate=self._baud,
                    timeout=2.0,
                )

                # Wait for Arduino to boot (resets on serial connect)
                time.sleep(2.5)
                self._serial.reset_input_buffer()

                # Ping to verify
                self._send({"cmd": "ping"})
                response = self._recv(timeout=3.0)

                if response and response.get("status") == "ok":
                    fw = response.get("fw", "?")
                    logger.info(f"[ARDUINO WEIGHT] Connected on {port} (firmware v{fw})")
                    self._port = port
                    self._initialized = True

                    # Initialize cached readings
                    for name in self._channels:
                        self._cached_readings[name] = WeightReading(
                            grams=0.0, channel=name, stable=False,
                            raw_value=0, timestamp=time.time(),
                        )

                    # Start background reader
                    self._reader_running = True
                    self._reader_thread = threading.Thread(
                        target=self._reader_loop, daemon=True,
                        name="Arduino-weight-reader",
                    )
                    self._reader_thread.start()

                    return True
                else:
                    logger.warning(f"[ARDUINO WEIGHT] No ping response on {port}")
                    self._serial.close()
                    self._serial = None

            except Exception as e:
                logger.warning(f"[ARDUINO WEIGHT] Failed on {port}: {e}")
                if self._serial:
                    try:
                        self._serial.close()
                    except Exception:
                        pass
                    self._serial = None

        logger.error("[ARDUINO WEIGHT] Could not connect to Arduino on any port")
        self._initialized = False
        return False

    def _reader_loop(self):
        """Background thread: continuously polls weight from Arduino."""
        logger.info("[ARDUINO WEIGHT] Background reader started")
        while self._reader_running:
            try:
                # Handle tare requests
                tare_ch = self._tare_request
                if tare_ch:
                    self._tare_request = None
                    arduino_ch = _to_arduino_ch(tare_ch)
                    with self._lock:
                        self._send({"cmd": "tare", "ch": arduino_ch})
                        resp = self._recv(timeout=3.0)
                    self._tare_result = resp is not None and "ok" in resp
                    if self._tare_result:
                        logger.info(f"[ARDUINO WEIGHT] Tared '{tare_ch}'")
                        self._cached_readings.pop(tare_ch, None)
                    self._tare_done.set()

                # Read all channels
                for name in self._channels:
                    if not self._reader_running:
                        break
                    arduino_ch = _to_arduino_ch(name)
                    with self._lock:
                        self._send({"cmd": "read", "ch": arduino_ch})
                        resp = self._recv(timeout=1.5)

                    if resp and "g" in resp:
                        self._cached_readings[name] = WeightReading(
                            grams=round(float(resp["g"]), 1),
                            channel=name,
                            stable=bool(resp.get("stable", False)),
                            raw_value=int(resp.get("raw", 0)),
                            timestamp=time.time(),
                        )
                    elif resp and "err" in resp:
                        logger.debug(f"[ARDUINO WEIGHT] {name}: {resp['err']}")

            except Exception as e:
                logger.error(f"[ARDUINO WEIGHT] Reader error: {e}")
                time.sleep(1.0)

            time.sleep(0.05)  # Small gap between cycles

        logger.info("[ARDUINO WEIGHT] Background reader stopped")

    def read_weight(self, channel: str) -> WeightReading:
        """Return cached weight reading (non-blocking)."""
        if not self._initialized or not HAS_SERIAL:
            return WeightReading(grams=0.0, channel=channel, stable=False)

        cached = self._cached_readings.get(channel)
        if cached:
            return cached

        return WeightReading(grams=0.0, channel=channel, stable=False)

    def tare(self, channel: str) -> bool:
        """Request tare via background thread. Blocks up to 5s for result."""
        if not self._initialized or not HAS_SERIAL:
            return False

        self._tare_done.clear()
        self._tare_result = False
        self._tare_request = channel
        if self._tare_done.wait(timeout=5.0):
            return self._tare_result
        return False

    def set_calibration(self, channel: str, offset: int, scale: float) -> bool:
        """Send calibration to Arduino and persist to DB.

        Args:
            channel: "shelf1" or "mixing_scale"
            offset: raw ADC offset (tare value) — sent to Arduino
            scale: raw units per gram — sent to Arduino
        """
        if not self._initialized:
            return False
        arduino_ch = _to_arduino_ch(channel)

        # Send scale to Arduino
        with self._lock:
            self._send({"cmd": "cal", "ch": arduino_ch, "scale": round(scale, 4)})
            resp = self._recv(timeout=2.0)
        ok = resp is not None and "ok" in resp

        if ok:
            logger.info(f"[ARDUINO WEIGHT] Calibration set for {channel}: offset={offset}, scale={scale:.4f}")

            # Persist to DB (same as HX711 direct driver)
            try:
                import json as _json
                from persistence.database import Database
                db = Database()
                db.connect()
                db.set_config(f"hx711_cal_{channel}", _json.dumps({
                    "offset": offset,
                    "scale": scale,
                }))
                db.close()
                logger.info(f"[ARDUINO WEIGHT] Calibration saved to DB for {channel}")
            except Exception as e:
                logger.warning(f"[ARDUINO WEIGHT] Could not save calibration to DB: {e}")

        return ok

    def get_channels(self) -> List[str]:
        return list(self._channels)

    def is_healthy(self) -> bool:
        if not self._initialized or not HAS_SERIAL:
            return False
        # Check if we have recent readings
        now = time.time()
        for name in self._channels:
            r = self._cached_readings.get(name)
            if not r or (now - r.timestamp) > 5.0:
                return False
        return True

    def shutdown(self) -> None:
        self._reader_running = False
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=3.0)

        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
        self._serial = None
        self._initialized = False
        logger.info("[ARDUINO WEIGHT] Shutdown")

    # ---- Shared serial access (Arduino also handles LEDs) ----

    def get_serial(self):
        """Expose serial connection for LED driver to share."""
        return self._serial

    def get_lock(self):
        """Expose lock for LED driver to share."""
        return self._lock

    def send_command(self, cmd: dict) -> Optional[dict]:
        """Send a command and get response (thread-safe). Used by LED driver."""
        if not self._initialized:
            return None
        with self._lock:
            self._send(cmd)
            return self._recv(timeout=1.0)

    # ---- Internal serial helpers ----

    def _send(self, cmd: dict) -> None:
        """Send JSON command to Arduino (caller must hold lock)."""
        if self._serial and self._serial.is_open:
            line = json.dumps(cmd, separators=(',', ':')) + "\n"
            self._serial.write(line.encode("utf-8"))
            self._serial.flush()

    def _recv(self, timeout: float = 1.0) -> Optional[dict]:
        """Read JSON response from Arduino (caller must hold lock)."""
        if not self._serial or not self._serial.is_open:
            return None

        old_timeout = self._serial.timeout
        self._serial.timeout = timeout
        try:
            line = self._serial.readline().decode("utf-8").strip()
            if line:
                return json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(f"[ARDUINO WEIGHT] Bad response: {e}")
        except Exception as e:
            logger.error(f"[ARDUINO WEIGHT] Serial read error: {e}")
        finally:
            self._serial.timeout = old_timeout

        return None
