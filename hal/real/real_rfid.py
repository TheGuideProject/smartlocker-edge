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

Alternative library:
  pip install pn532pi

This is a STUB driver. Methods log warnings and return safe defaults
when the hardware is not connected, so the system never crashes.
Flesh out the TODOs when your PN532 arrives.
"""

import logging
import time
from typing import List

from hal.interfaces import RFIDDriverInterface, TagReading

logger = logging.getLogger("smartlocker.sensor")


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
        self._initialized = False
        self._reader_ids = ["shelf1_slot1", "shelf1_slot2", "shelf1_slot3", "shelf1_slot4"]

    def initialize(self) -> bool:
        """
        Connect to the PN532 over I2C.
        Returns True if the reader is detected and firmware version is read.
        Returns False (with a logged error) if hardware is not connected.
        """
        try:
            # TODO: Uncomment and adapt when PN532 hardware is connected
            # -------------------------------------------------------
            # import board
            # import busio
            # from adafruit_pn532.i2c import PN532_I2C
            #
            # i2c = busio.I2C(board.SCL, board.SDA)
            # self._pn532 = PN532_I2C(i2c, address=self._i2c_address, debug=False)
            #
            # # Check firmware version to confirm communication
            # fw = self._pn532.firmware_version
            # logger.info(f"[REAL RFID] PN532 found! Firmware: {fw[0]}.{fw[1]}")
            #
            # # Configure to read ISO14443A (Mifare/NTAG) tags
            # self._pn532.SAM_configuration()
            # -------------------------------------------------------

            logger.warning(
                "[REAL RFID] STUB: PN532 driver not yet implemented. "
                "Uncomment the initialization code when hardware is connected."
            )
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
        Returns empty list if no tag is present or hardware error.
        """
        if not self._initialized:
            return []

        try:
            # TODO: Uncomment when PN532 hardware is connected
            # -------------------------------------------------------
            # # Read with a short timeout (don't block the polling loop)
            # uid = self._pn532.read_passive_target(timeout=0.1)
            #
            # if uid is not None:
            #     # Convert UID bytes to hex string (e.g., "04:A2:F3:1B:22:80")
            #     tag_id = ":".join(f"{b:02X}" for b in uid)
            #     return [TagReading(
            #         tag_id=tag_id,
            #         reader_id=self._reader_ids[0],  # Single reader for now
            #         signal_strength=80,
            #         timestamp=time.time(),
            #     )]
            # -------------------------------------------------------
            pass

        except Exception as e:
            logger.error(f"[REAL RFID] Poll error: {e}")

        return []

    def get_reader_ids(self) -> List[str]:
        """Return configured reader slot IDs."""
        return list(self._reader_ids)

    def is_healthy(self) -> bool:
        """Return True if the PN532 is initialized and responding."""
        if not self._initialized:
            return False

        # TODO: Add a quick firmware version check to verify hardware health
        # try:
        #     fw = self._pn532.firmware_version
        #     return fw is not None
        # except Exception:
        #     return False

        return True

    def shutdown(self) -> None:
        """Release I2C resources."""
        self._pn532 = None
        self._initialized = False
        logger.info("[REAL RFID] Shutdown")
