"""
SmartLocker Kivy Application

Main application class that:
1. Initializes the entire system (drivers, engines, database)
2. Creates the screen manager with all UI screens
3. Runs the sensor polling loop via Kivy Clock
4. Shows pairing screen on first boot if not paired to cloud
"""

import os
import sys
import time
import logging

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, SlideTransition
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.core.window import Window

# ============================================================
# GLOBAL KV STYLES
# ============================================================
Builder.load_string('''
#:import utils kivy.utils

<StatusBar@BoxLayout>:
    size_hint_y: None
    height: '48dp'
    padding: [15, 5]
    spacing: 10
    canvas.before:
        Color:
            rgba: 0.07, 0.13, 0.22, 1
        Rectangle:
            pos: self.pos
            size: self.size
        Color:
            rgba: 0.18, 0.77, 0.71, 0.4
        Rectangle:
            pos: self.x, self.y
            size: self.width, 1

<NavButton@Button>:
    background_normal: ''
    background_color: 0.11, 0.29, 0.40, 1
    color: 1, 1, 1, 1
    font_size: '20sp'
    bold: True
    size_hint_y: None
    height: '70dp'
    markup: True

<GreenButton@Button>:
    background_normal: ''
    background_color: 0.18, 0.77, 0.71, 1
    color: 1, 1, 1, 1
    font_size: '18sp'
    bold: True
    size_hint_y: None
    height: '60dp'

<DangerButton@Button>:
    background_normal: ''
    background_color: 0.90, 0.22, 0.27, 1
    color: 1, 1, 1, 1
    font_size: '18sp'
    bold: True
    size_hint_y: None
    height: '60dp'

<SecondaryButton@Button>:
    background_normal: ''
    background_color: 0.20, 0.25, 0.35, 1
    color: 0.8, 0.85, 0.92, 1
    font_size: '16sp'
    size_hint_y: None
    height: '55dp'

<ScreenTitle@Label>:
    font_size: '22sp'
    bold: True
    color: 1, 1, 1, 1
    size_hint_y: None
    height: '40dp'
    halign: 'left'
    text_size: self.size
    valign: 'middle'

<InfoLabel@Label>:
    font_size: '16sp'
    color: 0.75, 0.80, 0.88, 1
    halign: 'left'
    text_size: self.size
    valign: 'top'
    markup: True
''')


class SmartLockerApp(App):
    """Main Kivy application for the SmartLocker touchscreen."""

    title = 'SmartLocker'

    def build(self):
        """Initialize system and create UI."""
        Window.clearcolor = (0.05, 0.11, 0.16, 1)  # Dark navy background

        # Initialize system components
        self._init_system()

        # Create screen manager
        self.sm = ScreenManager(transition=SlideTransition(duration=0.2))

        # Import and add screens
        from ui.screens.home import HomeScreen
        from ui.screens.inventory import InventoryScreen
        from ui.screens.mixing import MixingScreen
        from ui.screens.demo import DemoScreen
        from ui.screens.pairing import PairingScreen
        from ui.screens.settings import SettingsScreen

        # Add pairing screen FIRST (so it's the default if not paired)
        self.sm.add_widget(PairingScreen(name='pairing'))
        self.sm.add_widget(HomeScreen(name='home'))
        self.sm.add_widget(InventoryScreen(name='inventory'))
        self.sm.add_widget(MixingScreen(name='mixing'))
        self.sm.add_widget(DemoScreen(name='demo'))
        self.sm.add_widget(SettingsScreen(name='settings'))

        # Decide initial screen based on pairing status
        if self.cloud.is_paired:
            # Already paired → go straight to home
            self.sm.current = 'home'

            # Start background sync
            self.sync_engine.start()
            print("  Cloud: PAIRED — sync started")
        else:
            # Not paired → show pairing screen
            self.sm.current = 'pairing'
            print("  Cloud: NOT PAIRED — showing pairing screen")

        # Start sensor polling loop (every 500ms)
        Clock.schedule_interval(self._poll_sensors, 0.5)

        return self.sm

    def _init_system(self):
        """Initialize all system components (same as main.py)."""
        from config.settings import MODE, DEVICE_ID
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

        self.mode = MODE
        self.device_id = DEVICE_ID
        self.logger = setup_logging()

        # Create event bus
        self.event_bus = EventBus()

        # Create database
        self.db = Database()
        self.db.connect()

        # Event log for UI display
        self.event_log = []

        def _log_event(event):
            self.db.save_event(event)
            self.db.enqueue_for_sync(event)
            self.event_log.append(event)
            # Keep last 50 events in memory
            if len(self.event_log) > 50:
                self.event_log = self.event_log[-50:]

        self.event_bus.subscribe_all(_log_event)

        # Create drivers based on mode
        if self.mode == 'test':
            from hal.fake.fake_rfid import FakeRFIDDriver
            from hal.fake.fake_weight import FakeWeightDriver
            from hal.fake.fake_led import FakeLEDDriver
            from hal.fake.fake_buzzer import FakeBuzzerDriver

            self.rfid = FakeRFIDDriver()
            self.weight = FakeWeightDriver(channels=['shelf1', 'mixing_scale'])
            self.led = FakeLEDDriver()
            self.buzzer = FakeBuzzerDriver()
        else:
            raise NotImplementedError(
                "LIVE mode not yet implemented. Use TEST mode for now."
            )

        # Create engines
        self.inventory = InventoryEngine(
            rfid=self.rfid, weight=self.weight,
            led=self.led, buzzer=self.buzzer,
            event_bus=self.event_bus,
        )
        self.mixing = MixingEngine(
            weight=self.weight, led=self.led,
            buzzer=self.buzzer, event_bus=self.event_bus,
        )
        self.usage = UsageCalculator(event_bus=self.event_bus)

        # ---- Cloud Sync ----
        self.cloud = CloudClient()
        self.sync_engine = SyncEngine(self.db, self.cloud)

        # Load demo recipe only if NOT paired (paired gets data from cloud)
        if not self.cloud.is_paired:
            recipe = MixingRecipe(
                recipe_id='RCP-001',
                name='SIGMACOVER 280 System',
                base_product_id='PROD-001',
                hardener_product_id='PROD-002',
                ratio_base=4.0,
                ratio_hardener=1.0,
                tolerance_pct=5.0,
                pot_life_minutes=480,
            )
            self.mixing.load_recipes({'RCP-001': recipe})

        # Initialize hardware
        if not self.inventory.initialize():
            print("WARNING: Failed to initialize sensors!")

        print(f"  SmartLocker UI initialized in {self.mode.upper()} mode")

    def _poll_sensors(self, dt):
        """Called every 500ms to poll RFID and weight sensors."""
        try:
            self.inventory.poll()
        except Exception as e:
            logging.getLogger('smartlocker').error(f"Poll error: {e}")

    def go_screen(self, screen_name):
        """Navigate to a screen by name."""
        self.sm.current = screen_name

    def go_back(self):
        """Go back to home screen."""
        self.sm.current = 'home'

    def on_stop(self):
        """Clean shutdown when app closes."""
        try:
            self.sync_engine.stop()
            self.inventory.shutdown()
            self.db.close()
        except Exception:
            pass
        print("SmartLocker UI stopped.")
