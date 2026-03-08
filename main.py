"""
SmartLocker Edge - Main Entry Point

Starts the application in TEST or LIVE mode based on config/settings.py.
In TEST mode: uses simulated sensors (runs on any laptop).
In LIVE mode: uses real PN532, Arduino, WS2812, buzzer (runs on RPi5).

Usage:
    python main.py              # Runs in whatever MODE is set in settings.py
    python main.py --test       # Force TEST mode
    python main.py --live       # Force LIVE mode
"""

import sys
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


def create_drivers(mode: str):
    """Create sensor drivers based on mode (test/live)."""
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

    elif mode == "live":
        # These will be implemented when real hardware arrives
        raise NotImplementedError(
            "LIVE mode drivers not yet implemented. "
            "Waiting for hardware delivery (~2 weeks). "
            "Use TEST mode for now."
        )
    else:
        raise ValueError(f"Unknown mode: {mode}. Use 'test' or 'live'.")

    return rfid, weight, led, buzzer


def load_demo_data(db: Database, mixing_engine: MixingEngine):
    """Load sample products and recipes for testing."""
    # Sample products
    products = [
        {
            "product_id": "PROD-001",
            "ppg_code": "SIGMA-280",
            "name": "SIGMACOVER 280 Base",
            "product_type": "base_paint",
            "density_g_per_ml": 1.4,
            "pot_life_minutes": 480,
            "hazard_class": "flammable",
            "can_sizes_ml": [5000],
            "can_tare_weight_g": {"5000": 400},
        },
        {
            "product_id": "PROD-002",
            "ppg_code": "SIGMA-280-H",
            "name": "SIGMACOVER 280 Hardener",
            "product_type": "hardener",
            "density_g_per_ml": 1.1,
            "can_sizes_ml": [1000],
            "can_tare_weight_g": {"1000": 150},
        },
        {
            "product_id": "PROD-003",
            "ppg_code": "SIGMA-THIN-91",
            "name": "SIGMA Thinner 91-92",
            "product_type": "thinner",
            "density_g_per_ml": 0.87,
            "can_sizes_ml": [5000],
            "can_tare_weight_g": {"5000": 400},
        },
    ]

    for p in products:
        db.upsert_product(p)

    # Sample mixing recipe
    recipe_data = {
        "recipe_id": "RCP-001",
        "name": "SIGMACOVER 280 System",
        "base_product_id": "PROD-001",
        "hardener_product_id": "PROD-002",
        "ratio_base": 4.0,
        "ratio_hardener": 1.0,
        "tolerance_pct": 5.0,
        "thinner_pct_brush": 5.0,
        "thinner_pct_roller": 5.0,
        "thinner_pct_spray": 10.0,
        "recommended_thinner_id": "PROD-003",
        "pot_life_minutes": 480,
    }
    db.upsert_recipe(recipe_data)

    # Load into mixing engine
    recipe = MixingRecipe(**recipe_data)
    mixing_engine.load_recipes({"RCP-001": recipe})

    print(f"  Loaded {len(products)} demo products and 1 recipe")


def main():
    # Parse command line
    mode = MODE
    if "--test" in sys.argv:
        mode = "test"
    elif "--live" in sys.argv:
        mode = "live"

    # Setup
    logger = setup_logging()

    print("=" * 60)
    print("  SMARTLOCKER EDGE")
    print(f"  Device: {DEVICE_ID}")
    print(f"  Mode: {mode.upper()}")
    print("=" * 60)

    # Create drivers
    rfid, weight, led, buzzer = create_drivers(mode)

    # Create core components
    event_bus = EventBus()
    db = Database()
    db.connect()

    # Wire event logging to database
    def log_event_to_db(event: Event):
        db.save_event(event)
        db.enqueue_for_sync(event)

    event_bus.subscribe_all(log_event_to_db)

    # Create engines
    inventory_engine = InventoryEngine(
        rfid=rfid, weight=weight, led=led, buzzer=buzzer,
        event_bus=event_bus,
    )
    mixing_engine = MixingEngine(
        weight=weight, led=led, buzzer=buzzer,
        event_bus=event_bus,
    )
    usage_calculator = UsageCalculator(event_bus=event_bus)

    # Initialize
    if not inventory_engine.initialize():
        print("ERROR: Failed to initialize sensors. Check hardware.")
        sys.exit(1)

    # ---- Cloud Sync ----
    cloud = CloudClient()
    sync_engine = SyncEngine(db, cloud)

    if cloud.is_paired:
        info = cloud.get_pairing_info()
        print(f"  Cloud: PAIRED")
        print(f"  Vessel: {info.get('vessel_name', 'N/A')}")
        print(f"  Company: {info.get('company_name', 'N/A')}")
        print(f"  Cloud URL: {info.get('cloud_url', 'N/A')}")

        # Start background sync
        sync_engine.start()
        print("  Sync: ACTIVE (background)")
    else:
        print("  Cloud: NOT PAIRED")
        print("  Run 'python scripts/pair_device.py' to connect to cloud")

        # Load demo data only if not paired (paired devices get data from cloud)
        load_demo_data(db, mixing_engine)

    print()
    print("  System ready. Starting main loop...")
    print("  Press Ctrl+C to stop.")
    print()

    # Main loop
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


if __name__ == "__main__":
    main()
