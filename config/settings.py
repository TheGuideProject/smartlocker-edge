"""
SmartLocker Edge - Configuration Settings

MODE controls the entire system behavior:
  "test" = simulated sensors (runs on any laptop, no hardware needed)
  "live" = real sensors (runs on Raspberry Pi with physical hardware)

Change MODE to switch between simulated and real hardware.
All business logic (mixing, inventory, events) is IDENTICAL in both modes.
"""

# ============================================================
# SYSTEM MODE
# ============================================================
MODE = "test"  # "test" or "live"

# ============================================================
# DEVICE IDENTITY
# ============================================================
DEVICE_ID = "LOCKER-DEV-001"
VESSEL_NAME = "Test Vessel"
VESSEL_IMO = "0000000"

# ============================================================
# SENSOR POLLING RATES
# ============================================================
RFID_POLL_INTERVAL_MS = 500       # How often to check RFID readers (milliseconds)
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
# SYNC CONFIGURATION
# ============================================================
SYNC_ENABLED = False            # Disable sync for early development
SYNC_BATCH_SIZE = 50            # Max events per sync batch
SYNC_INTERVAL_S = 30            # Seconds between sync attempts
SYNC_RETRY_MAX = 7              # Max retry attempts before marking failed
MQTT_BROKER_URL = ""            # Fill in when cloud is ready
MQTT_PORT = 443
MQTT_USE_WSS = True

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
# HARDWARE PINS (LIVE mode only, ignored in TEST mode)
# ============================================================
RFID_I2C_BUS = 1
RFID_I2C_ADDRESSES = [0x24]     # PN532 default I2C address

ARDUINO_SERIAL_PORT = "/dev/ttyUSB0"  # Arduino Nano USB serial
ARDUINO_BAUD_RATE = 115200

LED_SPI_BUS = 0
LED_SPI_DEVICE = 0
LED_COUNT = 12                   # Total LEDs in strip

BUZZER_GPIO_PIN = 18             # PWM-capable GPIO pin

# ============================================================
# LOGGING
# ============================================================
LOG_LEVEL = "DEBUG" if MODE == "test" else "INFO"
LOG_DIR = "logs"
