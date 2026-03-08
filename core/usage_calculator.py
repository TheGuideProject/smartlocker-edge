"""
Usage Calculator

Estimates paint consumption from weight measurements.
Tracks stock levels and generates stock alerts.
"""

import logging
from typing import Optional, Dict
from dataclasses import dataclass

from config import settings
from core.models import ConsumptionEvent, EventConfirmation
from core.event_types import Event, EventType
from core.event_bus import EventBus

logger = logging.getLogger("smartlocker")


@dataclass
class StockLevel:
    """Current stock status for a product on a slot."""
    product_id: str
    product_name: str
    slot_id: str
    weight_full_g: float       # Weight when can was full
    weight_current_g: float    # Current weight
    can_tare_g: float          # Empty can weight
    percentage_remaining: float
    status: str                # "ok", "low", "critical", "empty"


class UsageCalculator:
    """
    Calculates paint consumption and stock levels.

    Two main use cases:
    1. Can removed and returned: usage = weight_before - weight_after
    2. Mixing session: usage = actual weights recorded during mixing
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

        # Track weight snapshots: slot_id -> weight at last scan
        self._weight_snapshots: Dict[str, float] = {}

        # Known product weights: tag_id -> weight_full_g
        self._full_weights: Dict[str, float] = {}

        # Known can tare weights: tag_id -> tare_g
        self._tare_weights: Dict[str, float] = {}

    def register_can(self, tag_id: str, weight_full_g: float, tare_g: float) -> None:
        """Register a can's full weight and tare weight (from product catalog)."""
        self._full_weights[tag_id] = weight_full_g
        self._tare_weights[tag_id] = tare_g

    def record_removal(self, slot_id: str, tag_id: str, weight_at_removal_g: float) -> None:
        """Record the weight when a can is removed from a slot."""
        self._weight_snapshots[slot_id] = weight_at_removal_g
        logger.debug(f"Recorded removal weight: slot={slot_id}, tag={tag_id}, weight={weight_at_removal_g}g")

    def record_return(
        self,
        slot_id: str,
        tag_id: str,
        weight_at_return_g: float,
        session_id: Optional[str] = None,
        confirmed: bool = False,
    ) -> ConsumptionEvent:
        """
        Record when a can is returned and calculate usage.

        Returns a ConsumptionEvent with the estimated usage.
        """
        weight_before = self._weight_snapshots.get(slot_id, 0)
        tare = self._tare_weights.get(tag_id, 0)

        # Usage = weight before removal - weight after return
        # (both include can tare weight, so it cancels out)
        usage_g = max(0, weight_before - weight_at_return_g)

        event = ConsumptionEvent(
            tag_id=tag_id,
            product_id="",  # TODO: resolve from tag catalog
            slot_id=slot_id,
            session_id=session_id,
            weight_before_g=weight_before,
            weight_after_g=weight_at_return_g,
            estimated_usage_g=usage_g,
            confirmation=(
                EventConfirmation.CONFIRMED if confirmed
                else EventConfirmation.UNCONFIRMED
            ),
        )

        # Publish consumption event
        self.event_bus.publish(Event(
            event_type=EventType.CONSUMPTION_RECORDED,
            device_id=settings.DEVICE_ID,
            slot_id=slot_id,
            tag_id=tag_id,
            data={
                "weight_before_g": weight_before,
                "weight_after_g": weight_at_return_g,
                "estimated_usage_g": usage_g,
                "session_id": session_id or "",
            },
        ))

        # Check stock level
        self._check_stock_level(tag_id, weight_at_return_g)

        # Clean up snapshot
        self._weight_snapshots.pop(slot_id, None)

        logger.info(
            f"Consumption recorded: slot={slot_id}, "
            f"usage={usage_g:.0f}g ({weight_before:.0f}g -> {weight_at_return_g:.0f}g)"
        )

        return event

    def calculate_stock_level(self, tag_id: str, current_weight_g: float) -> StockLevel:
        """Calculate stock level for a specific can."""
        full_weight = self._full_weights.get(tag_id, current_weight_g)
        tare = self._tare_weights.get(tag_id, 0)

        net_full = full_weight - tare
        net_current = max(0, current_weight_g - tare)

        if net_full > 0:
            pct = (net_current / net_full) * 100
        else:
            pct = 0

        if pct <= 0:
            status = "empty"
        elif pct <= settings.STOCK_CRITICAL_THRESHOLD_PCT:
            status = "critical"
        elif pct <= settings.STOCK_LOW_THRESHOLD_PCT:
            status = "low"
        else:
            status = "ok"

        return StockLevel(
            product_id="",  # TODO: resolve from tag catalog
            product_name="",
            slot_id="",
            weight_full_g=full_weight,
            weight_current_g=current_weight_g,
            can_tare_g=tare,
            percentage_remaining=round(pct, 1),
            status=status,
        )

    def _check_stock_level(self, tag_id: str, current_weight_g: float) -> None:
        """Check if stock level triggers an alert."""
        level = self.calculate_stock_level(tag_id, current_weight_g)

        if level.status == "critical":
            self.event_bus.publish(Event(
                event_type=EventType.STOCK_CRITICAL,
                device_id=settings.DEVICE_ID,
                tag_id=tag_id,
                data={
                    "percentage_remaining": level.percentage_remaining,
                    "weight_current_g": current_weight_g,
                },
            ))
        elif level.status == "low":
            self.event_bus.publish(Event(
                event_type=EventType.STOCK_LOW,
                device_id=settings.DEVICE_ID,
                tag_id=tag_id,
                data={
                    "percentage_remaining": level.percentage_remaining,
                    "weight_current_g": current_weight_g,
                },
            ))
