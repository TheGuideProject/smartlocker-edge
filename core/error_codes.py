"""
Error Code Definitions for SmartLocker Edge.

Comprehensive error code system covering sensor, system, software,
inventory, and mixing error categories.

Each error code carries:
  - code:        Short identifier (e.g. "E001")
  - title:       Human-readable name
  - description: Detailed description of the error
  - severity:    "critical" | "warning" | "info"
  - category:    "sensor" | "system" | "software" | "inventory" | "mixing"
  - resolution:  Step-by-step resolution guidance

Usage:
    from core.error_codes import ErrorCode, get_error_by_code

    ec = ErrorCode.E001_RFID_DISCONNECTED
    print(ec.code)        # "E001"
    print(ec.severity)    # "critical"

    ec2 = get_error_by_code("E001")
    assert ec2 == ec
"""

from enum import Enum
from typing import Optional


class ErrorCode(Enum):
    """All error codes in the SmartLocker system."""

    # The value tuple is:
    # (code, title, description, severity, category, resolution)

    # ================================================================
    # SENSOR ERRORS (E001 - E019)
    # ================================================================

    E001_RFID_DISCONNECTED = (
        "E001",
        "RFID Disconnected",
        "RFID reader not responding",
        "critical",
        "sensor",
        "Check USB connection, restart device",
    )

    E002_RFID_READ_ERROR = (
        "E002",
        "RFID Read Error",
        "RFID intermittent read failure",
        "warning",
        "sensor",
        "Clean reader, check antenna",
    )

    E003_RFID_MULTIPLE_TAGS = (
        "E003",
        "RFID Multiple Tags",
        "Multiple tags detected on single slot",
        "warning",
        "sensor",
        "Remove extra tags",
    )

    E004_WEIGHT_DISCONNECTED = (
        "E004",
        "Weight Sensor Disconnected",
        "Weight sensor (HX711/Arduino) not responding",
        "critical",
        "sensor",
        "Check serial connection",
    )

    E005_WEIGHT_OUT_OF_RANGE = (
        "E005",
        "Weight Out of Range",
        "Weight reading outside valid range",
        "warning",
        "sensor",
        "Recalibrate, check load cell",
    )

    E006_WEIGHT_DRIFT = (
        "E006",
        "Weight Drift",
        "Weight readings drifting over time",
        "warning",
        "sensor",
        "Recalibrate sensor",
    )

    E007_WEIGHT_OVERLOAD = (
        "E007",
        "Weight Overload",
        "Weight exceeds max capacity",
        "warning",
        "sensor",
        "Remove excess weight",
    )

    E008_LED_DRIVER_ERROR = (
        "E008",
        "LED Driver Error",
        "LED strip communication failure",
        "warning",
        "sensor",
        "Check wiring",
    )

    E009_BUZZER_ERROR = (
        "E009",
        "Buzzer Error",
        "Buzzer not responding",
        "info",
        "sensor",
        "Check connection",
    )

    E010_SENSOR_INIT_FAILED = (
        "E010",
        "Sensor Init Failed",
        "Sensor failed to initialize at boot",
        "critical",
        "sensor",
        "Restart device",
    )

    # ================================================================
    # SYSTEM ERRORS (E020 - E039)
    # ================================================================

    E020_CPU_OVERTEMP = (
        "E020",
        "CPU Over-Temperature",
        "CPU temperature above 80°C",
        "critical",
        "system",
        "Check cooling fan, ventilation",
    )

    E021_CPU_HIGH_TEMP = (
        "E021",
        "CPU High Temperature",
        "CPU temperature above 70°C",
        "warning",
        "system",
        "Improve ventilation",
    )

    E022_CPU_THROTTLING = (
        "E022",
        "CPU Throttling",
        "CPU is being throttled",
        "warning",
        "system",
        "Improve cooling",
    )

    E023_RAM_CRITICAL = (
        "E023",
        "RAM Critical",
        "RAM usage above 90%",
        "critical",
        "system",
        "Restart device",
    )

    E024_RAM_HIGH = (
        "E024",
        "RAM High",
        "RAM usage above 80%",
        "warning",
        "system",
        "Close unused processes",
    )

    E025_DISK_FULL = (
        "E025",
        "Disk Full",
        "SD card storage above 95%",
        "critical",
        "system",
        "Clean logs, contact support",
    )

    E026_DISK_HIGH = (
        "E026",
        "Disk High",
        "SD card storage above 85%",
        "warning",
        "system",
        "Clean old data",
    )

    E027_SD_CARD_ERROR = (
        "E027",
        "SD Card Error",
        "SD card I/O errors detected",
        "critical",
        "system",
        "Replace SD card immediately",
    )

    E028_SD_CARD_READONLY = (
        "E028",
        "SD Card Read-Only",
        "SD card mounted read-only",
        "critical",
        "system",
        "Replace SD card",
    )

    E029_SYSTEM_CLOCK_ERROR = (
        "E029",
        "System Clock Error",
        "System clock not synchronized",
        "warning",
        "system",
        "Check NTP",
    )

    E030_POWER_UNSTABLE = (
        "E030",
        "Power Unstable",
        "Voltage fluctuations detected",
        "warning",
        "system",
        "Check power supply",
    )

    # ================================================================
    # SOFTWARE ERRORS (E040 - E059)
    # ================================================================

    E040_DATABASE_ERROR = (
        "E040",
        "Database Error",
        "SQLite database corrupted or locked",
        "critical",
        "software",
        "Restart, contact support",
    )

    E041_DATABASE_FULL = (
        "E041",
        "Database Full",
        "Database file too large",
        "warning",
        "software",
        "Purge old data",
    )

    E042_SYNC_FAILED = (
        "E042",
        "Sync Failed",
        "Cloud sync failed repeatedly",
        "warning",
        "software",
        "Check network",
    )

    E043_SYNC_QUEUE_FULL = (
        "E043",
        "Sync Queue Full",
        "Too many unsynced events",
        "warning",
        "software",
        "Check connectivity",
    )

    E044_OTA_UPDATE_FAILED = (
        "E044",
        "OTA Update Failed",
        "Firmware update failed",
        "warning",
        "software",
        "Retry or contact support",
    )

    E045_CONFIG_CORRUPT = (
        "E045",
        "Config Corrupt",
        "Configuration file corrupted",
        "critical",
        "software",
        "Reset to defaults",
    )

    E046_MEMORY_LEAK = (
        "E046",
        "Memory Leak",
        "Process memory growing abnormally",
        "warning",
        "software",
        "Restart device",
    )

    E047_WATCHDOG_TIMEOUT = (
        "E047",
        "Watchdog Timeout",
        "Process not responding",
        "critical",
        "software",
        "Auto-restart",
    )

    # ================================================================
    # INVENTORY ERRORS (E060 - E079)
    # ================================================================

    E060_UNAUTHORIZED_REMOVAL = (
        "E060",
        "Unauthorized Removal",
        "Can removed without active session",
        "critical",
        "inventory",
        "Investigate immediately",
    )

    E061_WRONG_SLOT_RETURN = (
        "E061",
        "Wrong Slot Return",
        "Can returned to wrong slot",
        "warning",
        "inventory",
        "Guide crew to correct slot",
    )

    E062_MISSING_CAN = (
        "E062",
        "Missing Can",
        "Can not returned within timeout",
        "warning",
        "inventory",
        "Locate can",
    )

    E063_UNKNOWN_TAG = (
        "E063",
        "Unknown Tag",
        "Unregistered RFID tag detected",
        "info",
        "inventory",
        "Register tag in system",
    )

    E064_WEIGHT_MISMATCH = (
        "E064",
        "Weight Mismatch",
        "Can weight doesn't match expected",
        "warning",
        "inventory",
        "Verify can contents",
    )

    E065_STOCK_CRITICAL = (
        "E065",
        "Stock Critical",
        "Product stock critically low",
        "critical",
        "inventory",
        "Order immediately",
    )

    E066_STOCK_LOW = (
        "E066",
        "Stock Low",
        "Product stock below threshold",
        "warning",
        "inventory",
        "Plan reorder",
    )

    # ================================================================
    # MIXING ERRORS (E080 - E099)
    # ================================================================

    E080_MIX_OUT_OF_SPEC = (
        "E080",
        "Mix Out of Spec",
        "Mix ratio outside tolerance",
        "warning",
        "mixing",
        "Adjust or accept with override",
    )

    E081_POT_LIFE_EXPIRED = (
        "E081",
        "Pot Life Expired",
        "Mixed paint pot-life expired",
        "critical",
        "mixing",
        "Dispose, do not use",
    )

    E082_POT_LIFE_WARNING = (
        "E082",
        "Pot Life Warning",
        "Pot-life at 75%+",
        "info",
        "mixing",
        "Use soon",
    )

    E083_MIX_ABORTED = (
        "E083",
        "Mix Aborted",
        "Mixing session aborted",
        "info",
        "mixing",
        "Investigate reason",
    )

    # ================================================================
    # Properties
    # ================================================================

    def __init__(self, code: str, title: str, description: str,
                 severity: str, category: str, resolution: str):
        self._code = code
        self._title = title
        self._description = description
        self._severity = severity
        self._category = category
        self._resolution = resolution

    @property
    def code(self) -> str:
        """Short error code string, e.g. 'E001'."""
        return self._code

    @property
    def title(self) -> str:
        """Human-readable error title."""
        return self._title

    @property
    def description(self) -> str:
        """Detailed error description."""
        return self._description

    @property
    def severity(self) -> str:
        """Severity level: 'critical', 'warning', or 'info'."""
        return self._severity

    @property
    def category(self) -> str:
        """Error category: 'sensor', 'system', 'software', 'inventory', 'mixing'."""
        return self._category

    @property
    def resolution(self) -> str:
        """Recommended resolution steps."""
        return self._resolution

    def __repr__(self) -> str:
        return f"ErrorCode.{self.name}({self._code}: {self._title} [{self._severity}])"


# ====================================================================
# HELPER FUNCTIONS
# ====================================================================

# Build lookup table: code string -> ErrorCode member
_CODE_LOOKUP = {member.code: member for member in ErrorCode}


def get_error_by_code(code_str: str) -> Optional[ErrorCode]:
    """
    Look up an ErrorCode by its code string (e.g. "E001").

    Returns None if the code is not found.
    """
    return _CODE_LOOKUP.get(code_str)
