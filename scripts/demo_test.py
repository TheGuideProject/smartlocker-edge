"""
Demo Test Script - Runs a complete simulated scenario.

This script demonstrates the system working in TEST mode:
1. Initializes all components with fake sensors
2. Simulates placing cans on shelves (RFID tags appear)
3. Simulates removing a can (RFID tag disappears)
4. Starts a mixing session
5. Simulates weighing base and hardener
6. Shows event log

Run this to verify the system works before real hardware arrives.

Usage:
    cd smartlocker-edge
    python -m scripts.demo_test
"""

import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.logging_config import setup_logging
from core.event_bus import EventBus
from core.event_types import Event, EventType
from core.inventory_engine import InventoryEngine
from core.mixing_engine import MixingEngine
from core.usage_calculator import UsageCalculator
from core.models import MixingRecipe, ApplicationMethod
from hal.fake.fake_rfid import FakeRFIDDriver
from hal.fake.fake_weight import FakeWeightDriver
from hal.fake.fake_led import FakeLEDDriver
from hal.fake.fake_buzzer import FakeBuzzerDriver
from persistence.database import Database


def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def print_step(num, text):
    print(f"\n--- Step {num}: {text} ---")


def main():
    logger = setup_logging()

    print_header("SMARTLOCKER DEMO - TEST MODE")

    # ============================================================
    # SETUP
    # ============================================================
    print_step(0, "Initializing system")

    # Create fake drivers
    rfid = FakeRFIDDriver()
    weight = FakeWeightDriver(channels=["shelf1", "mixing_scale"])
    led = FakeLEDDriver()
    buzzer = FakeBuzzerDriver()

    # Create core
    event_bus = EventBus()
    db = Database(db_path="data/demo_test.db")
    db.connect()

    # Track events for display
    event_log = []

    def log_event(event: Event):
        db.save_event(event)
        event_log.append(event)
        print(f"  EVENT: {event.event_type.value} "
              f"[slot={event.slot_id}, tag={event.tag_id}]")

    event_bus.subscribe_all(log_event)

    # Create engines
    inventory = InventoryEngine(
        rfid=rfid, weight=weight, led=led, buzzer=buzzer,
        event_bus=event_bus,
    )
    mixing = MixingEngine(
        weight=weight, led=led, buzzer=buzzer,
        event_bus=event_bus,
    )
    usage = UsageCalculator(event_bus=event_bus)

    # Load demo recipe
    recipe = MixingRecipe(
        recipe_id="RCP-001",
        name="SIGMACOVER 280 System",
        base_product_id="PROD-001",
        hardener_product_id="PROD-002",
        ratio_base=4.0,
        ratio_hardener=1.0,
        tolerance_pct=5.0,
        pot_life_minutes=480,
    )
    mixing.load_recipes({"RCP-001": recipe})

    # Initialize
    assert inventory.initialize(), "Failed to initialize!"
    print("  System initialized OK")

    # ============================================================
    # SCENARIO: SHELF INVENTORY
    # ============================================================
    print_step(1, "Simulating 3 paint cans placed on shelf")

    rfid.add_tag("shelf1_slot1", "TAG-BASE-001")
    rfid.add_tag("shelf1_slot2", "TAG-HARD-001")
    rfid.add_tag("shelf1_slot3", "TAG-THIN-001")
    weight.set_weight("shelf1", 18500)  # ~18.5 kg total

    inventory.poll()  # Detect all 3 cans
    time.sleep(0.1)

    slots = inventory.get_occupied_slots()
    print(f"  Occupied slots: {len(slots)}")
    for s in slots:
        print(f"    {s.slot_id}: tag={s.current_tag_id}, status={s.status.value}")

    # ============================================================
    # SCENARIO: UNAUTHORIZED REMOVAL
    # ============================================================
    print_step(2, "Simulating unauthorized can removal (no active session)")

    rfid.remove_tag("shelf1_slot3")  # Remove thinner can
    weight.set_weight("shelf1", 13500)  # Weight drops

    inventory.poll()  # Detect removal

    # ============================================================
    # SCENARIO: START MIXING SESSION
    # ============================================================
    print_step(3, "Starting mixing session via touchscreen")

    inventory.active_session = True  # Crew is using touchscreen

    success = mixing.start_session(
        recipe_id="RCP-001",
        user_name="Crew Member A",
        job_id="JOB-BT3-2026",
    )
    print(f"  Session started: {success}")

    # Show recipe (crew wants to mix 500g of base)
    mixing.show_recipe(base_amount_g=500.0)
    print(f"  Recipe: 500g base + {mixing.session.hardener_weight_target_g}g hardener")

    # ============================================================
    # SCENARIO: PICK AND WEIGH BASE
    # ============================================================
    print_step(4, "Picking base can and weighing")

    mixing.advance_to_pick_base()

    # Crew picks up base can
    rfid.remove_tag("shelf1_slot1")
    inventory.poll()

    mixing.confirm_base_picked("TAG-BASE-001")

    # Tare the mixing scale (with empty container)
    weight.set_weight("mixing_scale", 200)  # Container weight
    mixing.tare_scale()

    # Simulate pouring base (target: 500g)
    weight.set_weight("mixing_scale", 698)  # 200 (container) + 498 (base)
    print(f"  Scale reading: {weight.read_weight('mixing_scale').grams:.0f}g (target: 500g)")

    # Check target status
    status = mixing.check_weight_target()
    if status:
        print(f"  Pour status: {status['zone']} ({status['progress_pct']:.1f}%)")

    # Confirm base pour
    weight.set_weight("mixing_scale", 702)  # Final: ~502g of base
    mixing.confirm_base_weighed()
    print(f"  Base weighed: {mixing.session.base_weight_actual_g:.0f}g")

    # ============================================================
    # SCENARIO: PICK AND WEIGH HARDENER
    # ============================================================
    print_step(5, "Picking hardener can and weighing")

    rfid.remove_tag("shelf1_slot2")
    inventory.poll()

    mixing.confirm_hardener_picked("TAG-HARD-001")

    # Simulate pouring hardener (target: ~125g for 4:1 ratio)
    weight.set_weight("mixing_scale", 828)  # Previous + ~126g hardener
    mixing.confirm_hardener_weighed()

    print(f"  Hardener weighed: {mixing.session.hardener_weight_actual_g:.0f}g")
    print(f"  Ratio achieved: {mixing.session.ratio_achieved:.2f} (target: 4.0)")
    print(f"  In spec: {mixing.session.ratio_in_spec}")

    # ============================================================
    # SCENARIO: CONFIRM MIX AND ADD THINNER
    # ============================================================
    print_step(6, "Confirming mix and adding thinner")

    mixing.confirm_mix()
    mixing.skip_thinner()  # No thinner this time

    print(f"  Pot-life timer started!")
    pot_status = mixing.check_pot_life()
    if pot_status:
        print(f"  Pot-life remaining: {pot_status['remaining_min']:.0f} minutes")

    # ============================================================
    # SCENARIO: RETURN CANS
    # ============================================================
    print_step(7, "Returning cans to shelf")

    mixing.return_cans_phase()

    # Return base can
    rfid.add_tag("shelf1_slot1", "TAG-BASE-001")
    weight.set_weight("shelf1", 13000)  # Less than before (paint was used)
    inventory.poll()

    # Return hardener can
    rfid.add_tag("shelf1_slot2", "TAG-HARD-001")
    weight.set_weight("shelf1", 13800)
    inventory.poll()

    # Complete session
    mixing.complete_session()

    # ============================================================
    # SUMMARY
    # ============================================================
    print_header("DEMO COMPLETE - SUMMARY")

    print(f"  Total events generated: {len(event_log)}")
    print(f"  Events in database: {db.get_event_count()}")
    print(f"  Unsynced events: {db.get_event_count(synced=False)}")
    print()
    print("  Event timeline:")
    for i, e in enumerate(event_log):
        print(f"    {i+1}. {e.event_type.value}")

    print()
    print("  Slot states:")
    for slot in inventory.get_all_slots():
        print(f"    {slot.slot_id}: {slot.status.value} (tag={slot.current_tag_id})")

    print()
    print("  All systems working in TEST mode!")
    print("  When hardware arrives, change MODE='live' in config/settings.py")

    # Cleanup
    inventory.shutdown()
    db.close()

    # Clean up test database
    try:
        os.remove("data/demo_test.db")
        os.remove("data/demo_test.db-wal")
        os.remove("data/demo_test.db-shm")
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    main()
