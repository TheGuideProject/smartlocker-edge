"""
SmartLocker Edge - Configuration Settings

MODE controls the entire system behavior:
  "test" = simulated sensors (runs on any laptop, no hardware needed)
  "live" = real sensors (runs on Raspberry Pi with physical hardware)

Change MODE to switch between simulated and real hardware.
All business logic (mixing, inventory, events) is IDENTICAL in both modes.
"""

# ============================================================
# SYSTEM MODE (legacy - kept for backward compatibility)
# ============================================================
# NOTE: MODE is now derived from the per-sensor DRIVER_* settings below.
# If you set MODE explicitly to "test", ALL drivers will be forced to "fake".
# If you set MODE to "live", ALL drivers will be forced to "real".
# Set MODE to "auto" (default) to use the per-sensor DRIVER_* settings.
MODE = "auto"

# ============================================================
# DRIVER MODE - Per-sensor configuration
# ============================================================
# Each sensor can be independently set to "fake" or "real".
# This allows progressive hardware integration & testing:
#   - Start with all "fake" (pure software testing on any laptop)
#   - Switch one sensor to "real" when it arrives (e.g., RFID first)
#   - Keep the others as "fake" until you're ready
#   - When all are "real", the system runs in full LIVE mode
#
# The overall system mode is determined automatically:
#   all fake  -> "test" mode
#   mixed     -> "hybrid" mode
#   all real  -> "live" mode
# ============================================================
DRIVER_RFID = "real"       # "fake" or "real"
RFID_MODULE = "pn532_multi_usb"  # "pn532_multi_usb" (N readers via USB hub) or "pn532_usb" (single) or "rc522" (SPI) or "pn532" (I2C)
RFID_USB_PORT = "/dev/serial/by-path/platform-xhci-hcd.0-usb-0:1.3:1.0-port0"  # PN532 slot1 (stable path)

# Multi-reader config: list of {port, reader_id} pairs.
# Using /dev/serial/by-path/ symlinks so ports survive reboot.
# Empty list = auto-detect all CH340/CP210x ports (excluding Arduino).
RFID_READER_MAP = [
    {"port": "/dev/serial/by-path/platform-xhci-hcd.0-usb-0:1.3:1.0-port0",   "reader_id": "shelf1_slot1"},
    {"port": "/dev/serial/by-path/platform-xhci-hcd.0-usb-0:1.4.1:1.0-port0", "reader_id": "shelf1_slot2"},
    {"port": "/dev/serial/by-path/platform-xhci-hcd.0-usb-0:1.4.2:1.0-port0", "reader_id": "shelf1_slot3"},
    {"port": "/dev/serial/by-path/platform-xhci-hcd.0-usb-0:1.4.3:1.0-port0", "reader_id": "shelf1_slot4"},
]
DRIVER_WEIGHT = "real"     # "fake" or "real" - Arduino serial bridge
DRIVER_LED = "real"        # "fake" or "real" - Bar graph + shelf LEDs via Arduino
DRIVER_BUZZER = "real"     # "fake" or "real" - GPIO PWM buzzer on GPIO 13

# ============================================================
# DEVICE IDENTITY
# ============================================================
DEVICE_ID = "LOCKER-DEV-001"
VESSEL_NAME = "Test Vessel"
VESSEL_IMO = "0000000"

# ============================================================
# SENSOR POLLING RATES
# ============================================================
RFID_POLL_INTERVAL_MS = 2000      # How often to check RFID readers (2s — CH340 bridge needs slower polling)
WEIGHT_POLL_INTERVAL_MS = 200     # How often to read weight sensors
WEIGHT_STABLE_WINDOW_S = 3.0     # Seconds of stable readings before considering weight "settled"
WEIGHT_STABLE_TOLERANCE_G = 10   # Grams tolerance for "stable" weight

