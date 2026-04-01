"""
Real RFID Driver - PN532 NFC Reader via USB Serial (CH340 bridge)

Reads/writes NTAG215 tags: UID + product data (CODE|BATCH|NAME|COLOR).

Hardware: PN532 V3 module with CH340 USB-UART bridge -> /dev/ttyUSB0
No special libraries needed — just pyserial.

Plug-and-play: hot-swap modules without reboot.
"""

import logging
import time
import threading
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


# NTAG215 user data starts at page 4
USER_PAGE_START = 4
USER_PAGE_END = 129  # NTAG215 has pages 0-134, user area 4-129
PRODUCT_SEPARATOR = "|"


class RealRFIDDriverPN532USB(RFIDDriverInterface):
    """PN532 NFC driver via USB serial (CH340/CP2102 bridge).

    Plug-and-play: if the USB device disconnects, the driver
    gracefully degrades and reconnects on next poll.
    """

    def __init__(self, port: Optional[str] = None, baudrate: int = 115200):
        self._port = port
        self._baudrate = baudrate
        self._ser: Optional["serial.Serial"] = None
        self._initialized = False
        self._lock = threading.Lock()
        self._reader_ids = [
            "shelf1_slot1", "shelf1_slot2",
            "shelf1_slot3", "shelf1_slot4",
        ]
        self._last_error_time = 0.0

    # ----------------------------------------------------------
    # Low-level PN532 serial protocol
    # ----------------------------------------------------------

    def _find_port(self) -> Optional[str]:
        """Auto-detect PN532 USB port (CH340/CP2102).

        Skips ports already claimed by the Arduino weight driver.
        """
        if self._port:
            return self._port

        # Get port claimed by Arduino weight driver (if any)
        claimed_ports = set()
        try:
            from config.settings import WEIGHT_MODE
            if WEIGHT_MODE == "arduino_serial":
                from config.settings import WEIGHT_SERIAL_PORT
                claimed_ports.add(WEIGHT_SERIAL_PORT)
                # Also skip any port that's already open (can't open exclusively)
                import os
                for check_port in ["/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyUSB2"]:
                    if os.path.exists(check_port):
                        try:
                            test = serial.Serial(check_port, 115200, timeout=0.1)
                            test.close()
                        except Exception:
                            # Port already open = claimed by Arduino
                            claimed_ports.add(check_port)
                            logger.info(f"[PN532 USB] Skipping {check_port} (already in use)")
        except Exception:
            pass

        try:
            for p in serial.tools.list_ports.comports():
                if p.device in claimed_ports:
                    continue
                desc = (p.description or "").lower()
                vid_pid = f"{p.vid:04X}:{p.pid:04X}" if p.vid else ""
                # CH340 = 1A86:7523, CP2102 = 10C4:EA60
                if any(k in desc for k in ["ch340", "cp210", "usb-serial", "usb serial"]):
                    logger.info(f"[PN532 USB] Auto-detected port: {p.device} ({p.description})")
                    return p.device
                if vid_pid in ("1A86:7523", "10C4:EA60"):
                    logger.info(f"[PN532 USB] Auto-detected port by VID:PID: {p.device}")
                    return p.device
            # Fallback: try common paths (skip claimed)
            import os
            for fallback in ["/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyUSB2", "/dev/ttyACM0"]:
                if os.path.exists(fallback) and fallback not in claimed_ports:
                    return fallback
        except Exception as e:
            logger.debug(f"[PN532 USB] Port scan error: {e}")
        return None

    def _open_serial(self) -> bool:
        """Open serial connection to PN532."""
        port = self._find_port()
        if not port:
            logger.warning("[PN532 USB] No USB serial port found")
            return False

        try:
            self._ser = serial.Serial(port, self._baudrate, timeout=0.5)
            time.sleep(0.3)
            self._ser.reset_input_buffer()
            self._port = port
            return True
        except Exception as e:
            logger.error(f"[PN532 USB] Cannot open {port}: {e}")
            self._ser = None
            return False

    def _send_command(self, data: List[int], timeout: float = 1.0) -> Optional[bytes]:
        """Send a PN532 command frame and return the response data (after TFI)."""
        if not self._ser:
            return None

        # Build frame: preamble + length + LCS + TFI(0xD4) + data + DCS + postamble
        length = len(data) + 1
        lcs = (0x100 - length) & 0xFF
        body = [0xD4] + data
        dcs = (0x100 - (sum(body) & 0xFF)) & 0xFF
        frame = bytes([0x00, 0x00, 0xFF, length, lcs] + body + [dcs, 0x00])

        try:
            self._ser.reset_input_buffer()
            self._ser.write(frame)

            # Read ACK (6 bytes: 00 00 FF 00 FF 00)
            old_timeout = self._ser.timeout
            self._ser.timeout = 0.3
            ack = self._ser.read(6)
            self._ser.timeout = timeout

            # Read response frame
            resp = self._ser.read(64)
            self._ser.timeout = old_timeout

            if not resp:
                return None

            # Find response TFI marker (0xD5)
            idx = resp.find(b'\xD5')
            if idx < 0:
                return None

            return resp[idx:]  # D5 + command_response + data...

        except (serial.SerialException, OSError) as e:
            logger.error(f"[PN532 USB] Serial error: {e}")
            self._close_serial()
            return None

    def _close_serial(self):
        """Safely close serial port."""
        if self._ser:
            try:
                self._ser.close()
            except Exception:
                pass
        self._ser = None

    def _wakeup(self) -> bool:
        """Send wakeup sequence and verify firmware."""
        if not self._ser:
            return False
        try:
            # Wakeup preamble
            wakeup = (b'\x55' * 16) + bytes([
                0xFF, 0x03, 0xFD, 0xD4, 0x14, 0x01, 0x17, 0x00
            ])
            self._ser.write(wakeup)
            time.sleep(0.5)
            self._ser.read(100)  # flush

            # GetFirmwareVersion
            resp = self._send_command([0x02], timeout=1.0)
            if resp and len(resp) >= 5 and resp[1] == 0x03:
                ic = resp[2]
                fw_ver = resp[3]
                fw_rev = resp[4]
                logger.info(
                    f"[PN532 USB] Firmware: IC=0x{ic:02X} v{fw_ver}.{fw_rev}"
                )
                return True
        except Exception as e:
            logger.error(f"[PN532 USB] Wakeup failed: {e}")
        return False

    def _sam_configure(self) -> bool:
        """Set SAM to normal mode."""
        resp = self._send_command([0x14, 0x01, 0x00, 0x00], timeout=1.0)
        return resp is not None and b'\xD5\x15' in resp

    # ----------------------------------------------------------
    # Tag operations
    # ----------------------------------------------------------

    def _detect_tag(self, timeout: float = 0.3) -> Optional[bytes]:
        """InListPassiveTarget — returns raw response or None."""
        return self._send_command([0x4A, 0x01, 0x00], timeout=timeout)

    def _parse_uid(self, resp: bytes) -> Optional[bytes]:
        """Extract UID bytes from InListPassiveTarget response."""
        idx = resp.find(b'\xD5\x4B')
        if idx < 0:
            return None
        try:
            n_tags = resp[idx + 2]
            if n_tags == 0:
                return None
            uid_len = resp[idx + 7]
            uid = resp[idx + 8: idx + 8 + uid_len]
            return uid if len(uid) == uid_len else None
        except IndexError:
            return None

    def _read_page(self, page: int) -> Optional[bytes]:
        """Read 4 pages (16 bytes) starting at `page` via InDataExchange."""
        resp = self._send_command([0x40, 0x01, 0x30, page], timeout=0.5)
        if not resp:
            return None
        idx = resp.find(b'\xD5\x41')
        if idx < 0:
            return None
        if resp[idx + 2] != 0x00:  # error byte
            return None
        data = resp[idx + 3: idx + 19]
        return data if len(data) == 16 else None

    def _write_page(self, page: int, data_4bytes: bytes) -> bool:
        """Write 4 bytes to a single NTAG page via InDataExchange."""
        if len(data_4bytes) != 4:
            return False
        resp = self._send_command(
            [0x40, 0x01, 0xA2, page] + list(data_4bytes), timeout=0.5
        )
        return resp is not None and b'\xD5\x41\x00' in resp

    def _read_product_data(self) -> Optional[str]:
        """Read product string from NTAG215 user pages (4+)."""
        raw = bytearray()
        for page in range(USER_PAGE_START, USER_PAGE_START + 44, 4):
            data = self._read_page(page)
            if data is None:
                break
            raw.extend(data)
            if 0x00 in data:
                break

        if not raw:
            return None

        try:
            text = raw.split(b'\x00')[0].decode('ascii', errors='ignore')
            # Find product pattern: CODE|BATCH|NAME|COLOR
            if PRODUCT_SEPARATOR in text:
                parts = text.split(PRODUCT_SEPARATOR)
                if len(parts) >= 4:
                    return text
                # Try finding pattern within text (skip NDEF headers)
                for i in range(len(text)):
                    sub = text[i:]
                    segs = sub.split(PRODUCT_SEPARATOR)
                    if len(segs) >= 4 and len(segs[0]) > 0:
                        return sub
        except Exception:
            pass
        return None

    def write_product_data(self, product_string: str) -> bool:
        """Write product data to a tag currently on the reader.

        Format: CODE|BATCH|NAME|COLOR
        Returns True if write succeeded.
        Call after poll_tags() has detected a tag (tag must still be present).
        """
        with self._lock:
            # Detect tag first
            resp = self._detect_tag(timeout=2.0)
            if not resp or not self._parse_uid(resp):
                logger.warning("[PN532 USB] No tag present for write")
                return False

            data = product_string.encode('ascii')
            page = USER_PAGE_START
            for i in range(0, len(data), 4):
                chunk = data[i:i + 4]
                if len(chunk) < 4:
                    chunk = chunk + b'\x00' * (4 - len(chunk))
                if not self._write_page(page, chunk):
                    logger.error(f"[PN532 USB] Write failed at page {page}")
                    return False
                page += 1

            # Write null terminator page
            self._write_page(page, b'\x00\x00\x00\x00')

            logger.info(f"[PN532 USB] Wrote {len(data)} bytes to pages {USER_PAGE_START}-{page}")
            return True

    # ----------------------------------------------------------
    # HAL Interface implementation
    # ----------------------------------------------------------

    def initialize(self) -> bool:
        if not HAS_SERIAL:
            logger.warning("[PN532 USB] pyserial not available")
            self._initialized = False
            return False

        with self._lock:
            if not self._open_serial():
                return False
            if not self._wakeup():
                self._close_serial()
                return False
            if not self._sam_configure():
                self._close_serial()
                return False

        self._initialized = True
        logger.info(f"[PN532 USB] Initialized on {self._port}")
        return True

    def poll_tags(self) -> List[TagReading]:
        if not self._initialized:
            return []

        with self._lock:
            try:
                resp = self._detect_tag(timeout=0.3)
                if not resp:
                    return []

                uid_bytes = self._parse_uid(resp)
                if not uid_bytes:
                    return []

                tag_id = ":".join(f"{b:02X}" for b in uid_bytes)

                # Read product data
                product_data = self._read_product_data()
                parsed = {}
                if product_data:
                    parts = product_data.split(PRODUCT_SEPARATOR)
                    if len(parts) >= 4:
                        parsed = {
                            'ppg_code': parts[0],
                            'batch_number': parts[1],
                            'product_name': parts[2],
                            'color': parts[3],
                        }

                return [TagReading(
                    tag_id=tag_id,
                    reader_id=self._reader_ids[0],
                    signal_strength=90,
                    timestamp=time.time(),
                    product_data=product_data,
                    ppg_code=parsed.get('ppg_code'),
                    batch_number=parsed.get('batch_number'),
                    product_name=parsed.get('product_name'),
                    color=parsed.get('color'),
                )]

            except Exception as e:
                now = time.time()
                if now - self._last_error_time > 10:
                    logger.error(f"[PN532 USB] Poll error: {e}")
                    self._last_error_time = now
                # Try to reconnect on serial errors
                if not self._ser or not self._ser.is_open:
                    self._try_reconnect()
                return []

    def _try_reconnect(self):
        """Attempt to reconnect after USB disconnect."""
        logger.info("[PN532 USB] Attempting reconnect...")
        self._close_serial()
        if self._open_serial() and self._wakeup() and self._sam_configure():
            logger.info("[PN532 USB] Reconnected successfully")
        else:
            self._initialized = False

    def get_reader_ids(self) -> List[str]:
        return list(self._reader_ids)

    def is_healthy(self) -> bool:
        if not self._initialized or not self._ser:
            return False
        try:
            return self._ser.is_open
        except Exception:
            return False

    def shutdown(self) -> None:
        with self._lock:
            self._close_serial()
        self._initialized = False
        logger.info("[PN532 USB] Shutdown")
