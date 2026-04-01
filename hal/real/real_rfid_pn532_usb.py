"""
Real RFID Driver - PN532 NFC Reader via USB Serial (CH340 bridge)

Uses the adafruit-circuitpython-pn532 library for reliable communication.
Reads NTAG215 tags: UID + product data (CODE|BATCH|NAME|COLOR).

Hardware: PN532 V2/V3 module with CH340 USB-UART bridge -> /dev/ttyUSBx
Required: pip install pyserial adafruit-circuitpython-pn532

Plug-and-play: hot-swap modules without reboot.
"""

import logging
import threading
import time
from typing import List, Optional

from hal.interfaces import RFIDDriverInterface, TagReading

logger = logging.getLogger("smartlocker.sensor")

try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False
    logger.warning("[PN532 USB] pyserial not installed. pip install pyserial")

try:
    from adafruit_pn532.uart import PN532_UART
    HAS_ADAFRUIT = True
except ImportError:
    HAS_ADAFRUIT = False
    PN532_UART = None
    logger.warning(
        "[PN532 USB] adafruit-circuitpython-pn532 not installed. "
        "pip install adafruit-circuitpython-pn532"
    )


# NTAG215 user data starts at page 4
USER_PAGE_START = 4
USER_PAGE_END = 129
PRODUCT_SEPARATOR = "|"


