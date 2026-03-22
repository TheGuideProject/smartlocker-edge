#!/usr/bin/env python3
"""
RC522 RFID Reader - Quick Test Script

Run on Raspberry Pi to verify RC522 wiring and tag reading.

Wiring:
  SDA  → GPIO 8  (Pin 24)
  SCK  → GPIO 11 (Pin 23)
  MOSI → GPIO 10 (Pin 19)
  MISO → GPIO 9  (Pin 21)
  RST  → GPIO 25 (Pin 22)
  GND  → Pin 6
  3.3V → Pin 1

Usage:
  python3 scripts/test_rc522.py
"""

import sys
import time

print("=" * 50)
print("  RC522 RFID Reader Test")
print("=" * 50)

# Step 1: Check SPI is enabled
print("\n[1] Checking SPI...")
try:
    import spidev
    spi = spidev.SpiDev()
    spi.open(0, 0)
    spi.close()
    print("    SPI OK")
except Exception as e:
    print(f"    SPI ERROR: {e}")
    print("    Fix: sudo raspi-config → Interface Options → SPI → Enable")
    print("    Then reboot: sudo reboot")
    sys.exit(1)

# Step 2: Check mfrc522 library
print("\n[2] Checking mfrc522 library...")
try:
    from mfrc522 import SimpleMFRC522
    print("    mfrc522 OK")
except ImportError:
    print("    mfrc522 NOT INSTALLED")
    print("    Fix: pip install mfrc522")
    sys.exit(1)

# Step 3: Initialize reader
print("\n[3] Initializing RC522 reader...")
try:
    import RPi.GPIO as GPIO
    reader = SimpleMFRC522()
    print("    Reader initialized OK")
except Exception as e:
    print(f"    INIT ERROR: {e}")
    print("    Check wiring!")
    sys.exit(1)

# Step 4: Read tags
print("\n[4] Ready to read tags!")
print("    Hold an NFC tag near the reader...")
print("    Press Ctrl+C to stop\n")

try:
    while True:
        # Use low-level MFRC522 for non-blocking read
        rdr = reader.READER

        # Request tag
        (status, tag_type) = rdr.MFRC522_Request(rdr.PICC_REQIDL)

        if status == rdr.MI_OK:
            # Anti-collision
            (status, uid) = rdr.MFRC522_Anticoll()

            if status == rdr.MI_OK:
                tag_id = ":".join(f"{b:02X}" for b in uid if b != 0)
                print(f"    TAG DETECTED: {tag_id}")
                print(f"    Raw UID bytes: {uid}")
                print(f"    Tag type: {tag_type}")
                print()
                time.sleep(1)  # Debounce

        time.sleep(0.1)  # Poll every 100ms

except KeyboardInterrupt:
    print("\n\nStopped by user.")
finally:
    GPIO.cleanup()
    print("GPIO cleaned up. Done!")
