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
import queue
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
        self._poll_channels: List[str] = list(self._channels)
        self._fast_read_channels = set()
        self._cycle_sleep_s = 0.05

        # Background reader thread
        self._reader_thread: Optional[threading.Thread] = None
        self._reader_running = False

        # Tare request mechanism (same pattern as HX711 direct driver)
        self._tare_request: Optional[str] = None
        self._tare_done = threading.Event()
        self._tare_result = False
        self._fw_version = "?"  # Populated after ping

        # Async command queue for LED/buzzer (fire-and-forget)
        self._cmd_queue: queue.Queue = queue.Queue(maxsize=32)

    def initialize(self) -> bool:
        """
        Open serial connection to the Arduino Nano.
        Auto-detects port by opening ALL candidate ports at once,
        waiting once for boot (3.5s), then pinging each.
        This works regardless of USB port enumeration order.
        """
        if not HAS_SERIAL:
            logger.warning("[ARDUINO WEIGHT] Cannot initialize: pyserial not available.")
            self._initialized = False
            return False

        # ── Collect candidate ports ──
        ports_to_try = []
        import os

        # If a specific port is configured and exists, use ONLY that (no auto-detect)
        if self._port and os.path.exists(self._port):
            ports_to_try = [self._port]
            logger.info(f"[ARDUINO WEIGHT] Using configured port: {self._port}")
        else:
            # Auto-detect: scan all USB serial ports
            try:
                available = serial.tools.list_ports.comports()
                for p in available:
                    if any(kw in (p.description or "").lower()
                           for kw in ["ch340", "ftdi", "arduino", "usb serial", "usb-serial"]):
                        if p.device not in ports_to_try:
                            ports_to_try.append(p.device)
                            logger.info(f"[ARDUINO WEIGHT] Candidate port: {p.device} ({p.description})")
            except Exception:
                pass

        if not ports_to_try:
            logger.error("[ARDUINO WEIGHT] No USB serial ports found")
            self._initialized = False
            return False

        # ── Open ALL ports at once (Arduino resets on open) ──
        opened = {}  # port -> serial.Serial
        for port in ports_to_try:
            try:
                s = serial.Serial(port=port, baudrate=self._baud, timeout=1.0)
                opened[port] = s
            except Exception as e:
                logger.debug(f"[ARDUINO WEIGHT] Cannot open {port}: {e}")

        if not opened:
            logger.error("[ARDUINO WEIGHT] Could not open any serial port")
            self._initialized = False
            return False

        # ── Single boot wait — Arduino resets on serial open, needs 3.5s ──
        logger.info(f"[ARDUINO WEIGHT] Opened {len(opened)} ports, waiting 3.5s for Arduino boot...")
        time.sleep(3.5)

        # ── Read boot data and identify Arduino vs PN532 ──
        arduino_port = None
        for port, s in list(opened.items()):
            try:
                boot_data = b""
                if s.in_waiting:
                    boot_data = s.read(s.in_waiting)

                if boot_data:
                    logger.info(f"[ARDUINO WEIGHT] Boot data on {port}: {boot_data[:100]!r}")

                # Fast reject: PN532 sends binary with 0x00 bytes
                if boot_data and (b'\x00\x55' in boot_data or b'\x00\x00' in boot_data):
                    logger.info(f"[ARDUINO WEIGHT] Skipping {port} (PN532 binary)")
                    s.close()
                    del opened[port]
                    continue

                # Fast accept: Arduino boot messages
                if b'"boot"' in boot_data or b'"ready"' in boot_data:
                    logger.info(f"[ARDUINO WEIGHT] Arduino boot detected on {port}!")
                    arduino_port = port
                    break

            except Exception as e:
                logger.debug(f"[ARDUINO WEIGHT] Error reading boot data on {port}: {e}")

        # ── Ping remaining candidates (Arduino first if detected by boot data) ──
        if arduino_port:
            ping_order = [arduino_port] + [p for p in opened if p != arduino_port]
        else:
            ping_order = list(opened.keys())

        for port in ping_order:
            s = opened.get(port)
            if not s or not s.is_open:
                continue
            try:
                s.reset_input_buffer()
                line = json.dumps({"cmd": "ping"}, separators=(',', ':')) + "\n"
                s.write(line.encode("utf-8"))
                s.flush()

                s.timeout = 2.0
                resp_line = s.readline().decode("utf-8").strip()
                response = json.loads(resp_line) if resp_line else None

                if response and response.get("status") == "ok":
                    fw = response.get("fw", "?")
                    self._fw_version = fw
                    logger.info(f"[ARDUINO WEIGHT] Connected on {port} (firmware v{fw})")
                    self._serial = s
                    self._port = port
                    self._initialized = True

                    # Close all other ports
                    for other_port, other_s in opened.items():
                        if other_port != port:
                            try:
                                other_s.close()
                            except Exception:
                                pass

                    # Initialize cached readings
                    for name in self._channels:
                        self._cached_readings[name] = WeightReading(
                            grams=0.0, channel=name, stable=False,
                            raw_value=0, timestamp=time.time(),
                        )

                    # Trigger HX711 init and check tare source
                    self._init_hx_and_maybe_restore_tare()

                    # Start background reader
                    self._reader_running = True
                    self._reader_thread = threading.Thread(
                        target=self._reader_loop, daemon=True,
                        name="Arduino-weight-reader",
                    )
                    self._reader_thread.start()
                    return True
                else:
                    logger.info(f"[ARDUINO WEIGHT] No ping response on {port} (not Arduino)")

            except Exception as e:
                logger.debug(f"[ARDUINO WEIGHT] Ping failed on {port}: {e}")

        # ── Cleanup: close all ports if Arduino not found ──
        for s in opened.values():
            try:
                s.close()
            except Exception:
                pass

        logger.error("[ARDUINO WEIGHT] Could not connect to Arduino on any port")
        self._initialized = False
        return False

    def _init_hx_and_maybe_restore_tare(self) -> None:
        """Send init_hx to Arduino, read the hx711_ready response to check
        the tare source. If Arduino auto-tared (EEPROM was empty/invalid),
        attempt to restore tare offsets from DB backup."""
        try:
            with self._lock:
                self._send({"cmd": "init_hx"})
                # Wait for hx711_ready (or hx711_init_start + hx711_ready)
                deadline = time.time() + 20.0
                source = None
                while time.time() < deadline:
                    resp = self._recv(timeout=5.0)
                    if resp is None:
                        continue
                    if resp.get("info") == "hx711_ready" or resp.get("info") == "hx711_ready_debug":
                        source = resp.get("source", "unknown")
                        shelf_off = resp.get("shelf_off", 0)
                        mix_off = resp.get("mix_off", 0)
                        logger.info(
                            f"[ARDUINO WEIGHT] HX711 ready: source={source}, "
                            f"shelf_off={shelf_off}, mix_off={mix_off}"
                        )
                        break
                    elif resp.get("info") == "hx711_init_start":
                        logger.info("[ARDUINO WEIGHT] HX711 init started, waiting for ready...")
                        continue
                    else:
                        logger.debug(f"[ARDUINO WEIGHT] init_hx skipped msg: {resp}")

            if source == "auto_tare":
                logger.info("[ARDUINO WEIGHT] EEPROM was empty — checking DB for tare backup...")
                self._try_restore_tare_from_db()
            elif source == "eeprom":
                logger.info("[ARDUINO WEIGHT] Tare loaded from EEPROM (good)")
            else:
                logger.info(f"[ARDUINO WEIGHT] Tare source: {source}")

        except Exception as e:
            logger.warning(f"[ARDUINO WEIGHT] init_hx sequence failed: {e}")

    def _restore_calibration_from_db(self):
        """Restore saved calibration factors from DB and send to Arduino.
        This ensures correct calibration even after Arduino reboot."""
        try:
            from persistence.database import Database
            db = Database()
            db.connect()
            restored = 0
            for channel in self._channels:
                cal_json = db.get_config(f"hx711_cal_{channel}")
                if cal_json:
                    cal = json.loads(cal_json)
                    scale = cal.get("scale", 0)
                    if scale > 0.1:  # Sanity check — reject invalid values
                        arduino_ch = _to_arduino_ch(channel)
                        with self._lock:
                            self._send({"cmd": "cal", "ch": arduino_ch,
                                        "scale": round(scale, 4)})
                            resp = self._recv(timeout=2.0)
                        if resp and "ok" in resp:
                            logger.info(
                                f"[ARDUINO WEIGHT] Restored calibration for "
                                f"{channel}: scale={scale:.4f}"
                            )
                            restored += 1
                        else:
                            logger.warning(
                                f"[ARDUINO WEIGHT] Failed to restore cal for "
                                f"{channel}: {resp}"
                            )
                    else:
                        logger.warning(
                            f"[ARDUINO WEIGHT] Skipping bad cal for {channel}: "
                            f"scale={scale}"
                        )
            db.close()
            if restored:
                logger.info(f"[ARDUINO WEIGHT] Restored {restored} calibration(s) from DB")
        except Exception as e:
            logger.warning(f"[ARDUINO WEIGHT] Could not restore calibration: {e}")

    # ---- Tare backup: DB as fallback for EEPROM ----

    def _save_tare_to_db(self, tare_resp: dict) -> None:
        """Save tare offsets to DB after a successful tare command.

        DB keys: hx711_tare_shelf, hx711_tare_mix
        Value: JSON with offset, timestamp, source, fw, channel
        """
        try:
            from persistence.database import Database
            db = Database()
            db.connect()

            shelf_off = tare_resp.get("shelf_off")
            mix_off = tare_resp.get("mix_off")
            now = time.time()

            if shelf_off is not None and shelf_off != 0:
                db.save_config("hx711_tare_shelf", json.dumps({
                    "offset": shelf_off,
                    "timestamp": now,
                    "source": "tare_command",
                    "fw": self._fw_version,
                    "channel": "shelf",
                }))
                logger.info(f"[ARDUINO WEIGHT] Tare backup saved to DB: shelf offset={shelf_off}")

            if mix_off is not None and mix_off != 0:
                db.save_config("hx711_tare_mix", json.dumps({
                    "offset": mix_off,
                    "timestamp": now,
                    "source": "tare_command",
                    "fw": self._fw_version,
                    "channel": "mix",
                }))
                logger.info(f"[ARDUINO WEIGHT] Tare backup saved to DB: mix offset={mix_off}")

            db.close()
        except Exception as e:
            logger.warning(f"[ARDUINO WEIGHT] Could not save tare to DB: {e}")

    def _try_restore_tare_from_db(self) -> None:
        """If Arduino booted with auto_tare (EEPROM was empty), try to restore
        offsets from DB backup via set_offset command.

        Priority: EEPROM (already loaded by Arduino) > DB backup > auto_tare.
        This method is only called when Arduino reports source='auto_tare'.
        """
        try:
            from persistence.database import Database
            db = Database()
            db.connect()

            shelf_json = db.get_config("hx711_tare_shelf")
            mix_json = db.get_config("hx711_tare_mix")
            db.close()

            if not shelf_json and not mix_json:
                logger.info("[ARDUINO WEIGHT] No tare backup in DB — keeping auto_tare offsets")
                return

            # Parse and validate
            shelf_off = 0
            mix_off = 0
            if shelf_json:
                shelf_data = json.loads(shelf_json)
                shelf_off = shelf_data.get("offset", 0)
                shelf_age_h = (time.time() - shelf_data.get("timestamp", 0)) / 3600
                logger.info(
                    f"[ARDUINO WEIGHT] DB tare backup found: shelf offset={shelf_off} "
                    f"(age={shelf_age_h:.1f}h, source={shelf_data.get('source', '?')})"
                )
            if mix_json:
                mix_data = json.loads(mix_json)
                mix_off = mix_data.get("offset", 0)
                mix_age_h = (time.time() - mix_data.get("timestamp", 0)) / 3600
                logger.info(
                    f"[ARDUINO WEIGHT] DB tare backup found: mix offset={mix_off} "
                    f"(age={mix_age_h:.1f}h, source={mix_data.get('source', '?')})"
                )

            # Sanity: offsets must be non-zero
            if shelf_off == 0 and mix_off == 0:
                logger.warning("[ARDUINO WEIGHT] DB tare offsets are zero — skipping restore")
                return

            # Send set_offset to Arduino (restores offsets + saves to EEPROM)
            with self._lock:
                if shelf_off and mix_off:
                    self._send({"cmd": "set_offset", "ch": "all",
                                "shelf_off": shelf_off, "mix_off": mix_off})
                elif shelf_off:
                    self._send({"cmd": "set_offset", "ch": "shelf", "offset": shelf_off})
                elif mix_off:
                    self._send({"cmd": "set_offset", "ch": "mix", "offset": mix_off})
                resp = self._recv(timeout=5.0)

            if resp and "ok" in resp:
                logger.info(
                    f"[ARDUINO WEIGHT] Tare restored from DB backup! "
                    f"shelf_off={resp.get('shelf_off')}, mix_off={resp.get('mix_off')}"
                )
            else:
                logger.warning(f"[ARDUINO WEIGHT] set_offset failed: {resp}")

        except Exception as e:
            logger.warning(f"[ARDUINO WEIGHT] Could not restore tare from DB: {e}")

    def _reader_loop(self):
        """Background thread: continuously polls weight from Arduino."""
        logger.info("[ARDUINO WEIGHT] Background reader started")
        while self._reader_running:
            try:
                # Drain queued LED/buzzer commands FIRST (fast, non-blocking)
                self._drain_command_queue()

                # Handle tare requests
                tare_ch = self._tare_request
                if tare_ch:
                    self._tare_request = None
                    arduino_ch = _to_arduino_ch(tare_ch)
                    with self._lock:
                        self._send({"cmd": "tare", "ch": arduino_ch})
                        resp = self._recv(timeout=6.0)
                    self._tare_result = resp is not None and "ok" in resp
                    if self._tare_result:
                        logger.info(f"[ARDUINO WEIGHT] Tared '{tare_ch}'")
                        self._cached_readings.pop(tare_ch, None)
                        # Save tare offsets to DB as backup
                        if resp:
                            self._save_tare_to_db(resp)
                    self._tare_done.set()

                poll_channels = list(self._poll_channels or self._channels)

                # Read active channels only
                for name in poll_channels:
                    if not self._reader_running:
                        break
                    arduino_ch = _to_arduino_ch(name)
                    cmd_name = "read_fast" if name in self._fast_read_channels else "read"
                    with self._lock:
                        self._send({"cmd": cmd_name, "ch": arduino_ch})
                        resp = self._recv(timeout=2.5, expect_ch=arduino_ch)

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

                    # Drain queued commands between channels too
                    self._drain_command_queue()

            except Exception as e:
                logger.error(f"[ARDUINO WEIGHT] Reader error: {e}")
                time.sleep(1.0)

            time.sleep(self._cycle_sleep_s)

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
        """Request tare via background thread. Blocks up to 15s for result.
        SAMPLES_TARE=30 at 10Hz = 3s/channel, tare all = ~6s + overhead."""
        if not self._initialized or not HAS_SERIAL:
            return False

        self._tare_done.clear()
        self._tare_result = False
        self._tare_request = channel
        if self._tare_done.wait(timeout=15.0):
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

    def set_poll_channels(self, channels: Optional[List[str]] = None,
                          cycle_sleep_s: Optional[float] = None) -> None:
        """Limit background polling to specific channels.

        Args:
            channels: Internal channel names to poll. None/empty restores all.
            cycle_sleep_s: Optional loop delay override.
        """
        if channels:
            valid = [ch for ch in channels if ch in self._channels]
            self._poll_channels = valid or list(self._channels)
        else:
            self._poll_channels = list(self._channels)

        if cycle_sleep_s is not None:
            self._cycle_sleep_s = max(0.0, cycle_sleep_s)
        else:
            self._cycle_sleep_s = 0.05

        logger.info(
            f"[ARDUINO WEIGHT] Poll channels set to {self._poll_channels} "
            f"(cycle_sleep={self._cycle_sleep_s:.3f}s)"
        )

    def focus_mixing_scale(self, enabled: bool) -> None:
        """Convenience mode: prioritize mixing scale during active mixing."""
        if enabled:
            self._fast_read_channels = {"mixing_scale"}
            self.set_poll_channels(["mixing_scale"], cycle_sleep_s=0.01)
        else:
            self._fast_read_channels = set()
            self.set_poll_channels(None, cycle_sleep_s=0.05)

    def is_healthy(self) -> bool:
        if not self._initialized or not HAS_SERIAL:
            return False
        # Check if we have recent readings
        # With SAMPLES_NORMAL=20 each read takes ~2s, full cycle ~5s
        now = time.time()
        for name in self._channels:
            r = self._cached_readings.get(name)
            if not r or (now - r.timestamp) > 15.0:
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
        """Send a command and get response (SYNCHRONOUS, thread-safe).
        Use ONLY for init/test where the response is needed.
        For LED blink / buzzer, use enqueue_command() instead."""
        if not self._initialized:
            return None
        with self._lock:
            self._send(cmd)
            return self._recv(timeout=1.0)

    def enqueue_command(self, cmd: dict) -> None:
        """Fire-and-forget: put a command on the async queue.
        The reader loop drains this queue between weight reads.
        If queue is full, the command is silently dropped
        (LED/buzzer tolerate missed commands)."""
        try:
            self._cmd_queue.put_nowait(cmd)
        except queue.Full:
            logger.debug("[ARDUINO WEIGHT] Command queue full, dropping: %s", cmd.get("cmd"))

    def _drain_command_queue(self) -> None:
        """Process up to 8 queued commands (LED/buzzer).
        Called by _reader_loop between weight reads.
        Each command holds the lock for ~50ms max."""
        for _ in range(8):
            try:
                cmd = self._cmd_queue.get_nowait()
            except queue.Empty:
                break
            try:
                with self._lock:
                    self._send(cmd)
                    self._recv(timeout=0.2)  # Short timeout — response not critical
            except Exception as e:
                logger.debug(f"[ARDUINO WEIGHT] Queued cmd failed: {e}")

    # ---- Internal serial helpers ----

    def _send(self, cmd: dict) -> None:
        """Send JSON command to Arduino (caller must hold lock).
        Drains any stale data in the buffer before sending."""
        if self._serial and self._serial.is_open:
            # Drain stale responses from previous commands
            if self._serial.in_waiting:
                stale = self._serial.read(self._serial.in_waiting)
                logger.debug(f"[ARDUINO WEIGHT] Drained {len(stale)} stale bytes")
            line = json.dumps(cmd, separators=(',', ':')) + "\n"
            self._serial.write(line.encode("utf-8"))
            self._serial.flush()

    def _recv(self, timeout: float = 5.0, expect_ch: str = None) -> Optional[dict]:
        """Read JSON response from Arduino (caller must hold lock).

        If expect_ch is set, reads lines in a loop until a response with
        matching 'ch' field is found, discarding non-matching lines.
        If expect_ch is None, returns the first valid JSON object.
        """
        if not self._serial or not self._serial.is_open:
            return None

        old_timeout = self._serial.timeout
        self._serial.timeout = min(timeout, 1.0)  # readline granularity
        deadline = time.time() + timeout

        try:
            while time.time() < deadline:
                line = self._serial.readline().decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                try:
                    obj = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    logger.debug(f"[ARDUINO WEIGHT] Non-JSON line: {line[:80]}")
                    continue

                # No channel filter — return first valid JSON
                if expect_ch is None:
                    return obj

                # Check channel match
                resp_ch = obj.get("ch", "")
                if resp_ch == expect_ch:
                    return obj

                # Discard with appropriate log
                if "info" in obj or "boot" in obj:
                    logger.debug(f"[ARDUINO WEIGHT] Skipped init msg: {line[:60]}")
                elif resp_ch:
                    logger.debug(
                        f"[ARDUINO WEIGHT] Skipped wrong ch "
                        f"(want={expect_ch}, got={resp_ch})")
                else:
                    logger.debug(f"[ARDUINO WEIGHT] Skipped non-weight: {line[:60]}")

        except Exception as e:
            logger.error(f"[ARDUINO WEIGHT] Serial read error: {e}")
        finally:
            self._serial.timeout = old_timeout

        return None
