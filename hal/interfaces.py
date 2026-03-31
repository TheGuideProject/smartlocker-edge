"""
Hardware Abstraction Layer (HAL) - Interface Definitions

These are CONTRACTS that both fake (test) and real (live) drivers must follow.
Think of them as promises: "Any RFID driver must be able to do X, Y, Z."

In TEST mode: fake drivers return simulated values.
In LIVE mode: real drivers talk to physical PN532, Arduino, LEDs, buzzer.
The rest of the software doesn't care which one is running.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum
import time


# ============================================================
# DATA CLASSES - Structured sensor readings
# ============================================================

@dataclass
class TagReading:
    """A single RFID/NFC tag detection."""
    tag_id: str                 # Unique tag UID (e.g., "04:A2:F3:1B:22:80")
    reader_id: str              # Which reader detected it (e.g., "shelf1_slot1")
    signal_strength: int = 0    # 0-100 relative signal quality
    timestamp: float = field(default_factory=time.time)
    # Product data read from NTAG (format: PPG_CODE/BATCH/PRODUCT_NAME/COLOR)
    product_data: Optional[str] = None
    ppg_code: Optional[str] = None
    batch_number: Optional[str] = None
    product_name: Optional[str] = None
    color: Optional[str] = None


@dataclass
class WeightReading:
    """A single weight measurement from a load cell or scale."""
    grams: float                # Weight in grams
    channel: str                # Which load cell / scale (e.g., "shelf1", "mixing_scale")
    stable: bool = False        # True if reading has settled (not fluctuating)
    raw_value: int = 0          # Raw ADC value (for debugging)
    timestamp: float = field(default_factory=time.time)


class LEDColor(Enum):
    """Standard LED colors for slot indicators."""
    OFF = (0, 0, 0)
    GREEN = (0, 255, 0)
    RED = (255, 0, 0)
    YELLOW = (255, 200, 0)
    BLUE = (0, 0, 255)
    WHITE = (255, 255, 255)


class LEDPattern(Enum):
    """LED animation patterns."""
    SOLID = "solid"
    BLINK_SLOW = "blink_slow"     # ~1 Hz
    BLINK_FAST = "blink_fast"     # ~3 Hz
    PULSE = "pulse"               # Smooth fade in/out


class BuzzerPattern(Enum):
    """Standard buzzer sound patterns."""
    CONFIRM = "confirm"           # Single short beep (action confirmed)
    WARNING = "warning"           # Double beep (attention needed)
    ERROR = "error"               # Long continuous buzz (something wrong)
    TARGET_REACHED = "target"     # Rising tone (pour target reached)
    TICK = "tick"                 # Very short click (weight change acknowledged)
    ALARM = "alarm"               # Repeating loud alarm (weight alarm, unauthorized)


# ============================================================
# ABSTRACT INTERFACES - Every driver must implement these
# ============================================================

class RFIDDriverInterface(ABC):
    """
    Contract for RFID/NFC tag readers.

    Any RFID driver (fake or real PN532) must implement these methods.
    The rest of the system calls these methods without knowing which
    driver is actually running.
    """

    @abstractmethod
    def initialize(self) -> bool:
        """
        Set up the reader hardware.
        Returns True if successful, False if initialization failed.
        """
        ...

    @abstractmethod
    def poll_tags(self) -> List[TagReading]:
        """
        Check all readers and return a list of currently detected tags.
        Returns empty list if no tags are detected.
        Called repeatedly at RFID_POLL_INTERVAL_MS.
        """
        ...

    @abstractmethod
    def get_reader_ids(self) -> List[str]:
        """Return list of all configured reader IDs (e.g., ['shelf1_slot1', 'shelf1_slot2'])."""
        ...

    @abstractmethod
    def is_healthy(self) -> bool:
        """Return True if all readers are responding normally."""
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """Release hardware resources."""
        ...


class WeightDriverInterface(ABC):
    """
    Contract for weight sensors (shelf load cells + mixing scale).

    In LIVE mode, this talks to Arduino Nano via USB serial.
    The Arduino reads HX711 ADC chips and sends averaged values.
    """

    @abstractmethod
    def initialize(self) -> bool:
        """Set up weight sensor connections. Returns True if successful."""
        ...

    @abstractmethod
    def read_weight(self, channel: str) -> WeightReading:
        """
        Read current weight from a specific channel.
        Channels: "shelf1", "shelf2", "mixing_scale", etc.
        """
        ...

    @abstractmethod
    def tare(self, channel: str) -> bool:
        """
        Zero out the scale on a specific channel.
        Used before mixing: place empty container, tare to zero.
        Returns True if tare successful.
        """
        ...

    @abstractmethod
    def get_channels(self) -> List[str]:
        """Return list of all available weight channels."""
        ...

    @abstractmethod
    def is_healthy(self) -> bool:
        """Return True if all weight sensors are responding normally."""
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """Release hardware resources."""
        ...


class LEDDriverInterface(ABC):
    """
    Contract for LED slot indicators.

    Each shelf slot has one or more LEDs that can show colors and patterns
    to guide the crew (green = pick here, red = wrong, etc.).
    """

    @abstractmethod
    def initialize(self) -> bool:
        """Set up LED hardware. Returns True if successful."""
        ...

    @abstractmethod
    def set_slot(self, slot_id: str, color: LEDColor,
                 pattern: LEDPattern = LEDPattern.SOLID) -> None:
        """
        Set color and pattern for a specific slot's LED.
        slot_id: e.g., "shelf1_slot1"
        """
        ...

    @abstractmethod
    def clear_slot(self, slot_id: str) -> None:
        """Turn off LED for a specific slot."""
        ...

    @abstractmethod
    def clear_all(self) -> None:
        """Turn off all LEDs."""
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """Turn off all LEDs and release hardware."""
        ...


class BuzzerDriverInterface(ABC):
    """
    Contract for audio feedback (buzzer/speaker).

    Provides sound feedback to crew: confirmation beeps, warnings, errors.
    """

    @abstractmethod
    def initialize(self) -> bool:
        """Set up buzzer hardware. Returns True if successful."""
        ...

    @abstractmethod
    def play(self, pattern: BuzzerPattern) -> None:
        """
        Play a predefined sound pattern.
        Non-blocking: starts the sound and returns immediately.
        """
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop any currently playing sound."""
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """Release hardware resources."""
        ...
