#!/bin/bash
# Flash Arduino Nano firmware from RPi
#
# Usage:
#   ./scripts/flash_arduino.sh                    # auto-detect port
#   ./scripts/flash_arduino.sh /dev/ttyUSB0       # explicit port
#
# Prerequisites:
#   sudo apt install avrdude arduino-cli
#
# The script:
#   1. Compiles the .ino to .hex using arduino-cli
#   2. Flashes the Arduino Nano via avrdude
#   3. Waits for Arduino to reboot and sends ping to verify

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FIRMWARE_DIR="$PROJECT_DIR/firmware/smartlocker_nano"
SKETCH="$FIRMWARE_DIR/smartlocker_nano.ino"
BUILD_DIR="/tmp/smartlocker_arduino_build"

# Auto-detect port or use argument
PORT="${1:-$(ls /dev/ttyUSB* 2>/dev/null | head -1)}"
if [ -z "$PORT" ]; then
    echo "ERROR: No Arduino found. Connect it via USB."
    exit 1
fi
echo "=== SmartLocker Arduino Flash ==="
echo "Port: $PORT"
echo "Sketch: $SKETCH"

# Check if arduino-cli is installed
if command -v arduino-cli &>/dev/null; then
    echo "Using arduino-cli to compile..."

    # Install core if needed
    arduino-cli core list 2>/dev/null | grep -q "arduino:avr" || \
        arduino-cli core install arduino:avr

    # Install libraries if needed
    arduino-cli lib list 2>/dev/null | grep -q "HX711" || \
        arduino-cli lib install "HX711"
    arduino-cli lib list 2>/dev/null | grep -q "ArduinoJson" || \
        arduino-cli lib install "ArduinoJson"

    # Compile
    echo "Compiling..."
    arduino-cli compile \
        --fqbn arduino:avr:nano:cpu=atmega328old \
        --output-dir "$BUILD_DIR" \
        "$FIRMWARE_DIR"

    HEX_FILE="$BUILD_DIR/smartlocker_nano.ino.hex"

    if [ ! -f "$HEX_FILE" ]; then
        # Try alternative naming
        HEX_FILE="$BUILD_DIR/smartlocker_nano.ino.with_bootloader.hex"
    fi

    echo "Flashing $HEX_FILE..."
    avrdude -p atmega328p -c arduino -P "$PORT" -b 57600 \
        -U flash:w:"$HEX_FILE":i

elif [ -f "$FIRMWARE_DIR/smartlocker_nano.hex" ]; then
    # Pre-compiled hex file in repo
    echo "Using pre-compiled .hex file..."
    HEX_FILE="$FIRMWARE_DIR/smartlocker_nano.hex"

    avrdude -p atmega328p -c arduino -P "$PORT" -b 57600 \
        -U flash:w:"$HEX_FILE":i
else
    echo "ERROR: No arduino-cli found and no pre-compiled .hex file."
    echo "Install arduino-cli:  curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh"
    echo "Or compile on Windows and copy the .hex file to: $FIRMWARE_DIR/smartlocker_nano.hex"
    exit 1
fi

echo ""
echo "Flash complete! Waiting for Arduino to reboot..."
sleep 3

# Verify with ping
echo '{"cmd":"ping"}' > "$PORT"
sleep 1
RESPONSE=$(timeout 3 cat "$PORT" 2>/dev/null || true)
if echo "$RESPONSE" | grep -q '"status":"ok"'; then
    echo "Arduino responding! Firmware update successful."
else
    echo "WARNING: No ping response (may need manual verification)"
fi

echo "=== Done ==="