# ============================================================
# INVENTORY THRESHOLDS
# ============================================================
CAN_REMOVAL_TIMEOUT_S = 4 * 3600       # 4 hours: if can not returned, mark as "in use"
CAN_REMOVAL_CONSUMED_TIMEOUT_S = 12 * 3600  # 12 hours: mark as consumed
WEIGHT_CHANGE_MIN_G = 30                # Minimum weight change to register as an event
STOCK_LOW_THRESHOLD_PCT = 25            # Below 25% = low stock alert
STOCK_CRITICAL_THRESHOLD_PCT = 10       # Below 10% = critical stock alert

# ============================================================
# MIXING PARAMETERS
# ============================================================
MIX_RATIO_TOLERANCE_PCT = 5.0   # ±5% tolerance on base:hardener ratio
MIX_WEIGHT_STABLE_S = 2.0      # Seconds of stable weight before confirming pour
THINNER_MAX_PCT = 20.0          # Maximum thinner percentage allowed

# ============================================================
# CLOUD SYNC CONFIGURATION
# ============================================================
CLOUD_URL = "https://web-production-34fe1.up.railway.app"  # Fixed cloud backend URL
CLOUD_API_KEY = ""              # Set after pairing (slk_xxx token from cloud)
CLOUD_DEVICE_UUID = ""          # Cloud's internal UUID for this device
CLOUD_PAIRED = False            # True after successful pairing
CLOUD_PAIRING_FILE = "data/cloud_pairing.json"  # Persistent pairing config

SYNC_ENABLED = False            # Auto-enabled after pairing
SYNC_BATCH_SIZE = 50            # Max events per sync batch
SYNC_INTERVAL_S = 30            # Seconds between sync attempts (30s — catch short connectivity windows)
SYNC_RETRY_MAX = 7              # Max retry attempts before marking failed
HEARTBEAT_INTERVAL_S = 30      # Seconds between heartbeat pings

# ============================================================
# DATABASE
# ============================================================
DB_PATH = "data/smartlocker.db"

# ============================================================
# UI SETTINGS
# ============================================================
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 480              # 4.3" DSI display native resolution
BUTTON_MIN_SIZE_PX = 60          # Minimum touch target for gloved hands
FONT_SIZE_LABEL = 18
FONT_SIZE_HEADING = 24

# ============================================================
# REAL HARDWARE CONFIG (used when a DRIVER_* is set to "real")
# ============================================================

# RFID - PN532 via I2C
# Library: adafruit-circuitpython-pn532 (recommended) or pn532pi
RFID_I2C_BUS = 1                 # I2C bus number (usually 1 on RPi)
RFID_I2C_ADDRESS = 0x24          # Default PN532 I2C address
RFID_I2C_ADDRESSES = [0x24]     # List for multi-reader setups

# Weight - HX711 Direct GPIO (2 channels, no Arduino needed)
WEIGHT_MODE = "arduino_serial"        # "hx711_direct" or "arduino_serial"
HX711_SHELF_DT = 5                    # Shelf scale: GPIO pin for HX711 DOUT
HX711_SHELF_SCK = 6                   # Shelf scale: GPIO pin for HX711 SCK
HX711_MIX_DT = 23                     # Mixing scale: GPIO pin for HX711 DOUT
HX711_MIX_SCK = 24                    # Mixing scale: GPIO pin for HX711 SCK
HX711_SHELF_SCALE = 20.6660           # Shelf: raw units per gram (recalibrated 2026-04-03, pin-swapped)
HX711_MIX_SCALE = 10.4070            # Mixing: raw units per gram (recalibrated 2026-04-03, pin-swapped)
HX711_SCALE_FACTOR = HX711_SHELF_SCALE  # Legacy alias
# Legacy aliases (backward compat)
HX711_DT_PIN = HX711_SHELF_DT
HX711_SCK_PIN = HX711_SHELF_SCK

