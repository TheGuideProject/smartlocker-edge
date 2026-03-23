"""
Real RFID Driver - RC522 (MFRC522) NFC/RFID Reader via SPI

Reads NTAG215 tags: UID + product data (PPG_CODE/BATCH/PRODUCT_NAME/COLOR).

Hardware: SDA→GPIO8, SCK→GPIO11, MOSI→GPIO10, MISO→GPIO9, RST→GPIO25, 3.3V, GND

Graceful fallback on Windows/non-RPi.
"""

import logging
import time
from typing import List, Optional

from hal.interfaces import RFIDDriverInterface, TagReading

logger = logging.getLogger("smartlocker.sensor")

try:
    from mfrc522 import SimpleMFRC522
    import RPi.GPIO as GPIO
    HAS_RC522 = True
except ImportError:
    HAS_RC522 = False
    SimpleMFRC522 = None  # type: ignore[assignment, misc]
    logger.warning("[REAL RFID] mfrc522 library not installed.")

USER_PAGE_START = 4


class RealRFIDDriverRC522(RFIDDriverInterface):
    """RC522 RFID driver — reads NTAG215 UID + product data via SPI."""

    def __init__(self):
        self._reader = None
        self._rdr = None
        self._initialized = False
        self._reader_ids = ["shelf1_slot1", "shelf1_slot2", "shelf1_slot3", "shelf1_slot4"]

    def initialize(self) -> bool:
        if not HAS_RC522:
            self._initialized = False
            return False
        try:
            self._reader = SimpleMFRC522()
            self._rdr = self._reader.READER
            self._initialized = True
            logger.info("[REAL RFID] RC522 initialized via SPI")
            return True
        except Exception as e:
            logger.error(f"[REAL RFID] Init failed: {e}")
            self._initialized = False
            return False

    def _ntag_read_page(self, page):
        """Read 16 bytes (4 pages) from NTAG215 using manual CRC."""
        rdr = self._rdr
        if not rdr:
            return None

        try:
            # Disable CRC on RX
            rdr.Write_MFRC522(0x13, 0x00)

            # Calculate CRC_A for READ command
            rdr.Write_MFRC522(0x01, 0x00)  # Idle
            rdr.Write_MFRC522(0x05, 0x04)  # Clear DivIrq
            rdr.Write_MFRC522(0x0A, 0x80)  # Flush FIFO
            rdr.Write_MFRC522(0x09, 0x30)  # READ cmd
            rdr.Write_MFRC522(0x09, page)  # Page number
            rdr.Write_MFRC522(0x01, 0x03)  # CalcCRC

            time.sleep(0.05)

            crc_lo = rdr.Read_MFRC522(0x22)
            crc_hi = rdr.Read_MFRC522(0x21)

            buf = [0x30, page, crc_lo, crc_hi]
            (status, recv, _) = rdr.MFRC522_ToCard(rdr.PCD_TRANSCEIVE, buf)

            if status == rdr.MI_OK and recv and len(recv) >= 16:
                return recv[:16]
        except Exception as e:
            logger.debug(f"[REAL RFID] Read page {page} error: {e}")

        return None

    def _read_product_data(self) -> Optional[str]:
        """Read product data string from NTAG215 user pages."""
        raw = bytearray()

        for page in range(USER_PAGE_START, USER_PAGE_START + 32, 4):
            data = self._ntag_read_page(page)
            if data is None:
                break
            raw.extend(data)
            if 0x00 in data:
                break

        if not raw:
            return None

        try:
            text = raw.decode('latin-1')
            # Find PPG_CODE/BATCH/NAME/COLOR pattern (skip NDEF header if present)
            for i in range(len(text)):
                remaining = text[i:]
                if '/' in remaining:
                    parts = remaining.split('\x00')[0]
                    segments = parts.split('/')
                    if len(segments) >= 4 and len(segments[0]) > 0:
                        return parts
        except Exception:
            pass

        return None

    @staticmethod
    def _parse_product(text: str) -> dict:
        parts = text.split('/')
        if len(parts) >= 4:
            return {
                'ppg_code': parts[0],
                'batch_number': parts[1],
                'product_name': parts[2],
                'color': parts[3],
            }
        return {}

    def poll_tags(self) -> List[TagReading]:
        if not self._initialized or not HAS_RC522 or not self._rdr:
            return []

        try:
            rdr = self._rdr
            (status, _) = rdr.MFRC522_Request(rdr.PICC_REQIDL)
            if status != rdr.MI_OK:
                return []

            (status, uid_bytes) = rdr.MFRC522_Anticoll()
            if status != rdr.MI_OK:
                return []

            rdr.MFRC522_SelectTag(uid_bytes)
            rdr.MFRC522_StopCrypto1()

            tag_id = ":".join(f"{b:02X}" for b in uid_bytes if b != 0)

            # Read product data from NTAG pages
            product_data = self._read_product_data()
            parsed = self._parse_product(product_data) if product_data else {}

            return [TagReading(
                tag_id=tag_id,
                reader_id=self._reader_ids[0],
                signal_strength=80,
                timestamp=time.time(),
                product_data=product_data,
                ppg_code=parsed.get('ppg_code'),
                batch_number=parsed.get('batch_number'),
                product_name=parsed.get('product_name'),
                color=parsed.get('color'),
            )]

        except Exception as e:
            logger.error(f"[REAL RFID] Poll error: {e}")
            return []

    def get_reader_ids(self) -> List[str]:
        return list(self._reader_ids)

    def is_healthy(self) -> bool:
        return self._initialized and HAS_RC522

    def shutdown(self) -> None:
        if HAS_RC522 and self._initialized:
            try:
                GPIO.cleanup()
            except Exception:
                pass
        self._reader = None
        self._rdr = None
        self._initialized = False
        logger.info("[REAL RFID] RC522 shutdown")
