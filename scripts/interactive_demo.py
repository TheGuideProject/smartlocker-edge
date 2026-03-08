"""
Interactive Demo - Control the SmartLocker from your keyboard.

This lets you simulate every action a crew member would do:
  - Place/remove cans on shelf slots
  - Start a mixing session
  - Pour base and hardener (simulated weight)
  - See real-time events and system state

Run:
    cd smartlocker-edge
    python -m scripts.interactive_demo

Commands are shown on screen. Type a command and press Enter.
"""

import sys
import os
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.logging_config import setup_logging
from core.event_bus import EventBus
from core.event_types import Event, EventType
from core.inventory_engine import InventoryEngine
from core.mixing_engine import MixingEngine
from core.usage_calculator import UsageCalculator
from core.models import MixingRecipe, MixingState, ApplicationMethod, SlotStatus
from hal.fake.fake_rfid import FakeRFIDDriver
from hal.fake.fake_weight import FakeWeightDriver
from hal.fake.fake_led import FakeLEDDriver
from hal.fake.fake_buzzer import FakeBuzzerDriver
from persistence.database import Database

# ============================================================
# COLORS FOR TERMINAL OUTPUT
# ============================================================

class C:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    DIM = "\033[2m"


# ============================================================
# GLOBAL STATE
# ============================================================

rfid: FakeRFIDDriver = None
weight: FakeWeightDriver = None
led: FakeLEDDriver = None
buzzer: FakeBuzzerDriver = None
event_bus: EventBus = None
db: Database = None
inventory: InventoryEngine = None
mixing: MixingEngine = None
usage: UsageCalculator = None

event_log = []
polling_active = False


# ============================================================
# HELPERS
# ============================================================

def print_banner():
    print(f"""
{C.BOLD}{C.CYAN}+------------------------------------------------------+
|          SMARTLOCKER - INTERACTIVE DEMO               |
|          Mode: TEST (simulated sensors)               |
+------------------------------------------------------+{C.RESET}
""")


def print_help():
    print(f"""
{C.BOLD}=== SHELF COMMANDS ==={C.RESET}
  {C.GREEN}place <slot> <tag>{C.RESET}    Place a can on a slot
                          Example: {C.DIM}place 1 BASE-001{C.RESET}
  {C.RED}remove <slot>{C.RESET}          Remove can from a slot
                          Example: {C.DIM}remove 1{C.RESET}
  {C.YELLOW}weight <grams>{C.RESET}        Set shelf total weight
                          Example: {C.DIM}weight 15000{C.RESET}

{C.BOLD}=== MIXING COMMANDS ==={C.RESET}
  {C.GREEN}mix{C.RESET}                   Start a mixing session
  {C.GREEN}recipe <base_grams>{C.RESET}   Set how much base to mix
                          Example: {C.DIM}recipe 500{C.RESET}
  {C.GREEN}pick_base{C.RESET}             Ready to pick base can
  {C.GREEN}pick_hardener{C.RESET}         Ready to pick hardener can
  {C.GREEN}tare{C.RESET}                  Tare the mixing scale
  {C.GREEN}pour <grams>{C.RESET}          Set mixing scale weight (simulates pouring)
                          Example: {C.DIM}pour 500{C.RESET}
  {C.GREEN}weigh_base{C.RESET}            Confirm base pour done
  {C.GREEN}weigh_hardener{C.RESET}        Confirm hardener pour done
  {C.GREEN}confirm{C.RESET}               Confirm the mix
  {C.GREEN}thinner <method>{C.RESET}      Add thinner (brush/roller/spray)
  {C.GREEN}skip_thinner{C.RESET}          Skip thinner
  {C.GREEN}complete{C.RESET}              Complete the session
  {C.GREEN}abort{C.RESET}                 Abort current session

{C.BOLD}=== INFO COMMANDS ==={C.RESET}
  {C.BLUE}status{C.RESET}                Show all slot states
  {C.BLUE}events{C.RESET}                Show event history
  {C.BLUE}mixing_status{C.RESET}         Show current mixing state
  {C.BLUE}scale{C.RESET}                 Show mixing scale reading
  {C.BLUE}potlife{C.RESET}               Show pot-life timer
  {C.BLUE}help{C.RESET}                  Show this help
  {C.BLUE}quit{C.RESET}                  Exit

""")


