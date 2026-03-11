"""
Real RFID Driver - PN532 NFC/RFID Reader via I2C

Connects to a PN532 NFC reader on the Raspberry Pi's I2C bus.
Reads ISO14443A (NTAG/Mifare) tags placed under paint cans.

Hardware setup:
  - PN532 board wired to RPi I2C (SDA=GPIO2, SCL=GPIO3)
  - Set PN532 DIP switches to I2C mode (typically: SEL0=ON, SEL1=OFF)
  - Default I2C address: 0x24

Required library (install on RPi):
  pip install adafruit-circuitpython-pn532
  pip install adafruit-blinka

Graceful fallback: if adafruit_pn532/board/busio are not installed (e.g., on
Windows or a dev machine), all methods log warnings and return safely without
crashing.
"""

import logging
import time
from typing import List, Optional

from hal.interfaces import RFIDDriverInterface, TagReading

logger = logging.getLogger("smartlocker.sensor")

# ---------- Graceful import with fallback ----------
try:
    import board
    import busio
    from adafruit_pn532.i2c import PN532_I2C
    HAS_PN532 = True
except ImportError:
    HAS_PN532 = False
    board = None  # type: ignore[assignment, misc]
    busio = None  # type: ignore[assignment, misc]
    PN532_I2C = None  # type: ignore[assignment, misc]
    logger.warning(
        "[REAL RFID] adafruit_pn532 / board / busio libraries not installed. "
        "RFID reader will be non-functional. Install with: "
        "pip install adafruit-circuitpython-pn532 adafruit-blinka"
    )


class RealRFIDDriver(RFIDDriverInterface):
    """
    Real PN532 NFC/RFID driver over I2C.

    Reads NFC tags (ISO14443A) that are attached to paint can bottoms.
    Each slot on the shelf has one reader position; this driver polls
    the single PN532 module and returns any detected tag UIDs.
    """

    def __init__(self):
        from config.settings import RFID_I2C_BUS, RFID_I2C_ADDRESS
        self._i2c_bus = RFID_I2C_BUS
        self._i2c_address = RFID_I2C_ADDRESS
        self._pn532 = None
        self._i2c = None
        self._initialized = False
        self._reader_ids = ["shelf1_slot1", "shelf1_slot2", "shelf1_slot3", "shelf1_slot4"]

    def initialize(self) -> bool:
        """
        Connect to the PN532 over I2C.
        Returns True if the reader is detected and firmware version is read.
        Returns False (with a logged warning) if hardware or library is not available.
        """
        if not HAS_PN532:
            logger.warning(
                "[REAL RFID] Cannot initialize: adafruit_pn532 library not available. "
                "All RFID operations will return empty results."
            )
            self._initialized = False
            return False

        try:
            self._i2c = busio.I2C(board.SCL, board.SDA)
            self._pn532 = PN532_I2C(self._i2c, address=self._i2c_address, debug=False)

            # Check firmware version to confirm communication
            fw = self._pn532.firmware_version
            logger.info(f"[REAL RFID] PN532 found! Firmware: {fw[0]}.{fw[1]}")

            # Configure to read ISO14443A (Mifare/NTAG) tags
            self._pn532.SAM_configuration()

            self._initialized = True
            return True

        except Exception as e:
            logger.error(f"[REAL RFID] Failed to initialize PN532: {e}")
            self._initialized = False
            return False

    def poll_tags(self) -> List[TagReading]:
        """
        Poll the PN532 for NFC tags.
        Returns a list of TagReading for each detected tag.
        Returns empty list if no tag is present, hardware error,
        or library not available.
        """
        if not self._initialized or not HAS_PN532:
            if not HAS_PN532 and self._initialized:
                logger.warning("[REAL RFID] No-op poll_tags(): library not available")
            return []

        try:
            # Read with a short timeout (don't block the polling loop)
            uid = self._pn532.read_passive_target(timeout=0.1)

            if uid is not None:
                # Convert UID bytes to hex string (e.g., "04:A2:F3:1B:22:80")
                tag_id = ":".join(f"{b:02X}" for b in uid)
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
        """Return True if the PN532 is initialized and responding."""
        if not self._initialized or not HAS_PN532:
            return False

        try:
            fw = self._pn532.firmware_version
            return fw is not None
        except Exception:
            return False

    def shutdown(self) -> None:
        """Release I2C resources."""
        if self._i2c is not None:
            try:
                self._i2c.deinit()
            except Exception:
                pass
        self._pn532 = None
        self._i2c = None
        self._initialized = False
        logger.info("[REAL RFID] Shutdown")
