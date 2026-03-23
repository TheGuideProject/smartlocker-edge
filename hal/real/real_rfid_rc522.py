"""
Real RFID Driver - RC522 (MFRC522) NFC/RFID Reader via SPI

Connects to an RC522 RFID reader on the Raspberry Pi's SPI bus.
Reads ISO14443A (NTAG215) tags placed under paint cans.
Reads both UID and product data stored on the tag.

Tag data format: PPG_CODE/BATCH/PRODUCT_NAME/COLOR
Example: 616826/80008800/SIGMAPRIME-200/YELLOWGREEN

Hardware setup (RPi5):
  - SDA (SS)  → GPIO 8  (Pin 24, CE0)
  - SCK       → GPIO 11 (Pin 23)
  - MOSI      → GPIO 10 (Pin 19)
  - MISO      → GPIO 9  (Pin 21)
  - RST       → GPIO 25 (Pin 22)
  - GND       → Pin 6
  - 3.3V      → Pin 1   (NEVER 5V!)
  - IRQ       → Not connected

Required library (install on RPi):
  pip install mfrc522

Graceful fallback: if mfrc522 is not installed (e.g., on Windows),
all methods log warnings and return safely without crashing.
"""

import logging
import time
from typing import List, Optional

from hal.interfaces import RFIDDriverInterface, TagReading

logger = logging.getLogger("smartlocker.sensor")

# ---------- Graceful import with fallback ----------
try:
    from mfrc522 import SimpleMFRC522
    import RPi.GPIO as GPIO
    HAS_RC522 = True
except ImportError:
    HAS_RC522 = False
    SimpleMFRC522 = None  # type: ignore[assignment, misc]
    logger.warning(
        "[REAL RFID] mfrc522 library not installed. "
        "RFID reader will be non-functional. Install with: "
        "pip install mfrc522"
    )

# NTAG215 constants
NTAG_READ_CMD = 0x30
USER_PAGE_START = 4
USER_PAGE_END = 129


class RealRFIDDriverRC522(RFIDDriverInterface):
    """
    Real RC522 (MFRC522) RFID driver over SPI.

    Reads NFC tags (NTAG215) attached to paint can bottoms.
    Returns both UID and product data stored on the tag.
    """

    def __init__(self):
        self._reader = None
        self._rdr = None  # Low-level MFRC522
        self._initialized = False
        self._reader_ids = ["shelf1_slot1", "shelf1_slot2", "shelf1_slot3", "shelf1_slot4"]

    def initialize(self) -> bool:
        if not HAS_RC522:
            logger.warning(
                "[REAL RFID] Cannot initialize: mfrc522 library not available."
            )
            self._initialized = False
            return False

        try:
            self._reader = SimpleMFRC522()
            self._rdr = self._reader.READER
            self._initialized = True
            logger.info("[REAL RFID] RC522 initialized via SPI (GPIO 8 CE0)")
            return True
        except Exception as e:
            logger.error(f"[REAL RFID] Failed to initialize RC522: {e}")
            self._initialized = False
            return False

    def _ntag_read_data(self) -> Optional[str]:
        """Read product data from NTAG215 user pages (4+). Returns decoded string or None."""
        if not self._rdr:
            return None

        raw = bytearray()
        try:
            for page in range(USER_PAGE_START, min(USER_PAGE_START + 16, USER_PAGE_END)):
                # Read 4 pages at once (16 bytes)
                buf = [NTAG_READ_CMD, page]
                (status, data, _) = self._rdr.MFRC522_ToCard(
                    self._rdr.PCD_TRANSCEIVE, buf
                )
                if status != self._rdr.MI_OK or not data:
                    break
                raw.extend(data[:4])
                # Stop if null terminator found
                if 0x00 in data[:4]:
                    break

            if raw:
                text = raw.split(b'\x00')[0].decode('utf-8')
                return text if text else None
        except Exception as e:
            logger.debug(f"[REAL RFID] Could not read tag data: {e}")

        return None

    @staticmethod
    def _parse_product_data(text: str) -> dict:
        """Parse PPG_CODE/BATCH/PRODUCT_NAME/COLOR format."""
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
        """
        Poll the RC522 for NFC tags.
        Returns UID + product data if available.
        """
        if not self._initialized or not HAS_RC522 or not self._rdr:
            return []

        try:
            # Request tag presence
            (status, _) = self._rdr.MFRC522_Request(self._rdr.PICC_REQIDL)
            if status != self._rdr.MI_OK:
                return []

            # Anti-collision — get UID
            (status, uid_bytes) = self._rdr.MFRC522_Anticoll()
            if status != self._rdr.MI_OK:
                return []

            # Select tag (required for reading data pages)
            self._rdr.MFRC522_SelectTag(uid_bytes)

            # Convert UID to hex string
            tag_id = ":".join(f"{b:02X}" for b in uid_bytes if b != 0)

            # Try to read product data from NTAG
            product_data = self._ntag_read_data()
            parsed = self._parse_product_data(product_data) if product_data else {}

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