def print_event(event: Event):
    """Display an event in a readable format."""
    color = C.GREEN
    if "error" in event.event_type.value or "unauthorized" in event.event_type.value:
        color = C.RED
    elif "warning" in event.event_type.value or "out_of_spec" in event.event_type.value:
        color = C.YELLOW

    parts = [f"  {color}[EVENT]{C.RESET} {event.event_type.value}"]
    if event.slot_id:
        parts.append(f"slot={event.slot_id}")
    if event.tag_id:
        parts.append(f"tag={event.tag_id}")
    if event.session_id:
        parts.append(f"session={event.session_id[:8]}...")

    print(" | ".join(parts))


def print_status():
    """Show current state of all slots."""
    print(f"\n{C.BOLD}=== SHELF STATUS ==={C.RESET}")
    for slot in inventory.get_all_slots():
        if slot.status == SlotStatus.OCCUPIED:
            icon = f"{C.GREEN}[CAN]{C.RESET}"
        elif slot.status == SlotStatus.REMOVED:
            icon = f"{C.YELLOW}[REMOVED]{C.RESET}"
        elif slot.status == SlotStatus.IN_USE_ELSEWHERE:
            icon = f"{C.RED}[IN USE]{C.RESET}"
        else:
            icon = f"{C.DIM}[EMPTY]{C.RESET}"

        tag_str = slot.current_tag_id or "---"
        print(f"  Slot {slot.position}: {icon}  tag={tag_str}  status={slot.status.value}")

    # Shelf weight
    try:
        w = weight.read_weight("shelf1")
        print(f"\n  Shelf weight: {w.grams:.0f}g")
    except:
        pass

    # Mixing scale
    try:
        w = weight.read_weight("mixing_scale")
        print(f"  Mixing scale: {w.grams:.0f}g")
    except:
        pass
    print()


def print_mixing_status():
    """Show current mixing session state."""
    if not mixing.session:
        print(f"\n  {C.DIM}No active mixing session.{C.RESET}")
        print(f"  Type {C.GREEN}'mix'{C.RESET} to start one.\n")
        return

    s = mixing.session
    print(f"\n{C.BOLD}=== MIXING SESSION ==={C.RESET}")
    print(f"  Session ID:  {s.session_id[:12]}...")
    print(f"  State:       {C.CYAN}{s.state.value}{C.RESET}")
    print(f"  User:        {s.user_name}")
    print(f"  Recipe:      {s.recipe_id}")

    if s.base_weight_target_g > 0:
        print(f"\n  {C.BOLD}Base:{C.RESET}")
        print(f"    Target:  {s.base_weight_target_g:.0f}g")
        print(f"    Actual:  {s.base_weight_actual_g:.0f}g")

    if s.hardener_weight_target_g > 0:
        print(f"\n  {C.BOLD}Hardener:{C.RESET}")
        print(f"    Target:  {s.hardener_weight_target_g:.0f}g")
        print(f"    Actual:  {s.hardener_weight_actual_g:.0f}g")

    if s.ratio_achieved > 0:
        color = C.GREEN if s.ratio_in_spec else C.RED
        print(f"\n  {C.BOLD}Ratio:{C.RESET} {color}{s.ratio_achieved:.2f}{C.RESET} (target: 4.0, tolerance: ±5%)")
        print(f"  In spec: {color}{s.ratio_in_spec}{C.RESET}")

    if s.override_reason:
        print(f"  Override: {C.YELLOW}{s.override_reason}{C.RESET}")

    print()


def print_scale():
    """Show mixing scale reading and target progress."""
    reading = mixing.get_current_weight()
    if not reading:
        print(f"  {C.DIM}Scale not available{C.RESET}")
        return

    print(f"\n  Mixing scale: {C.BOLD}{reading.grams:.1f}g{C.RESET}")

    target_info = mixing.check_weight_target()
    if target_info:
        zone = target_info["zone"]
        pct = target_info["progress_pct"]

        # Visual progress bar
        bar_len = 30
        filled = int(bar_len * min(pct, 100) / 100)
        bar = "#" * filled + "-" * (bar_len - filled)

        if zone == "in_range":
            color = C.GREEN
        elif zone == "approaching":
            color = C.YELLOW
        elif zone == "over":
            color = C.RED
        else:
            color = C.BLUE

        print(f"  Target:      {target_info['target_g']:.0f}g")
        print(f"  Progress:    {color}[{bar}] {pct:.1f}%{C.RESET}")
        print(f"  Zone:        {color}{zone}{C.RESET}")
    print()


