"""
Real Weight Driver - Arduino Nano HX711 Bridge via Serial

Communicates with an Arduino Nano that reads HX711 load cell amplifiers
and sends weight data as JSON lines over USB serial.

Hardware setup:
  - Arduino Nano connected to RPi via USB (appears as /dev/ttyUSB0)
  - Arduino runs custom firmware that reads HX711 chips
  - Each HX711 channel measures one shelf or the mixing scale

Serial protocol (Arduino -> RPi):
  Arduino sends JSON lines, one per reading:
    {"channel": "shelf1", "grams": 1234.5, "stable": true}
    {"channel": "mixing_scale", "grams": 567.8, "stable": false}

  RPi sends commands to Arduino:
    {"cmd": "read", "channel": "shelf1"}       -> request a reading
    {"cmd": "tare", "channel": "mixing_scale"} -> zero the scale
    {"cmd": "ping"}                            -> health check (responds: {"status": "ok"})

Required library:
  pip install pyserial

Graceful fallback: if pyserial is not installed (e.g., on a dev machine without
serial hardware), all methods log warnings and return safe defaults without
crashing.
"""

import logging
import time
import json
from typing import List, Dict, Optional

from hal.interfaces import WeightDriverInterface, WeightReading

logger = logging.getLogger("smartlocker.sensor")

# ---------- Graceful import with fallback ----------
try:
    import serial
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False
    serial = None  # type: ignore[assignment, misc]
    logger.warning(
        "[REAL WEIGHT] pyserial library not installed. "
        "Weight sensor will be non-functional. Install with: pip install pyserial"
    )


class RealWeightDriver(WeightDriverInterface):
    """
    Real weight sensor driver using Arduino Nano as HX711 bridge.

    The Arduino reads multiple HX711 load cell amplifiers and communicates
    via USB serial with JSON-formatted messages.
    """

    def __init__(self, channels: Optional[List[str]] = None):
        from config.settings import WEIGHT_SERIAL_PORT, WEIGHT_SERIAL_BAUD
        self._port = WEIGHT_SERIAL_PORT
        self._baud = WEIGHT_SERIAL_BAUD
        self._channels = channels or ["shelf1", "mixing_scale"]
        self._serial = None
        self._initialized = False
        # Cache of last readings per channel
        self._last_readings: Dict[str, WeightReading] = {}

    def initialize(self) -> bool:
        """
        Open serial connection to the Arduino Nano.
        Sends a ping command to verify communication.
        Returns True if Arduino responds, False otherwise.
        If pyserial is not installed, returns False and logs a warning.
        """
        if not HAS_SERIAL:
            logger.warning(
                "[REAL WEIGHT] Cannot initialize: pyserial library not available. "
                "All weight operations will return zero readings."
            )
            self._initialized = False
            return False

        try:
            self._serial = serial.Serial(
                port=self._port,
                baudrate=self._baud,
                timeout=2.0,
            )

            # Wait for Arduino to boot (it resets on serial connect)
            time.sleep(2.0)

            # Flush any boot messages
            self._serial.reset_input_buffer()

            # Send ping to verify communication
            self._send_command({"cmd": "ping"})
            response = self._read_response(timeout=3.0)

            if response and response.get("status") == "ok":
                logger.info(f"[REAL WEIGHT] Arduino connected on {self._port}")
                self._initialized = True
                return True
            else:
                logger.error("[REAL WEIGHT] Arduino did not respond to ping")
                self._serial.close()
                self._serial = None
                self._initialized = False
                return False

        except Exception as e:
            logger.error(f"[REAL WEIGHT] Failed to initialize serial: {e}")
            if self._serial is not None:
                try:
                    self._serial.close()
                except Exception:
                    pass
            self._serial = None
            self._initialized = False
            return False

    def read_weight(self, channel: str) -> WeightReading:
        """
        Request a weight reading from the Arduino for a specific channel.
        Returns the last known reading if communication fails.
        """
        if not self._initialized or not HAS_SERIAL:
            if not HAS_SERIAL:
                logger.warning(f"[REAL WEIGHT] No-op read_weight('{channel}'): library not available")
            return WeightReading(grams=0.0, channel=channel, stable=False)

        if channel not in self._channels:
            logger.warning(f"[REAL WEIGHT] Unknown channel: {channel}")
            return WeightReading(grams=0.0, channel=channel, stable=False)

        try:
            self._send_command({"cmd": "read", "channel": channel})
            response = self._read_response(timeout=1.0)

            if response and "grams" in response:
                reading = WeightReading(
                    grams=float(response["grams"]),
                    channel=channel,
                    stable=bool(response.get("stable", False)),
                    raw_value=int(response.get("raw", 0)),
                    timestamp=time.time(),
                )
                self._last_readings[channel] = reading
                return reading

        except Exception as e:
            logger.error(f"[REAL WEIGHT] Read error on '{channel}': {e}")

        # Return last known reading or zero
        return self._last_readings.get(
            channel,
            WeightReading(grams=0.0, channel=channel, stable=False)
        )

    def tare(self, channel: str) -> bool:
        """
        Send tare (zero) command to Arduino for a specific channel.
        Returns True if the Arduino acknowledges the tare.
        """
        if not self._initialized or not HAS_SERIAL:
            if not HAS_SERIAL:
                logger.warning(f"[REAL WEIGHT] No-op tare('{channel}'): library not available")
            return False

        try:
            self._send_command({"cmd": "tare", "channel": channel})
            response = self._read_response(timeout=2.0)

            if response and response.get("status") == "ok":
                logger.info(f"[REAL WEIGHT] Tared '{channel}'")
                # Clear cached reading for this channel after tare
                self._last_readings.pop(channel, None)
                return True
            else:
                logger.warning(f"[REAL WEIGHT] Tare failed for '{channel}'")
                return False

        except Exception as e:
            logger.error(f"[REAL WEIGHT] Tare error on '{channel}': {e}")
            return False

    def get_channels(self) -> List[str]:
        """Return list of configured weight channels."""
        return list(self._channels)

    def is_healthy(self) -> bool:
        """Check if Arduino serial connection is alive."""
        if not self._initialized or not HAS_SERIAL:
            return False

        try:
            self._send_command({"cmd": "ping"})
            response = self._read_response(timeout=1.0)
            return response is not None and response.get("status") == "ok"
        except Exception:
            return False

    def shutdown(self) -> None:
        """Close serial connection to Arduino."""
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
        self._serial = None
        self._initialized = False
        logger.info("[REAL WEIGHT] Shutdown")

    # ---- INTERNAL HELPERS ----

    def _send_command(self, cmd: dict) -> None:
        """Send a JSON command to the Arduino."""
        if self._serial and self._serial.is_open:
            line = json.dumps(cmd) + "\n"
            self._serial.write(line.encode("utf-8"))
            self._serial.flush()

    def _read_response(self, timeout: float = 1.0) -> Optional[dict]:
        """
        Read a JSON response line from the Arduino.
        Returns parsed dict or None if timeout/error.
        """
        if not self._serial or not self._serial.is_open:
            return None

        old_timeout = self._serial.timeout
        self._serial.timeout = timeout
        try:
            line = self._serial.readline().decode("utf-8").strip()
            if line:
                return json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(f"[REAL WEIGHT] Bad response: {e}")
        except Exception as e:
            logger.error(f"[REAL WEIGHT] Serial read error: {e}")
        finally:
            self._serial.timeout = old_timeout

        return None
