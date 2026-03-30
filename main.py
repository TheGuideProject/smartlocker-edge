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

    from config.settings import (
        MODE, DEVICE_ID, RFID_POLL_INTERVAL_MS,
        DRIVER_RFID, DRIVER_WEIGHT, DRIVER_LED, DRIVER_BUZZER,
    )
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

    # Resolve mode: CLI flags override config file
    cfg_mode = MODE
    if "--test" in sys.argv:
        cfg_mode = "test"
    elif "--live" in sys.argv:
        cfg_mode = "live"

    # Resolve per-sensor driver selections
    if cfg_mode == "test":
        drv_rfid = drv_weight = drv_led = drv_buzzer = "fake"
    elif cfg_mode == "live":
        drv_rfid = drv_weight = drv_led = drv_buzzer = "real"
    else:
        drv_rfid = DRIVER_RFID
        drv_weight = DRIVER_WEIGHT
        drv_led = DRIVER_LED
        drv_buzzer = DRIVER_BUZZER

    # Determine overall system mode
    drivers = [drv_rfid, drv_weight, drv_led, drv_buzzer]
    any_real = any(d == "real" for d in drivers)
    all_real = all(d == "real" for d in drivers)
    if all_real:
        mode = "live"
    elif any_real:
        mode = "hybrid"
    else:
        mode = "test"

    logger = setup_logging()

    print("=" * 60)
    print("  SMARTLOCKER EDGE (CLI MODE)")
    print(f"  Device: {DEVICE_ID}")
    print(f"  Mode: {mode.upper()}")
    print("=" * 60)

    # ---- RFID Driver ----
    if drv_rfid == "real":
        from config.settings import RFID_MODULE
        if RFID_MODULE == "pn532_usb":
            from hal.real.real_rfid_pn532_usb import RealRFIDDriverPN532USB
            rfid = RealRFIDDriverPN532USB()
        elif RFID_MODULE == "rc522":
            from hal.real.real_rfid_rc522 import RealRFIDDriverRC522
            rfid = RealRFIDDriverRC522()
        else:
            from hal.real.real_rfid import RealRFIDDriver
            rfid = RealRFIDDriver()
    else:
        from hal.fake.fake_rfid import FakeRFIDDriver
        rfid = FakeRFIDDriver()

    # ---- Weight Driver ----
    if drv_weight == "real":
        from config.settings import WEIGHT_MODE
        if WEIGHT_MODE == "hx711_direct":
            from hal.real.real_weight_hx711 import RealWeightDriverHX711
            weight = RealWeightDriverHX711()
        else:
            from hal.real.real_weight import RealWeightDriver
            weight = RealWeightDriver()
    else:
        from hal.fake.fake_weight import FakeWeightDriver
        weight = FakeWeightDriver()

    # ---- LED Driver ----
    if drv_led == "real":
        from hal.real.real_led import RealLEDDriver
        led = RealLEDDriver()
    else:
        from hal.fake.fake_led import FakeLEDDriver
        led = FakeLEDDriver()

    # ---- Buzzer Driver ----
    if drv_buzzer == "real":
        from hal.real.real_buzzer import RealBuzzerDriver
        buzzer = RealBuzzerDriver()
    else:
        from hal.fake.fake_buzzer import FakeBuzzerDriver
        buzzer = FakeBuzzerDriver()

    # Log driver status
    driver_status = {'rfid': drv_rfid, 'weight': drv_weight, 'led': drv_led, 'buzzer': drv_buzzer}
    if mode == 'hybrid':
        real_list = [k for k, v in driver_status.items() if v == 'real']
        fake_list = [k for k, v in driver_status.items() if v == 'fake']
        print(f"  Drivers - Real: {', '.join(real_list)} | Fake: {', '.join(fake_list)}")
    else:
        print(f"  All drivers: {'REAL' if mode == 'live' else 'FAKE (simulated)'}")

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
    inventory_engine.set_database(db)

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
    import os

    # Kivy configuration MUST be set before importing kivy modules
    os.environ.setdefault('KIVY_NO_CONSOLELOG', '1')
    os.environ.setdefault('KIVY_LOG_LEVEL', 'warning')

    from kivy.config import Config

    # Load saved display mode (touch43=800x480, desktop=1280x800)
    from ui.display_mode import DisplayMode, MODES
    dm = DisplayMode.instance()
    preset = dm.get_preset()
    Config.set('graphics', 'width', str(preset['width']))
    Config.set('graphics', 'height', str(preset['height']))
    Config.set('graphics', 'resizable', '1')
    Config.set('graphics', 'minimum_width', '800')
    Config.set('graphics', 'minimum_height', '480')

    # Touch input: disable multitouch emulation (red dots on right-click)
    Config.set('input', 'mouse', 'mouse,multitouch_on_demand')

    # Disable Kivy settings panel (gesture from bottom)
    Config.set('kivy', 'exit_on_escape', '1')

    # Enable docked virtual keyboard globally for touchscreen use
    # This makes a virtual keyboard appear at bottom when any TextInput gets focus
    Config.set('kivy', 'keyboard_mode', 'dock')

    from ui.app import SmartLockerApp
    SmartLockerApp().run()


def main_qt():
    """Start the PySide6 modern UI (new default)."""
    from ui_qt.app import run_qt_app
    run_qt_app()


if __name__ == "__main__":
    if "--cli" in sys.argv:
        main_cli()
    elif "--kivy" in sys.argv:
        main_ui()  # Legacy Kivy UI
    else:
        main_qt()  # New PySide6 UI (default)
