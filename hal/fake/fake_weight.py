"""
Fake Weight Driver (TEST mode)

Simulates load cell / scale readings without real hardware.
You can set weights manually, simulate pouring (gradual decrease),
and simulate shelf weight changes when cans are added/removed.
"""

import logging
import time
import random
from typing import List, Dict, Optional

from hal.interfaces import WeightDriverInterface, WeightReading

logger = logging.getLogger("smartlocker.sensor")


class FakeWeightDriver(WeightDriverInterface):
    """
    Simulated weight sensor for testing.

    Usage:
        driver = FakeWeightDriver(channels=["shelf1", "mixing_scale"])
        driver.initialize()

        # Set shelf weight (simulating 3 full paint cans)
        driver.set_weight("shelf1", 15000)  # 15 kg

        # Read it
        reading = driver.read_weight("shelf1")  # WeightReading(grams=15000, ...)

        # Simulate removing a can (weight drops by ~5kg)
        driver.set_weight("shelf1", 10000)

        # Set mixing scale for a pour
        driver.set_weight("mixing_scale", 0)      # empty container
        driver.set_weight("mixing_scale", 400)     # 400g of base poured
    """

    def __init__(self, channels: Optional[List[str]] = None):
        self._channels = channels or ["shelf1", "mixing_scale"]
        # Current weight per channel (grams)
        self._weights: Dict[str, float] = {ch: 0.0 for ch in self._channels}
        # Tare offset per channel
        self._tare: Dict[str, float] = {ch: 0.0 for ch in self._channels}
        # Whether to add realistic noise to readings
        self._noise_enabled = True
        self._noise_range_g = 5.0  # ±5g noise (simulates vibration)
        self._initialized = False

    def initialize(self) -> bool:
        self._initialized = True
        logger.info(f"[FAKE WEIGHT] Initialized channels: {self._channels}")
        return True

    def read_weight(self, channel: str) -> WeightReading:
        if not self._initialized:
            return WeightReading(grams=0, channel=channel, stable=False)
        if channel not in self._weights:
            raise ValueError(f"Unknown channel: {channel}. Available: {self._channels}")

        raw_weight = self._weights[channel] - self._tare[channel]

        # Add small random noise to simulate real sensor behavior
        noise = 0.0
        if self._noise_enabled:
            noise = random.uniform(-self._noise_range_g, self._noise_range_g)

        return WeightReading(
            grams=round(raw_weight + noise, 1),
            channel=channel,
            stable=True,  # Fake driver is always "stable"
            raw_value=int(raw_weight * 100),  # Simulated ADC value
            timestamp=time.time(),
        )

    def tare(self, channel: str) -> bool:
        if channel not in self._weights:
            return False
        self._tare[channel] = self._weights[channel]
        logger.info(f"[FAKE WEIGHT] Tared '{channel}' at {self._weights[channel]:.1f}g")
        return True

    def get_channels(self) -> List[str]:
        return list(self._channels)

    def is_healthy(self) -> bool:
        return self._initialized

    def shutdown(self) -> None:
        self._initialized = False
        logger.info("[FAKE WEIGHT] Shutdown")

    # ---- TEST-ONLY METHODS ----

    def set_weight(self, channel: str, grams: float) -> None:
        """Set the absolute weight on a channel (before tare)."""
        if channel not in self._weights:
            raise ValueError(f"Unknown channel: {channel}")
        self._weights[channel] = grams
        logger.info(f"[FAKE WEIGHT] '{channel}' set to {grams:.1f}g")

    def adjust_weight(self, channel: str, delta_grams: float) -> None:
        """Add/subtract from current weight (simulate pouring or removing)."""
        if channel not in self._weights:
            raise ValueError(f"Unknown channel: {channel}")
        self._weights[channel] += delta_grams
        logger.info(
            f"[FAKE WEIGHT] '{channel}' adjusted by {delta_grams:+.1f}g "
            f"-> {self._weights[channel]:.1f}g"
        )

    def set_noise(self, enabled: bool, range_g: float = 5.0) -> None:
        """Enable/disable sensor noise simulation."""
        self._noise_enabled = enabled
        self._noise_range_g = range_g

    def get_raw_weight(self, channel: str) -> float:
        """Get the set weight without noise (for test assertions)."""
        return self._weights.get(channel, 0.0) - self._tare.get(channel, 0.0)