# Weight - Arduino Nano via Serial (HX711 bridge, for multi-channel setups)
# Protocol: Arduino sends JSON lines: {"channel":"shelf1","grams":1234.5,"stable":true}
WEIGHT_SERIAL_PORT = "/dev/serial/by-path/platform-xhci-hcd.1-usb-0:2:1.0-port0"  # Arduino (stable path)
WEIGHT_SERIAL_BAUD = 115200           # Baud rate
ARDUINO_SERIAL_PORT = ""              # Empty = auto-detect (legacy alias)
ARDUINO_BAUD_RATE = 115200            # Legacy alias (backward compat)

# LED Mode: "arduino_serial" (via Arduino), "ws2812b" (NeoPixel strip), "gpio" (individual red LEDs)
# When WEIGHT_MODE is "arduino_serial" AND LED_MODE is not set, LEDs go via Arduino.
# Set LED_MODE = "gpio" to use individual red LEDs wired directly to RPi GPIO pins.
LED_MODE = ""        # "" = auto (Arduino if WEIGHT_MODE=arduino_serial), "gpio" = direct RPi GPIO, "ws2812b" = NeoPixel

# LED Strip - WS2812B via SPI/PWM (only used when LED_MODE = "ws2812b")
LED_SPI_BUS = 0
LED_SPI_DEVICE = 0
LED_COUNT = 12                   # Total LEDs in strip (one per slot)
LED_GPIO_PIN = 18                # Data pin (must support PWM: 12, 13, 18, 19)
LED_BRIGHTNESS = 128             # 0-255 brightness level

# Individual Red LED GPIO pins (only used when LED_MODE = "gpio")
# Wiring: GPIO → 150Ω resistor → LED (+) → LED (−) → GND
# Add/remove entries to match your slot count.
LED_GPIO_SLOT_PINS = {
    "shelf1_slot1": 17,          # Pin 11
    "shelf1_slot2": 27,          # Pin 13
    "shelf1_slot3": 22,          # Pin 15
    "shelf1_slot4": 25,          # Pin 22
    # "shelf1_slot5": 12,        # Pin 32  (uncomment when wired)
    # "shelf1_slot6": 16,        # Pin 36  (uncomment when wired)
}

# Slot Configuration (cloud-configurable; default 4 for dev)
SLOT_COUNT = 4

# Buzzer - GPIO PWM
# Library: RPi.GPIO or gpiozero
BUZZER_GPIO_PIN = 13             # BCM pin 13 (PWM-capable). Moved from 18 to avoid conflict with LED_GPIO_PIN.

# ============================================================
# LOGGING
# ============================================================
# In auto mode, use DEBUG if all drivers are fake, otherwise INFO
if MODE == "test":
    LOG_LEVEL = "DEBUG"
elif MODE == "live":
    LOG_LEVEL = "INFO"
else:
    # auto mode: DEBUG when all fake, INFO when any real
    _any_real = any(d == "real" for d in [DRIVER_RFID, DRIVER_WEIGHT, DRIVER_LED, DRIVER_BUZZER])
    LOG_LEVEL = "INFO" if _any_real else "DEBUG"
LOG_DIR = "logs"

# ============================================================
# BACKUP SETTINGS
# ============================================================
BACKUP_INTERVAL_H = 6
BACKUP_MAX_COPIES = 5
BACKUP_DIR = "data/backups"

# ============================================================
# WEBSOCKET REAL-TIME SYNC
# ============================================================
WS_ENABLED = True                     # Enable WebSocket real-time sync
WS_RECONNECT_INITIAL_S = 2           # Initial reconnect delay (seconds)
WS_RECONNECT_MAX_S = 120             # Maximum reconnect delay (2 minutes)
WS_PING_INTERVAL_S = 25              # WebSocket keepalive ping interval
WS_FALLBACK_EVENT_INTERVAL_S = 120   # HTTP event sync interval when WS active (backup)
WS_FALLBACK_CONFIG_INTERVAL_S = 600  # HTTP config sync interval when WS active (backup)
