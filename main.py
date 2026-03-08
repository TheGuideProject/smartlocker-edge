"""
SmartLocker Edge - Main Entry Point

Starts the Kivy touchscreen application by default.
Use --cli flag for terminal-only mode (no GUI).

Usage:
    python main.py              # Kivy UI (default)
    python main.py --cli        # Terminal-only mode (no GUI)
    python main.py --test       # Force TEST mode
    python main.py --live       # Force LIVE mode
"""

import sys


def main_cli():
    """Terminal-only mode (no Kivy GUI) — useful for headless testing."""
    import time
    import logging

    from config.settings import MODE, DEVICE_ID, RFID_POLL_INTERVAL_MS
    from config.logging_config import setup_logging
    from core.event_bus import EventBus
    from core.event_types import Event, EventType
    from core.inventory_engine import InventoryEngine
    from core.mixing_engine import MixingEngine
    from core.usage_calculator import UsageCalculator
    from core.models import MixingRecipe
    from persistence.database import Database
    from sync.cloud_client import CloudClient
    from sync.sync_engine import SyncEngine

    mode = MODE
    if "--test" in sys.argv:
        mode = "test"
    elif "--live" in sys.argv:
        mode = "live"

    logger = setup_logging()

    print("=" * 60)
    print("  SMARTLOCKER EDGE (CLI MODE)")
    print(f"  Device: {DEVICE_ID}")
    print(f"  Mode: {mode.upper()}")
    print("=" * 60)

    # Create drivers
    if mode == "test":
        from hal.fake.fake_rfid import FakeRFIDDriver
        from hal.fake.fake_weight import FakeWeightDriver
        from hal.fake.fake_led import FakeLEDDriver
        from hal.fake.fake_buzzer import FakeBuzzerDriver

        rfid = FakeRFIDDriver()
        weight = FakeWeightDriver()
        led = FakeLEDDriver()
        buzzer = FakeBuzzerDriver()
        print(f"  Mode: TEST (simulated sensors)")
    else:
        raise NotImplementedError("LIVE mode not yet implemented.")

    # Create core components
    event_bus = EventBus()
    db = Database()
    db.connect()

    def log_event_to_db(event: Event):
        db.save_event(event)
        db.enqueue_for_sync(event)

    event_bus.subscribe_all(log_event_to_db)

    inventory_engine = InventoryEngine(
        rfid=rfid, weight=weight, led=led, buzzer=buzzer,
        event_bus=event_bus,
    )
    mixing_engine = MixingEngine(
        weight=weight, led=led, buzzer=buzzer,
        event_bus=event_bus,
    )

    if not inventory_engine.initialize():
        print("ERROR: Failed to initialize sensors.")
        sys.exit(1)

    cloud = CloudClient()
    sync_engine = SyncEngine(db, cloud)

    if cloud.is_paired:
        info = cloud.get_pairing_info()
        print(f"  Cloud: PAIRED — {info.get('vessel_name', 'N/A')}")
        sync_engine.start()
    else:
        print("  Cloud: NOT PAIRED")

    print("\n  System ready (CLI mode). Press Ctrl+C to stop.\n")

    poll_interval = RFID_POLL_INTERVAL_MS / 1000.0
    try:
        while True:
            inventory_engine.poll()
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        sync_engine.stop()
        inventory_engine.shutdown()
        db.close()
        print("SmartLocker stopped.")


def main_ui():
    """Start the Kivy touchscreen UI (default mode)."""
    from ui.app import SmartLockerApp
    SmartLockerApp().run()


if __name__ == "__main__":
    if "--cli" in sys.argv:
        main_cli()
    else:
        main_ui()