def print_potlife():
    """Show pot-life timer."""
    info = mixing.check_pot_life()
    if not info:
        print(f"  {C.DIM}No active pot-life timer.{C.RESET}\n")
        return

    if info["expired"]:
        print(f"  {C.RED}{C.BOLD}POT-LIFE EXPIRED!{C.RESET}")
    else:
        remaining = info["remaining_min"]
        pct = info["elapsed_pct"]

        bar_len = 30
        filled = int(bar_len * pct / 100)
        bar = "#" * filled + "-" * (bar_len - filled)

        if pct < 75:
            color = C.GREEN
        elif pct < 90:
            color = C.YELLOW
        else:
            color = C.RED

        print(f"\n  Pot-life: {color}[{bar}] {pct:.0f}% used{C.RESET}")
        print(f"  Remaining: {C.BOLD}{remaining:.0f} minutes{C.RESET}")
    print()


def print_events():
    """Show recent events."""
    print(f"\n{C.BOLD}=== EVENT LOG (last 15) ==={C.RESET}")
    recent = event_log[-15:]
    for i, e in enumerate(recent):
        idx = len(event_log) - len(recent) + i + 1
        color = C.GREEN
        if "error" in e.event_type.value or "unauthorized" in e.event_type.value:
            color = C.RED
        elif "warning" in e.event_type.value or "out_of_spec" in e.event_type.value:
            color = C.YELLOW
        print(f"  {C.DIM}{idx:3d}.{C.RESET} {color}{e.event_type.value}{C.RESET}")
    print(f"\n  Total events: {len(event_log)}  |  In DB: {db.get_event_count()}")
    print()


# ============================================================
# BACKGROUND POLLING
# ============================================================

def polling_loop():
    """Background thread that polls sensors."""
    global polling_active
    while polling_active:
        inventory.poll()
        time.sleep(0.5)


# ============================================================
# COMMAND PROCESSING
# ============================================================

