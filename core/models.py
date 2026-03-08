"""
Core Data Models

These are the in-memory data structures used throughout the system.
They represent shelves, slots, products, mixing recipes, etc.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List
import time
import uuid


# ============================================================
# ENUMS
# ============================================================

class SlotStatus(Enum):
    """Current state of a shelf slot."""
    EMPTY = "empty"                     # No can present
    OCCUPIED = "occupied"               # Can is on the slot
    REMOVED = "removed"                 # Can was taken off (recently)
    IN_USE_ELSEWHERE = "in_use"         # Can removed, timeout exceeded, assumed in use
    ANOMALY = "anomaly"                 # Sensors disagree (RFID vs weight mismatch)


class MixingState(Enum):
    """States of the mixing workflow state machine."""
    IDLE = "idle"
    SELECT_JOB = "select_job"
    SELECT_PRODUCT = "select_product"
    SHOW_RECIPE = "show_recipe"
    PICK_BASE = "pick_base"
    WEIGH_BASE = "weigh_base"
    PICK_HARDENER = "pick_hardener"
    WEIGH_HARDENER = "weigh_hardener"
    CONFIRM_MIX = "confirm_mix"
    ADD_THINNER = "add_thinner"
    POT_LIFE_ACTIVE = "pot_life_active"
    RETURN_CANS = "return_cans"
    SESSION_COMPLETE = "session_complete"
    ABORTED = "aborted"


class ProductType(Enum):
    """Types of paint products."""
    BASE_PAINT = "base_paint"
    HARDENER = "hardener"
    THINNER = "thinner"
    PRIMER = "primer"


class ApplicationMethod(Enum):
    """How paint is applied."""
    BRUSH = "brush"
    ROLLER = "roller"
    SPRAY = "spray"


class EventConfirmation(Enum):
    """Whether an event was confirmed by crew via touchscreen."""
    CONFIRMED = "confirmed"         # Crew was using touchscreen
    UNCONFIRMED = "unconfirmed"     # Sensor detected change, no active session


# ============================================================
# PRODUCT & RECIPE MODELS
# ============================================================

@dataclass
class Product:
    """A paint product in the catalog."""
    product_id: str
    ppg_code: str
    name: str
    product_type: ProductType
    density_g_per_ml: float = 1.0
    pot_life_minutes: Optional[int] = None  # None for non-mixable products
    hazard_class: str = ""
    can_sizes_ml: List[int] = field(default_factory=lambda: [1000, 5000])
    can_tare_weight_g: dict = field(default_factory=dict)  # {size_ml: tare_grams}


@dataclass
class MixingRecipe:
    """Defines how to mix a two-component paint system."""
    recipe_id: str
    name: str
    base_product_id: str
    hardener_product_id: str
    ratio_base: float               # e.g., 4.0 (parts)
    ratio_hardener: float            # e.g., 1.0 (parts)
    tolerance_pct: float = 5.0      # ±5% acceptable
    thinner_pct_brush: float = 5.0
    thinner_pct_roller: float = 5.0
    thinner_pct_spray: float = 10.0
    recommended_thinner_id: Optional[str] = None
    pot_life_minutes: int = 480     # 8 hours default


# ============================================================
# SHELF & SLOT MODELS
# ============================================================

@dataclass
class Slot:
    """A single position on a shelf where one can sits."""
    slot_id: str                     # e.g., "shelf1_slot1"
    shelf_id: str                    # Parent shelf
    position: int                    # Slot number (1, 2, 3...)
    rfid_reader_id: str              # Associated RFID reader
    led_index: int                   # LED strip index
    status: SlotStatus = SlotStatus.EMPTY
    current_tag_id: Optional[str] = None
    current_product_id: Optional[str] = None
    weight_when_placed_g: float = 0.0
    weight_current_g: float = 0.0
    last_change_time: float = field(default_factory=time.time)


@dataclass
class Shelf:
    """A physical shelf with load cells and multiple slots."""
    shelf_id: str                    # e.g., "shelf1"
    position: int                    # Shelf number
    weight_channel: str              # Load cell channel name
    slots: List[Slot] = field(default_factory=list)
    tare_weight_g: float = 0.0      # Empty shelf weight
    max_weight_g: float = 50000.0   # 50 kg max capacity


# ============================================================
# MIXING SESSION MODEL
# ============================================================

@dataclass
class MixingSession:
    """Tracks a single mixing session from start to finish."""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: MixingState = MixingState.IDLE
    recipe_id: Optional[str] = None
    job_id: Optional[str] = None
    user_name: str = ""

    # Base component
    base_product_id: Optional[str] = None
    base_tag_id: Optional[str] = None
    base_weight_target_g: float = 0.0
    base_weight_actual_g: float = 0.0

    # Hardener component
    hardener_product_id: Optional[str] = None
    hardener_tag_id: Optional[str] = None
    hardener_weight_target_g: float = 0.0
    hardener_weight_actual_g: float = 0.0

    # Thinner (optional)
    thinner_product_id: Optional[str] = None
    thinner_weight_g: float = 0.0

    # Results
    ratio_achieved: float = 0.0
    ratio_in_spec: bool = False
    override_reason: str = ""
    application_method: ApplicationMethod = ApplicationMethod.BRUSH

    # Timing
    started_at: float = 0.0
    completed_at: float = 0.0
    pot_life_started_at: float = 0.0
    pot_life_expires_at: float = 0.0

    confirmation: EventConfirmation = EventConfirmation.CONFIRMED


# ============================================================
# CONSUMPTION EVENT MODEL
# ============================================================

@dataclass
class ConsumptionEvent:
    """Records a single paint consumption event."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tag_id: str = ""
    product_id: str = ""
    slot_id: str = ""
    session_id: Optional[str] = None
    job_id: Optional[str] = None
    weight_before_g: float = 0.0
    weight_after_g: float = 0.0
    estimated_usage_g: float = 0.0
    confirmation: EventConfirmation = EventConfirmation.UNCONFIRMED
    timestamp: float = field(default_factory=time.time)