class RealRFIDDriverPN532USB(RFIDDriverInterface):
    """PN532 NFC driver via USB serial using adafruit_pn532 library.

    Plug-and-play: if the USB device disconnects, the driver
    gracefully degrades and reconnects on later polls.
    """

    def __init__(self, port: Optional[str] = None, baudrate: int = 115200):
        self._port = port
        self._baudrate = baudrate
        self._ser: Optional["serial.Serial"] = None
        self._pn532: Optional["PN532_UART"] = None
        self._initialized = False
        self._lock = threading.Lock()
        self._reader_ids = [
            "shelf1_slot1", "shelf1_slot2",
            "shelf1_slot3", "shelf1_slot4",
        ]
        self._last_error_time = 0.0
        # Tag data cache: {uid_str: {"product_data": ..., "parsed": ..., "time": ...}}
        self._tag_cache = {}
        self._last_reconnect_attempt = 0.0
        self._reconnect_backoff_s = 3.0

    # ----------------------------------------------------------
    # Port detection
    # ----------------------------------------------------------

    def _find_port(self) -> Optional[str]:
        """Auto-detect PN532 USB port, skipping Arduino."""
        if self._port:
            return self._port

        # Get ports claimed by Arduino
        claimed_ports = set()
        try:
            from config.settings import WEIGHT_MODE
            if WEIGHT_MODE == "arduino_serial":
                import os
                for check_port in ["/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyUSB2", "/dev/ttyUSB3"]:
                    if os.path.exists(check_port):
                        try:
                            test = serial.Serial(check_port, 115200, timeout=0.5)
                            time.sleep(0.3)
                            test.reset_input_buffer()
                            test.write(b'{"cmd":"ping"}\n')
                            time.sleep(0.5)
                            resp = test.readline().decode("utf-8", errors="ignore").strip()
                            test.close()
                            if "fw" in resp or "status" in resp or "boot" in resp:
                                claimed_ports.add(check_port)
                                logger.info(f"[PN532 USB] Skipping {check_port} (Arduino)")
                        except Exception:
                            pass
        except Exception:
            pass

        try:
            for p in serial.tools.list_ports.comports():
                if p.device in claimed_ports:
                    continue
                desc = (p.description or "").lower()
                vid_pid = f"{p.vid:04X}:{p.pid:04X}" if p.vid else ""
                if any(k in desc for k in ["ch340", "ch341", "cp210", "usb-serial", "usb serial"]):
                    logger.info(f"[PN532 USB] Auto-detected port: {p.device} ({p.description})")
                    return p.device
                if vid_pid in ("1A86:7523", "10C4:EA60"):
                    logger.info(f"[PN532 USB] Auto-detected port by VID:PID: {p.device}")
                    return p.device

            # Fallback
            import os
            for fallback in ["/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyUSB2", "/dev/ttyACM0"]:
                if os.path.exists(fallback) and fallback not in claimed_ports:
                    return fallback
        except Exception as e:
            logger.debug(f"[PN532 USB] Port scan error: {e}")
        return None

    # ----------------------------------------------------------
    # Connection management
    # ----------------------------------------------------------

    def _connect(self) -> bool:
        """Open serial port and initialize PN532 via adafruit library."""
        port = self._find_port()
        if not port:
            logger.warning("[PN532 USB] No USB serial port found")
            return False

        try:
            self._ser = serial.Serial(port, self._baudrate, timeout=1)
            # Wait for CH340 bridge to stabilize after port open
            time.sleep(2)
            # Flush any boot/garbage data from the PN532
            self._ser.reset_input_buffer()
            self._ser.reset_output_buffer()

            self._pn532 = PN532_UART(self._ser, debug=False)

            # Get firmware version to verify connection
            ic, ver, rev, support = self._pn532.firmware_version
            logger.info(f"[PN532 USB] Firmware: v{ver}.{rev} on {port}")

            # Configure SAM (Security Access Module) for normal mode
            self._pn532.SAM_configuration()

            self._port = port
            return True

        except Exception as e:
            logger.error(f"[PN532 USB] Connection failed on {port}: {e}")
            self._disconnect()
            return False

    def _disconnect(self):
        """Close serial connection."""
        self._pn532 = None
        if self._ser:
            try:
                self._ser.close()
            except Exception:
                pass
        self._ser = None

    def _try_reconnect(self):
        """Attempt to reconnect after USB disconnect or failed health check."""
        now = time.time()
        if now - self._last_reconnect_attempt < self._reconnect_backoff_s:
            return
        self._last_reconnect_attempt = now

        logger.info("[PN532 USB] Attempting reconnect...")
        self._disconnect()
        if self._connect():
            self._initialized = True
            logger.info("[PN532 USB] Reconnected successfully")
        else:
            self._initialized = False

    # ----------------------------------------------------------
    # Tag operations
    # ----------------------------------------------------------

    def _read_product_data(self) -> Optional[str]:
        """Read product data string from NTAG215 user pages."""
        if not self._pn532:
            return None

        try:
            data = bytearray()
            for page in range(USER_PAGE_START, min(USER_PAGE_END, USER_PAGE_START + 20)):
                page_data = self._pn532.ntag2xx_read_block(page)
                if not page_data:
                    break
                # Check for null terminator
                null_idx = page_data.find(b"\x00")
                if null_idx >= 0:
                    data.extend(page_data[:null_idx])
                    break
                data.extend(page_data)

            if data:
                text = data.decode("ascii", errors="ignore").strip()
                if text and PRODUCT_SEPARATOR in text:
                    return text
        except Exception as e:
            logger.debug(f"[PN532 USB] Read product data error: {e}")

        return None

    def write_product_data(self, product_string: str) -> bool:
        """Write product data to NTAG215 tag.

        Format: PPG_CODE|BATCH|PRODUCT_NAME|COLOR
        """
        if not self._pn532:
            return False

        with self._lock:
            try:
                data = product_string.encode("ascii")
                page = USER_PAGE_START
                for i in range(0, len(data), 4):
                    chunk = data[i:i + 4]
                    if len(chunk) < 4:
                        chunk = chunk + b"\x00" * (4 - len(chunk))
                    self._pn532.ntag2xx_write_block(page, chunk)
                    page += 1

                # Null terminator
                self._pn532.ntag2xx_write_block(page, b"\x00\x00\x00\x00")

                logger.info(f"[PN532 USB] Wrote {len(data)} bytes to pages {USER_PAGE_START}-{page}")
                return True
            except Exception as e:
                logger.error(f"[PN532 USB] Write failed: {e}")
                return False

    # ----------------------------------------------------------
    # HAL Interface implementation
    # ----------------------------------------------------------

    def initialize(self) -> bool:
        if not HAS_SERIAL:
            logger.warning("[PN532 USB] pyserial not available")
            return False

        if not HAS_ADAFRUIT:
            logger.warning("[PN532 USB] adafruit_pn532 not available")
            return False

        # Try up to 3 times (CH340 sometimes needs multiple attempts)
        with self._lock:
            for attempt in range(1, 4):
                if self._connect():
                    self._initialized = True
                    logger.info(f"[PN532 USB] Initialized on {self._port}")
                    return True
                logger.warning(f"[PN532 USB] Init attempt {attempt}/3 failed, retrying...")
                self._disconnect()
                time.sleep(2)

        return False

    def poll_tags(self) -> List[TagReading]:
        if not self._initialized or not self._pn532:
            self._try_reconnect()
            return []

        with self._lock:
            try:
                uid = self._pn532.read_passive_target(timeout=0.05)
                if uid is None:
                    return []

                tag_id = ":".join(f"{b:02X}" for b in uid)

                # Check cache — only read NTAG pages once per tag
                cached = self._tag_cache.get(tag_id)
                if cached:
                    product_data = cached["product_data"]
                    parsed = cached["parsed"]
                else:
                    # First time seeing this tag — read product data (slow)
                    product_data = self._read_product_data()
                    parsed = {}
                    if product_data:
                        parts = product_data.split(PRODUCT_SEPARATOR)
                        if len(parts) >= 4:
                            parsed = {
                                "ppg_code": parts[0],
                                "batch_number": parts[1],
                                "product_name": parts[2],
                                "color": parts[3],
                            }
                    # Cache for next polls
                    self._tag_cache[tag_id] = {
                        "product_data": product_data,
                        "parsed": parsed,
                        "time": time.time(),
                    }
                    logger.info(f"[PN532 USB] Tag {tag_id} cached: {product_data or 'no data'}")

                return [TagReading(
                    tag_id=tag_id,
                    reader_id=self._reader_ids[0],
                    signal_strength=90,
                    timestamp=time.time(),
                    product_data=product_data,
                    ppg_code=parsed.get("ppg_code"),
                    batch_number=parsed.get("batch_number"),
                    product_name=parsed.get("product_name"),
                    color=parsed.get("color"),
                )]

            except Exception as e:
                now = time.time()
                if now - self._last_error_time > 30:
                    logger.error(f"[PN532 USB] Poll error: {e}")
                    self._last_error_time = now
                # I/O error = USB disconnect, try reconnect
                err_str = str(e).lower()
                if "i/o error" in err_str or "input/output" in err_str or "errno 5" in err_str:
                    logger.warning("[PN532 USB] USB I/O error - reconnecting...")
                    self._try_reconnect()
                elif not self._ser or not self._ser.is_open:
                    self._try_reconnect()
                return []

    def get_reader_ids(self) -> List[str]:
        return list(self._reader_ids)

    def is_healthy(self) -> bool:
        """Check if PN532 is connected. Non-blocking — just checks state."""
        return self._initialized and self._pn532 is not None and self._ser is not None

    def shutdown(self) -> None:
        with self._lock:
            self._disconnect()
        self._initialized = False
        logger.info("[PN532 USB] Shutdown")