def process_command(cmd: str) -> bool:
    """Process a user command. Returns False to quit."""
    parts = cmd.strip().split()
    if not parts:
        return True

    action = parts[0].lower()

    # --- SHELF COMMANDS ---

    if action == "place" and len(parts) >= 3:
        slot_num = parts[1]
        tag_id = parts[2]
        slot_id = f"shelf1_slot{slot_num}"
        try:
            rfid.add_tag(slot_id, tag_id)
            print(f"  {C.GREEN}Placed tag '{tag_id}' on slot {slot_num}{C.RESET}")
        except ValueError as e:
            print(f"  {C.RED}Error: {e}{C.RESET}")

    elif action == "remove" and len(parts) >= 2:
        slot_num = parts[1]
        slot_id = f"shelf1_slot{slot_num}"
        try:
            rfid.remove_tag(slot_id)
            print(f"  {C.YELLOW}Removed can from slot {slot_num}{C.RESET}")
        except ValueError as e:
            print(f"  {C.RED}Error: {e}{C.RESET}")

    elif action == "weight" and len(parts) >= 2:
        try:
            grams = float(parts[1])
            weight.set_weight("shelf1", grams)
            print(f"  Shelf weight set to {grams:.0f}g")
        except ValueError:
            print(f"  {C.RED}Invalid weight. Use: weight 15000{C.RESET}")

    # --- MIXING COMMANDS ---

    elif action == "mix":
        inventory.active_session = True
        user_name = " ".join(parts[1:]) if len(parts) > 1 else "Crew Demo"
        ok = mixing.start_session("RCP-001", user_name=user_name)
        if ok:
            print(f"  {C.GREEN}Mixing session started!{C.RESET}")
            print(f"  Now type: {C.CYAN}recipe 500{C.RESET} (to mix 500g of base)")
        else:
            print(f"  {C.RED}Failed to start session (already active?){C.RESET}")

    elif action == "recipe" and len(parts) >= 2:
        try:
            base_g = float(parts[1])
            mixing.show_recipe(base_g)
            if mixing.session:
                h = mixing.session.hardener_weight_target_g
                print(f"  Recipe: {base_g:.0f}g base + {h:.0f}g hardener (ratio 4:1)")
                print(f"  Now type: {C.CYAN}pick_base{C.RESET}")
        except ValueError:
            print(f"  {C.RED}Invalid amount. Use: recipe 500{C.RESET}")

    elif action == "pick_base":
        mixing.advance_to_pick_base()
        print(f"  {C.GREEN}Pick the base can from the shelf.{C.RESET}")
        print(f"  Type: {C.CYAN}remove <slot>{C.RESET} to simulate picking it up")

    elif action == "picked_base" or action == "base_picked":
        tag = parts[1] if len(parts) > 1 else "BASE-001"
        mixing.confirm_base_picked(tag)
        print(f"  Base can picked (tag: {tag})")
        print(f"  Type: {C.CYAN}tare{C.RESET} then {C.CYAN}pour <grams>{C.RESET} then {C.CYAN}weigh_base{C.RESET}")

    elif action == "pick_hardener":
        print(f"  {C.GREEN}Pick the hardener can from the shelf.{C.RESET}")
        print(f"  Type: {C.CYAN}remove <slot>{C.RESET} to simulate picking it up")

    elif action == "picked_hardener" or action == "hardener_picked":
        tag = parts[1] if len(parts) > 1 else "HARD-001"
        mixing.confirm_hardener_picked(tag)
        print(f"  Hardener can picked (tag: {tag})")
        print(f"  Type: {C.CYAN}pour <grams>{C.RESET} then {C.CYAN}weigh_hardener{C.RESET}")

    elif action == "tare":
        ok = mixing.tare_scale()
        if ok:
            print(f"  {C.GREEN}Scale tared to zero.{C.RESET}")
        else:
            print(f"  {C.RED}Tare failed.{C.RESET}")

    elif action == "pour" and len(parts) >= 2:
        try:
            grams = float(parts[1])
            # Set absolute weight on scale (after tare, so this is the poured amount)
            weight.set_weight("mixing_scale", weight._tare["mixing_scale"] + grams)
            print(f"  Scale reading: {grams:.0f}g poured")
            print_scale()
        except ValueError:
            print(f"  {C.RED}Invalid weight. Use: pour 500{C.RESET}")

    elif action == "weigh_base":
        mixing.confirm_base_weighed()
        if mixing.session:
            print(f"  {C.GREEN}Base weighed: {mixing.session.base_weight_actual_g:.0f}g{C.RESET}")
            print(f"  Now: {C.CYAN}pick_hardener{C.RESET} -> {C.CYAN}remove <slot>{C.RESET} -> {C.CYAN}picked_hardener{C.RESET}")

    elif action == "weigh_hardener":
        mixing.confirm_hardener_weighed()
        if mixing.session:
            s = mixing.session
            color = C.GREEN if s.ratio_in_spec else C.RED
            print(f"  {C.GREEN}Hardener weighed: {s.hardener_weight_actual_g:.0f}g{C.RESET}")
            print(f"  Ratio: {color}{s.ratio_achieved:.2f}{C.RESET} (target: 4.0)")
            print(f"  In spec: {color}{s.ratio_in_spec}{C.RESET}")
            print(f"  Type: {C.CYAN}confirm{C.RESET}")

    elif action == "confirm":
        reason = " ".join(parts[1:]) if len(parts) > 1 else ""
        mixing.confirm_mix(override_reason=reason)
        print(f"  {C.GREEN}Mix confirmed!{C.RESET}")
        print(f"  Type: {C.CYAN}skip_thinner{C.RESET} or {C.CYAN}thinner brush{C.RESET}")

    elif action == "thinner" and len(parts) >= 2:
        method_map = {
            "brush": ApplicationMethod.BRUSH,
            "roller": ApplicationMethod.ROLLER,
            "spray": ApplicationMethod.SPRAY,
        }
        method = method_map.get(parts[1].lower())
        if method:
            mixing.add_thinner(method, thinner_weight_g=0)
            print(f"  Thinner added for {parts[1]} application.")
            print_potlife()
            print(f"  Return cans, then type: {C.CYAN}complete{C.RESET}")
        else:
            print(f"  {C.RED}Unknown method. Use: brush, roller, or spray{C.RESET}")

    elif action == "skip_thinner":
        mixing.skip_thinner()
        print(f"  Thinner skipped. Pot-life timer started!")
        print_potlife()
        print(f"  Return cans to shelf, then type: {C.CYAN}complete{C.RESET}")

    elif action == "complete":
        mixing.complete_session()
        inventory.active_session = False
        print(f"  {C.GREEN}{C.BOLD}Session complete!{C.RESET}")

    elif action == "abort":
        reason = " ".join(parts[1:]) if len(parts) > 1 else "User aborted"
        mixing.abort_session(reason)
        inventory.active_session = False
        print(f"  {C.YELLOW}Session aborted: {reason}{C.RESET}")

    # --- INFO COMMANDS ---

    elif action == "status":
        print_status()

    elif action == "events":
        print_events()

    elif action in ("mixing_status", "mix_status", "ms"):
        print_mixing_status()

    elif action == "scale":
        print_scale()

    elif action == "potlife":
        print_potlife()

    elif action == "help":
        print_help()

    elif action in ("quit", "exit", "q"):
        return False

    else:
        print(f"  {C.DIM}Unknown command: '{action}'. Type 'help' for commands.{C.RESET}")

    return True


