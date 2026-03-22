"""
Real RFID Driver - RC522 (MFRC522) NFC/RFID Reader via SPI

Connects to an RC522 RFID reader on the Raspberry Pi's SPI bus.
Reads ISO14443A (Mifare/NTAG) tags placed under paint cans.

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

SPI must be enabled:
  sudo raspi-config  →  Interface Options  →  SPI  →  Enable
  (or add "dtparam=spi=on" to /boot/config.txt)

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


class RealRFIDDriverRC522(RFIDDriverInterface):
    """
    Real RC522 (MFRC522) RFID driver over SPI.

    Reads NFC tags (ISO14443A / Mifare) attached to paint can bottoms.
    """

    def __init__(self):
        self._reader = None
        self._initialized = False
        self._reader_ids = ["shelf1_slot1", "shelf1_slot2", "shelf1_slot3", "shelf1_slot4"]

    def initialize(self) -> bool:
        """
        Initialize the RC522 reader via SPI.
        Returns True if the reader is ready.
        """
        if not HAS_RC522:
            logger.warning(
                "[REAL RFID] Cannot initialize: mfrc522 library not available. "
                "All RFID operations will return empty results."
            )
            self._initialized = False
            return False

        try:
            self._reader = SimpleMFRC522()
            self._initialized = True
            logger.info("[REAL RFID] RC522 initialized via SPI (GPIO 8 CE0)")
            return True
        except Exception as e:
            logger.error(f"[REAL RFID] Failed to initialize RC522: {e}")
            self._initialized = False
            return False

    def poll_tags(self) -> List[TagReading]:
        """
        Poll the RC522 for NFC tags.
        Returns a list with one TagReading if a tag is detected, empty list otherwise.

        Uses the low-level MFRC522 class for non-blocking reads.
        """
        if not self._initialized or not HAS_RC522:
            return []

        try:
            # Use the underlying MFRC522 for non-blocking operation
            rdr = self._reader.READER  # type: ignore

            # Request tag presence (REQIDL = idle tags)
            (status, _tag_type) = rdr.MFRC522_Request(rdr.PICC_REQIDL)

            if status != rdr.MI_OK:
                return []  # No tag present

            # Anti-collision — get UID
            (status, uid_bytes) = rdr.MFRC522_Anticoll()

            if status != rdr.MI_OK:
                return []  # Collision or error

            # Convert UID to hex string (e.g., "04:A2:F3:1B")
            tag_id = ":".join(f"{b:02X}" for b in uid_bytes if b != 0)

            return [TagReading(
                tag_id=tag_id,
                reader_id=self._reader_ids[0],  # Single reader for now
                signal_strength=80,
                timestamp=time.time(),
            )]

        except Exception as e:
            logger.error(f"[REAL RFID] Poll error: {e}")
            return []

    def get_reader_ids(self) -> List[str]:
        """Return configured reader slot IDs."""
        return list(self._reader_ids)

    def is_healthy(self) -> bool:
        """Return True if the RC522 is initialized."""
        return self._initialized and HAS_RC522

    def shutdown(self) -> None:
        """Release SPI/GPIO resources."""
        if HAS_RC522 and self._initialized:
            try:
                GPIO.cleanup()
            except Exception:
                pass
        self._reader = None
        self._initialized = False
        logger.info("[REAL RFID] RC522 shutdown")
