"""
Mixing Engine - State Machine

Guides crew through the complete mixing workflow:
  1. Select maintenance job / area
  2. System shows which products are needed
  3. LEDs indicate which cans to pick
  4. Place container on mixing scale, tare
  5. Pour base component (live weight feedback)
  6. Pour hardener component (ratio monitoring)
  7. Optional: add thinner
  8. Log mixing session
  9. Start pot-life countdown
  10. Guide can returns to correct slots

This is the highest-value feature in the system.
"""

import logging
import time
from typing import Optional, Callable, Dict, Any, TYPE_CHECKING

from config import settings
from core.models import (
    MixingSession, MixingState, MixingRecipe, Product,
    ApplicationMethod, EventConfirmation,
)
from core.event_types import Event, EventType
from core.event_bus import EventBus
from hal.interfaces import (
    WeightDriverInterface, LEDDriverInterface, BuzzerDriverInterface,
    LEDColor, LEDPattern, BuzzerPattern, WeightReading,
)

if TYPE_CHECKING:
    from core.inventory_engine import InventoryEngine
    from persistence.database import Database

logger = logging.getLogger("smartlocker")


class MixingEngine:
    """
    State machine that manages the mixing workflow.

    Usage:
        engine = MixingEngine(weight, led, buzzer, event_bus)
        engine.start_session(recipe, user_name="Crew A")

        # Call update() repeatedly in the main loop
        engine.update()  # Reads weight, checks thresholds, advances state

        # UI calls these when crew interacts with touchscreen:
        engine.select_job(job_id)
        engine.confirm_pour()
        engine.confirm_mix()
        engine.add_thinner(method=ApplicationMethod.BRUSH)
    """

    def __init__(
        self,
        weight: WeightDriverInterface,
        led: LEDDriverInterface,
        buzzer: BuzzerDriverInterface,
        event_bus: EventBus,
    ):
        self.weight = weight
        self.led = led
        self.buzzer = buzzer
        self.event_bus = event_bus

        # Current session (None when idle)
        self.session: Optional[MixingSession] = None

        # Recipe catalog (loaded from DB/config — simplified for now)
        self._recipes: Dict[str, MixingRecipe] = {}
        self._products: Dict[str, Product] = {}

        # Callback for UI updates
        self._on_state_change: Optional[Callable[[MixingState, Dict], None]] = None

        # Cross-engine references (set after init via setters)
        self._inventory: Optional['InventoryEngine'] = None
        self._db: Optional['Database'] = None

        # Weight monitoring
        self._last_weight_reading: Optional[WeightReading] = None
        self._weight_stable_since: float = 0.0

        # Subscribe to CAN_RETURNED for auto-detecting can returns via RFID
        self.event_bus.subscribe(EventType.CAN_RETURNED, self._on_can_returned)
        # Subscribe to CAN_REMOVED for auto-detecting can picks via RFID
        self.event_bus.subscribe(EventType.CAN_REMOVED, self._on_can_removed)

    def set_inventory(self, inv: 'InventoryEngine') -> None:
        """Set the inventory engine reference for LED slot guidance."""
        self._inventory = inv
        logger.info("MixingEngine: inventory reference set")

    def set_database(self, db: 'Database') -> None:
        """Set the database reference for persisting mixing sessions."""
        self._db = db
        logger.info("MixingEngine: database reference set")

    def set_state_change_callback(self, callback: Callable[[MixingState, Dict], None]):
        """Register a callback for UI updates when state changes."""
        self._on_state_change = callback

    def load_recipes(self, recipes: Dict[str, MixingRecipe]):
        """Load mixing recipes (from database or config)."""
        self._recipes = recipes

    def load_products(self, products: Dict[str, Product]):
        """Load product catalog."""
        self._products = products

    # ============================================================
    # RFID AUTO-DETECT: CAN REMOVED / RETURNED
    # ============================================================

    def _on_can_removed(self, event: Event) -> None:
        """Auto-detect when crew picks up a can during PICK_BASE / PICK_HARDENER.
        If the removed tag matches the expected product, auto-advance."""
        if not self.session:
            return

        tag_id = event.tag_id
        product_id = event.data.get("product_id", "")

        if self.session.state == MixingState.PICK_BASE:
            if product_id == self.session.base_product_id:
                logger.info(f"RFID auto-detect: base can picked (tag={tag_id})")
                self.confirm_base_picked(tag_id)

        elif self.session.state == MixingState.PICK_HARDENER:
            if product_id == self.session.hardener_product_id:
                logger.info(f"RFID auto-detect: hardener can picked (tag={tag_id})")
                self.confirm_hardener_picked(tag_id)

    def _on_can_returned(self, event: Event) -> None:
        """Auto-detect when crew returns a can during RETURN_BASE / RETURN_HARDENER.
        If the returned tag matches the base/hardener, auto-advance the workflow."""
        if not self.session:
            return

        tag_id = event.tag_id

        if self.session.state == MixingState.RETURN_BASE:
            # Check if the returned tag is the base product
            if tag_id == self.session.base_tag_id:
                logger.info(f"RFID auto-detect: base can returned (tag={tag_id})")
                self.confirm_base_returned()
            else:
                # Also match by product_id if tag_id wasn't captured during pick
                product_id = event.data.get("product_id", "")
                if product_id == self.session.base_product_id:
                    logger.info(f"RFID auto-detect: base product returned (product={product_id})")
                    self.confirm_base_returned()

        elif self.session.state == MixingState.RETURN_HARDENER:
            if tag_id == self.session.hardener_tag_id:
                logger.info(f"RFID auto-detect: hardener can returned (tag={tag_id})")
                self.confirm_hardener_returned()
            else:
                product_id = event.data.get("product_id", "")
                if product_id == self.session.hardener_product_id:
                    logger.info(f"RFID auto-detect: hardener product returned (product={product_id})")
                    self.confirm_hardener_returned()

    # ============================================================
    # STATE TRANSITIONS
    # ============================================================

    def start_session(self, recipe_id: str, user_name: str = "",
                      job_id: Optional[str] = None,
                      fallback_recipe: Optional[MixingRecipe] = None) -> bool:
        """Start a new mixing session. Returns False if already in session.

        If recipe_id is not found in loaded recipes, uses fallback_recipe
        if provided (e.g. generated on-the-fly from maintenance chart data).
        """
        if self.session and self.session.state != MixingState.IDLE:
            logger.warning("Cannot start session: already active")
            return False

        recipe = self._recipes.get(recipe_id)
        if not recipe and fallback_recipe:
            # Use the fallback recipe and register it for this session
            recipe = fallback_recipe
            self._recipes[recipe_id] = recipe
            logger.info(f"Using fallback recipe for '{recipe_id}': {recipe.name}")
        if not recipe:
            logger.error(f"Unknown recipe: {recipe_id}")
            return False

        self.session = MixingSession(
            state=MixingState.SELECT_PRODUCT,
            recipe_id=recipe_id,
            job_id=job_id,
            user_name=user_name,
            base_product_id=recipe.base_product_id,
            hardener_product_id=recipe.hardener_product_id,
            started_at=time.time(),
        )

        self.event_bus.publish(Event(
            event_type=EventType.MIX_SESSION_STARTED,
            device_id=settings.DEVICE_ID,
            session_id=self.session.session_id,
            user_name=user_name,
            data={
                "recipe_id": recipe_id,
                "recipe_name": recipe.name,
                "job_id": job_id or "",
            },
        ))

        self._notify_ui({"recipe": recipe.name})
        logger.info(f"Mixing session started: {recipe.name} by {user_name}")
        return True

    def show_recipe(self, base_amount_g: float) -> None:
        """
        Calculate and display the recipe.
        base_amount_g: how much base the crew wants to mix.
        """
        if not self.session:
            return

        recipe = self._recipes.get(self.session.recipe_id)
        if not recipe:
            return

        # Calculate hardener amount from ratio
        hardener_amount_g = base_amount_g * (recipe.ratio_hardener / recipe.ratio_base)

        self.session.base_weight_target_g = base_amount_g
        self.session.hardener_weight_target_g = hardener_amount_g
        self.session.state = MixingState.SHOW_RECIPE

        self._notify_ui({
            "base_target_g": base_amount_g,
            "hardener_target_g": round(hardener_amount_g, 1),
            "ratio": f"{recipe.ratio_base}:{recipe.ratio_hardener}",
            "tolerance_pct": recipe.tolerance_pct,
            "pot_life_min": recipe.pot_life_minutes,
        })

    def advance_to_pick_base(self) -> None:
        """Crew confirmed recipe, ready to pick base can."""
        if not self.session or self.session.state != MixingState.SHOW_RECIPE:
            return

        self.session.state = MixingState.PICK_BASE

        # Light up the correct shelf slot for base product
        self.led.clear_all()
        if self._inventory:
            base_slot_id = self._inventory.get_slot_id_for_product(self.session.base_product_id)
            if base_slot_id:
                self.led.set_slot(base_slot_id, LEDColor.RED, LEDPattern.BLINK_SLOW)
                logger.info(f"LED guidance: base product slot {base_slot_id}")

        self.buzzer.play(BuzzerPattern.TICK)
        self._notify_ui({"instruction": "Pick the BASE can from the lit shelf slot"})

    def confirm_base_picked(self, tag_id: str) -> None:
        """Crew picked up the base can (confirmed by RFID disappearance)."""
        if not self.session or self.session.state != MixingState.PICK_BASE:
            return

        self.session.base_tag_id = tag_id
        self.session.state = MixingState.WEIGH_BASE

        self._notify_ui({
            "instruction": "Place container on mixing scale, then TARE",
            "target_g": self.session.base_weight_target_g,
        })

    def tare_scale(self) -> bool:
        """Crew placed container on scale and pressed TARE."""
        success = self.weight.tare("mixing_scale")
        if success:
            self.buzzer.play(BuzzerPattern.CONFIRM)
            logger.info("Mixing scale tared")
        return success

    def confirm_base_weighed(self) -> None:
        """Crew finished pouring base component."""
        if not self.session or self.session.state != MixingState.WEIGH_BASE:
            return

        reading = self.weight.read_weight("mixing_scale")
        self.session.base_weight_actual_g = reading.grams

        self.event_bus.publish(Event(
            event_type=EventType.MIX_BASE_WEIGHED,
            device_id=settings.DEVICE_ID,
            session_id=self.session.session_id,
            data={
                "target_g": self.session.base_weight_target_g,
                "actual_g": reading.grams,
            },
        ))

        # Guide crew to return the base can before picking hardener
        self.session.state = MixingState.RETURN_BASE
        self.buzzer.play(BuzzerPattern.CONFIRM)

        # Light up base slot with BLINK_FAST = "put it back here!"
        self.led.clear_all()
        if self._inventory:
            base_slot_id = self._inventory.get_slot_id_for_product(self.session.base_product_id)
            if base_slot_id:
                self.led.set_slot(base_slot_id, LEDColor.RED, LEDPattern.BLINK_FAST)
                logger.info(f"LED guidance: return base to slot {base_slot_id}")

        self._notify_ui({
            "instruction": "Return the BASE can to the lit shelf slot",
            "base_actual_g": reading.grams,
        })

    def confirm_base_returned(self) -> None:
        """Base can returned to shelf. Advance to pick hardener."""
        if not self.session or self.session.state != MixingState.RETURN_BASE:
            return

        self.led.clear_all()
        self.buzzer.play(BuzzerPattern.TICK)

        # Now guide to pick the hardener
        self.session.state = MixingState.PICK_HARDENER
        if self._inventory:
            hardener_slot_id = self._inventory.get_slot_id_for_product(self.session.hardener_product_id)
            if hardener_slot_id:
                self.led.set_slot(hardener_slot_id, LEDColor.RED, LEDPattern.BLINK_SLOW)
                logger.info(f"LED guidance: pick hardener from slot {hardener_slot_id}")

        self._notify_ui({
            "instruction": "Pick the HARDENER can from the lit shelf slot",
        })

    def confirm_hardener_picked(self, tag_id: str) -> None:
        """Crew picked up hardener can."""
        if not self.session or self.session.state != MixingState.PICK_HARDENER:
            return

        self.session.hardener_tag_id = tag_id
        self.session.state = MixingState.WEIGH_HARDENER

        self._notify_ui({
            "instruction": "Pour hardener into the mixing container",
            "target_g": self.session.hardener_weight_target_g,
        })

    def confirm_hardener_weighed(self) -> None:
        """Crew finished pouring hardener."""
        if not self.session or self.session.state != MixingState.WEIGH_HARDENER:
            return

        reading = self.weight.read_weight("mixing_scale")
        # Hardener weight = total - base
        hardener_actual = reading.grams - self.session.base_weight_actual_g
        self.session.hardener_weight_actual_g = hardener_actual

        # Calculate actual ratio
        if hardener_actual > 0:
            self.session.ratio_achieved = self.session.base_weight_actual_g / hardener_actual
        else:
            self.session.ratio_achieved = 0.0

        # Check if ratio is within tolerance
        recipe = self._recipes.get(self.session.recipe_id)
        if recipe:
            target_ratio = recipe.ratio_base / recipe.ratio_hardener
            deviation_pct = abs(self.session.ratio_achieved - target_ratio) / target_ratio * 100
            self.session.ratio_in_spec = deviation_pct <= recipe.tolerance_pct
        else:
            self.session.ratio_in_spec = False

        self.event_bus.publish(Event(
            event_type=EventType.MIX_HARDENER_WEIGHED,
            device_id=settings.DEVICE_ID,
            session_id=self.session.session_id,
            data={
                "target_g": self.session.hardener_weight_target_g,
                "actual_g": hardener_actual,
                "ratio_achieved": round(self.session.ratio_achieved, 2),
                "in_spec": self.session.ratio_in_spec,
            },
        ))

        # Guide crew to return hardener can before confirming mix
        self.session.state = MixingState.RETURN_HARDENER

        if self.session.ratio_in_spec:
            self.buzzer.play(BuzzerPattern.TARGET_REACHED)
        else:
            self.buzzer.play(BuzzerPattern.WARNING)
            self.event_bus.publish(Event(
                event_type=EventType.MIX_OUT_OF_SPEC,
                device_id=settings.DEVICE_ID,
                session_id=self.session.session_id,
                data={
                    "ratio_achieved": round(self.session.ratio_achieved, 2),
                    "ratio_in_spec": False,
                },
            ))

        # Light up hardener slot with BLINK_FAST = "put it back!"
        self.led.clear_all()
        if self._inventory:
            hardener_slot_id = self._inventory.get_slot_id_for_product(self.session.hardener_product_id)
            if hardener_slot_id:
                self.led.set_slot(hardener_slot_id, LEDColor.RED, LEDPattern.BLINK_FAST)
                logger.info(f"LED guidance: return hardener to slot {hardener_slot_id}")

        self._notify_ui({
            "ratio_achieved": round(self.session.ratio_achieved, 2),
            "in_spec": self.session.ratio_in_spec,
            "instruction": "Return HARDENER can, then confirm mix",
        })

    def confirm_hardener_returned(self) -> None:
        """Hardener can returned to shelf. Advance to confirm mix."""
        if not self.session or self.session.state != MixingState.RETURN_HARDENER:
            return

        self.led.clear_all()
        self.buzzer.play(BuzzerPattern.CONFIRM)
        self.session.state = MixingState.CONFIRM_MIX

        self._notify_ui({
            "ratio_achieved": round(self.session.ratio_achieved, 2),
            "in_spec": self.session.ratio_in_spec,
            "instruction": "MIX OK" if self.session.ratio_in_spec else "MIX OUT OF SPEC",
        })
        logger.info("Hardener returned — advancing to CONFIRM_MIX")

    def confirm_mix(self, override_reason: str = "") -> None:
        """Crew confirms the mix (even if out of spec with a reason)."""
        if not self.session or self.session.state != MixingState.CONFIRM_MIX:
            return

        if not self.session.ratio_in_spec and override_reason:
            self.session.override_reason = override_reason
            self.event_bus.publish(Event(
                event_type=EventType.MIX_OVERRIDE,
                device_id=settings.DEVICE_ID,
                session_id=self.session.session_id,
                data={"reason": override_reason},
            ))

        self.session.state = MixingState.ADD_THINNER
        self._notify_ui({"instruction": "Add thinner? Select application method or SKIP"})

    def add_thinner(self, method: ApplicationMethod, thinner_weight_g: float = 0.0) -> None:
        """Add thinner based on application method."""
        if not self.session or self.session.state != MixingState.ADD_THINNER:
            return

        self.session.application_method = method
        self.session.thinner_weight_g = thinner_weight_g

        recipe = self._recipes.get(self.session.recipe_id)
        if recipe:
            thinner_pct = {
                ApplicationMethod.BRUSH: recipe.thinner_pct_brush,
                ApplicationMethod.ROLLER: recipe.thinner_pct_roller,
                ApplicationMethod.SPRAY: recipe.thinner_pct_spray,
            }.get(method, 0)

            self.event_bus.publish(Event(
                event_type=EventType.MIX_THINNER_ADDED,
                device_id=settings.DEVICE_ID,
                session_id=self.session.session_id,
                data={
                    "method": method.value,
                    "thinner_pct": thinner_pct,
                    "thinner_weight_g": thinner_weight_g,
                },
            ))

        self._start_pot_life()

    def skip_thinner(self) -> None:
        """Skip thinner addition."""
        if not self.session or self.session.state != MixingState.ADD_THINNER:
            return
        self.session.application_method = ApplicationMethod.BRUSH
        self._start_pot_life()

    def _start_pot_life(self) -> None:
        """Start the pot-life countdown timer."""
        if not self.session:
            return

        recipe = self._recipes.get(self.session.recipe_id)
        pot_life_sec = (recipe.pot_life_minutes * 60) if recipe else 28800  # 8h default

        self.session.pot_life_started_at = time.time()
        self.session.pot_life_expires_at = time.time() + pot_life_sec
        self.session.state = MixingState.POT_LIFE_ACTIVE

        self.buzzer.play(BuzzerPattern.CONFIRM)

        self._notify_ui({
            "instruction": "Mix ready! Pot-life timer started.",
            "pot_life_minutes": pot_life_sec / 60,
            "expires_at": self.session.pot_life_expires_at,
        })

        logger.info(f"Pot-life started: {pot_life_sec/60:.0f} minutes")

    def return_cans_phase(self) -> None:
        """Transition to can return phase after mixing is done."""
        if not self.session:
            return
        self.session.state = MixingState.RETURN_CANS

        # Light up correct slots for can returns
        self.led.clear_all()
        if self._inventory:
            if self.session.base_tag_id:
                base_slot_id = self._inventory.get_slot_id_for_tag(self.session.base_tag_id)
                if base_slot_id:
                    self.led.set_slot(base_slot_id, LEDColor.RED, LEDPattern.BLINK_SLOW)
                    logger.info(f"LED guidance: return base to slot {base_slot_id}")
            if self.session.hardener_tag_id:
                hardener_slot_id = self._inventory.get_slot_id_for_tag(self.session.hardener_tag_id)
                if hardener_slot_id:
                    self.led.set_slot(hardener_slot_id, LEDColor.RED, LEDPattern.BLINK_SLOW)
                    logger.info(f"LED guidance: return hardener to slot {hardener_slot_id}")
        self._notify_ui({"instruction": "Return all cans to their slots"})

    def complete_session(self) -> None:
        """Mark session as complete, log everything."""
        if not self.session:
            return

        self.session.state = MixingState.SESSION_COMPLETE
        self.session.completed_at = time.time()
        self.session.confirmation = EventConfirmation.CONFIRMED

        self.event_bus.publish(Event(
            event_type=EventType.MIX_COMPLETED,
            device_id=settings.DEVICE_ID,
            session_id=self.session.session_id,
            user_name=self.session.user_name,
            data={
                "recipe_id": self.session.recipe_id,
                "base_actual_g": self.session.base_weight_actual_g,
                "hardener_actual_g": self.session.hardener_weight_actual_g,
                "thinner_g": self.session.thinner_weight_g,
                "ratio_achieved": round(self.session.ratio_achieved, 2),
                "in_spec": self.session.ratio_in_spec,
                "override_reason": self.session.override_reason,
                "method": self.session.application_method.value,
                "duration_sec": self.session.completed_at - self.session.started_at,
            },
        ))

        self.led.clear_all()
        self.buzzer.play(BuzzerPattern.CONFIRM)
        self._notify_ui({"instruction": "Session complete!"})

        logger.info(
            f"Mixing session complete: {self.session.session_id} "
            f"ratio={self.session.ratio_achieved:.2f} "
            f"in_spec={self.session.ratio_in_spec}"
        )

        # Persist to database
        if self._db:
            self._save_session_to_db(self.session, status="completed")
            # Update vessel_stock: subtract consumed base + hardener
            self._update_vessel_stock_consumption(self.session)

        # Reset
        self.session = None

    def abort_session(self, reason: str = "") -> None:
        """Abort the current mixing session."""
        if not self.session:
            return

        self.event_bus.publish(Event(
            event_type=EventType.MIX_ABORTED,
            device_id=settings.DEVICE_ID,
            session_id=self.session.session_id,
            data={"reason": reason, "state_when_aborted": self.session.state.value},
        ))

        self.led.clear_all()

        # Persist to database before clearing session
        if self._db and self.session:
            self._save_session_to_db(self.session, status="aborted")

        self.session = None
        self._notify_ui({"instruction": "Session aborted"})
        logger.info(f"Mixing session aborted: {reason}")

    # ============================================================
    # LIVE WEIGHT MONITORING
    # ============================================================

    def get_current_weight(self) -> Optional[WeightReading]:
        """Read current weight on mixing scale (for UI display)."""
        try:
            return self.weight.read_weight("mixing_scale")
        except Exception as e:
            logger.warning(f"Failed to read mixing scale: {e}")
            return None

    def check_weight_target(self) -> Optional[Dict[str, Any]]:
        """
        Check if current weight has reached the target for the active pour.
        Returns status dict for UI, or None if not in a weighing state.
        """
        if not self.session:
            return None

        reading = self.get_current_weight()
        if not reading:
            return None

        if self.session.state == MixingState.WEIGH_BASE:
            target = self.session.base_weight_target_g
            current = reading.grams
        elif self.session.state == MixingState.WEIGH_HARDENER:
            target = self.session.base_weight_actual_g + self.session.hardener_weight_target_g
            current = reading.grams
        else:
            return None

        progress_pct = (current / target * 100) if target > 0 else 0
        tolerance = settings.MIX_RATIO_TOLERANCE_PCT

        # Determine zone
        if progress_pct < 90:
            zone = "pouring"
        elif progress_pct < (100 - tolerance):
            zone = "approaching"
        elif progress_pct <= (100 + tolerance):
            zone = "in_range"
        else:
            zone = "over"

        return {
            "current_g": round(current, 1),
            "target_g": round(target, 1),
            "progress_pct": round(progress_pct, 1),
            "zone": zone,
            "stable": reading.stable,
        }

    def check_pot_life(self) -> Optional[Dict[str, Any]]:
        """Check pot-life timer status. Returns None if no active timer."""
        if not self.session or self.session.pot_life_expires_at == 0:
            return None

        now = time.time()
        remaining_sec = self.session.pot_life_expires_at - now
        total_sec = self.session.pot_life_expires_at - self.session.pot_life_started_at
        elapsed_pct = ((now - self.session.pot_life_started_at) / total_sec * 100) if total_sec > 0 else 0

        if remaining_sec <= 0:
            # Expired
            if self.session.state != MixingState.SESSION_COMPLETE:
                self.event_bus.publish(Event(
                    event_type=EventType.POT_LIFE_EXPIRED,
                    device_id=settings.DEVICE_ID,
                    session_id=self.session.session_id,
                ))
                self.buzzer.play(BuzzerPattern.ERROR)
            return {"remaining_sec": 0, "expired": True, "elapsed_pct": 100}

        # Warnings at 75% and 90%
        if elapsed_pct >= 90:
            self.buzzer.play(BuzzerPattern.WARNING)
        elif elapsed_pct >= 75:
            pass  # UI shows yellow

        return {
            "remaining_sec": round(remaining_sec),
            "remaining_min": round(remaining_sec / 60, 1),
            "elapsed_pct": round(elapsed_pct, 1),
            "expired": False,
        }

    # ============================================================
    # HELPERS
    # ============================================================

    @property
    def current_state(self) -> MixingState:
        return self.session.state if self.session else MixingState.IDLE

    @property
    def is_active(self) -> bool:
        return self.session is not None and self.session.state != MixingState.IDLE

    def _update_vessel_stock_consumption(self, session: 'MixingSession') -> None:
        """Subtract consumed amounts from vessel_stock after mixing.

        Uses the actual weighed amounts (base + hardener) to decrease inventory.
        """
        try:
            # Subtract base paint
            if session.base_product_id and session.base_weight_actual_g > 0:
                # Look up product for name and density
                product = self._db.get_product_by_id(session.base_product_id)
                if product:
                    self._db.update_vessel_stock_from_barcode(
                        product_info={
                            "product_id": product.get("product_id", session.base_product_id),
                            "product_name": product.get("name", "Base"),
                            "product_type": product.get("product_type", "base_paint"),
                            "density_g_per_ml": product.get("density_g_per_ml", 1.3),
                        },
                        action="unload",
                        weight_g=session.base_weight_actual_g,
                    )
                    logger.info(
                        f"Vessel stock updated: -{session.base_weight_actual_g:.0f}g "
                        f"base ({product.get('name', '?')})"
                    )

            # Subtract hardener
            if session.hardener_product_id and session.hardener_weight_actual_g > 0:
                product = self._db.get_product_by_id(session.hardener_product_id)
                if product:
                    self._db.update_vessel_stock_from_barcode(
                        product_info={
                            "product_id": product.get("product_id", session.hardener_product_id),
                            "product_name": product.get("name", "Hardener"),
                            "product_type": product.get("product_type", "hardener"),
                            "density_g_per_ml": product.get("density_g_per_ml", 1.0),
                        },
                        action="unload",
                        weight_g=session.hardener_weight_actual_g,
                    )
                    logger.info(
                        f"Vessel stock updated: -{session.hardener_weight_actual_g:.0f}g "
                        f"hardener ({product.get('name', '?')})"
                    )

        except Exception as e:
            logger.error(f"Failed to update vessel stock after mixing: {e}")

    def _save_session_to_db(self, session: 'MixingSession', status: str = "completed") -> None:
        """Persist mixing session to database."""
        try:
            self._db.save_mixing_session(session, status=status)
            logger.info(f"Mixing session saved to DB: {session.session_id} ({status})")
        except Exception as e:
            logger.error(f"Failed to save mixing session to DB: {e}")

    def _notify_ui(self, data: Dict[str, Any]) -> None:
        """Send state change notification to UI callback."""
        state = self.session.state if self.session else MixingState.IDLE
        if self._on_state_change:
            try:
                self._on_state_change(state, data)
            except Exception as e:
                logger.error(f"UI callback error: {e}")