# ============================================================
# MAIN
# ============================================================

def main():
    global rfid, weight, led, buzzer, event_bus, db
    global inventory, mixing, usage, polling_active

    # Suppress sensor log noise in interactive mode
    import logging
    logging.getLogger("smartlocker.sensor").setLevel(logging.WARNING)
    logger = setup_logging()
    logging.getLogger("smartlocker").setLevel(logging.WARNING)

    print_banner()

    # Create components
    rfid = FakeRFIDDriver()
    weight = FakeWeightDriver(channels=["shelf1", "mixing_scale"])
    weight.set_noise(False)  # Disable noise for cleaner demo
    led = FakeLEDDriver()
    buzzer = FakeBuzzerDriver()
    event_bus = EventBus()
    db = Database(db_path="data/interactive_demo.db")
    db.connect()

    def on_event(event: Event):
        db.save_event(event)
        event_log.append(event)
        print_event(event)

    event_bus.subscribe_all(on_event)

    inventory = InventoryEngine(
        rfid=rfid, weight=weight, led=led, buzzer=buzzer,
        event_bus=event_bus,
    )
    mixing = MixingEngine(
        weight=weight, led=led, buzzer=buzzer,
        event_bus=event_bus,
    )
    usage = UsageCalculator(event_bus=event_bus)

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

    inventory.initialize()

    # Start background polling
    polling_active = True
    poll_thread = threading.Thread(target=polling_loop, daemon=True)
    poll_thread.start()

    print(f"  System ready. Type {C.GREEN}'help'{C.RESET} for commands.\n")
    print(f"  {C.BOLD}Quick start:{C.RESET}")
    print(f"    1. {C.CYAN}place 1 BASE-001{C.RESET}     (put a base can on slot 1)")
    print(f"    2. {C.CYAN}place 2 HARD-001{C.RESET}     (put a hardener can on slot 2)")
    print(f"    3. {C.CYAN}status{C.RESET}               (see shelf state)")
    print(f"    4. {C.CYAN}mix{C.RESET}                  (start a mixing session)")
    print()

    # Command loop
    try:
        while True:
            try:
                cmd = input(f"{C.BOLD}locker>{C.RESET} ")
                if not process_command(cmd):
                    break
            except EOFError:
                break
    except KeyboardInterrupt:
        pass

    # Cleanup
    print(f"\n{C.DIM}Shutting down...{C.RESET}")
    polling_active = False
    poll_thread.join(timeout=2)
    inventory.shutdown()
    db.close()

    try:
        os.remove("data/interactive_demo.db")
        os.remove("data/interactive_demo.db-wal")
        os.remove("data/interactive_demo.db-shm")
    except FileNotFoundError:
        pass

    print("Bye!")


if __name__ == "__main__":
    main()
