"""
SmartLocker Kivy Application

Main application class that:
1. Initializes the entire system (drivers, engines, database)
2. Creates the screen manager with all UI screens
3. Runs the sensor polling loop via Kivy Clock
4. Shows pairing screen on first boot if not paired to cloud

Design System 2026 - "Maritime Tech"
=====================================
A modern dark industrial design with gradient accents, rounded cards,
generous touch targets (64dp minimum for gloved hands), and high-contrast
text optimized for a 4.3" touchscreen (800x480) in variable lighting.

Color Palette:
  BG_DARK        = (0.06, 0.07, 0.10, 1)   # Near-black carbon
  BG_CARD        = (0.10, 0.12, 0.16, 1)   # Card surface
  BG_CARD_HOVER  = (0.13, 0.15, 0.20, 1)   # Card pressed/hover
  BG_INPUT       = (0.07, 0.09, 0.13, 1)   # Input field bg

  PRIMARY        = (0.00, 0.82, 0.73, 1)    # Bright teal/cyan
  PRIMARY_DIM    = (0.00, 0.55, 0.49, 1)    # Teal pressed state
  SECONDARY      = (0.33, 0.58, 0.85, 1)   # Ocean blue
  ACCENT         = (0.98, 0.65, 0.25, 1)    # Warm amber

  SUCCESS        = (0.20, 0.82, 0.48, 1)    # Green
  WARNING        = (0.98, 0.76, 0.22, 1)    # Yellow
  DANGER         = (0.93, 0.27, 0.32, 1)    # Red
  INFO           = (0.33, 0.58, 0.85, 1)    # Blue

  TEXT_PRIMARY   = (0.96, 0.97, 0.98, 1)    # Almost white
  TEXT_SECONDARY = (0.60, 0.64, 0.72, 1)    # Muted gray
  TEXT_MUTED     = (0.38, 0.42, 0.50, 1)    # Dim text

  DIVIDER        = (0.18, 0.20, 0.26, 1)   # Subtle line
"""

import os
import sys
import time
import logging

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, FadeTransition
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.core.window import Window

# ============================================================
# DESIGN TOKENS (importable by screens)
# ============================================================
class DS:
    """Design System tokens - centralized styling constants."""

    # --- Background colors ---
    BG_DARK       = (0.06, 0.07, 0.10, 1)
    BG_CARD       = (0.10, 0.12, 0.16, 1)
    BG_CARD_HOVER = (0.13, 0.15, 0.20, 1)
    BG_INPUT      = (0.07, 0.09, 0.13, 1)
    BG_STATUS_BAR = (0.05, 0.06, 0.09, 1)

    # --- Primary palette ---
    PRIMARY       = (0.00, 0.82, 0.73, 1)
    PRIMARY_DIM   = (0.00, 0.55, 0.49, 1)
    PRIMARY_GLOW  = (0.00, 0.82, 0.73, 0.15)
    SECONDARY     = (0.33, 0.58, 0.85, 1)
    SECONDARY_DIM = (0.20, 0.38, 0.60, 1)
    ACCENT        = (0.98, 0.65, 0.25, 1)
    ACCENT_DIM    = (0.70, 0.46, 0.16, 1)

    # --- Semantic colors ---
    SUCCESS       = (0.20, 0.82, 0.48, 1)
    WARNING       = (0.98, 0.76, 0.22, 1)
    DANGER        = (0.93, 0.27, 0.32, 1)
    DANGER_DIM    = (0.60, 0.18, 0.22, 1)
    INFO          = (0.33, 0.58, 0.85, 1)

    # --- Text colors ---
    TEXT_PRIMARY   = (0.96, 0.97, 0.98, 1)
    TEXT_SECONDARY = (0.60, 0.64, 0.72, 1)
    TEXT_MUTED     = (0.38, 0.42, 0.50, 1)

    # --- Dividers / borders ---
    DIVIDER        = (0.18, 0.20, 0.26, 1)
    BORDER_SUBTLE  = (0.14, 0.16, 0.22, 1)

    # --- Slot status colors ---
    SLOT_OCCUPIED  = (0.00, 0.82, 0.73, 1)
    SLOT_EMPTY     = (0.30, 0.33, 0.38, 1)
    SLOT_REMOVED   = (0.98, 0.65, 0.25, 1)
    SLOT_IN_USE    = (0.98, 0.76, 0.22, 1)
    SLOT_ANOMALY   = (0.93, 0.27, 0.32, 1)

    # --- Font sizes (sp) ---
    FONT_HERO   = '40sp'     # Giant numbers (weight display, timers)
    FONT_H1     = '26sp'     # Screen title / big buttons
    FONT_H2     = '20sp'     # Section headers
    FONT_H3     = '17sp'     # Card titles
    FONT_BODY   = '15sp'     # Normal text
    FONT_SMALL  = '13sp'     # Secondary info, labels
    FONT_TINY   = '11sp'     # Status bar, micro-text

    # --- Spacing (dp) ---
    PAD_SCREEN  = 12         # Screen edge padding
    PAD_CARD    = 10         # Inside card padding
    SPACING     = 8          # Default spacing between elements
    RADIUS      = 12         # Card corner radius

    # --- Touch targets (dp) ---
    BTN_HEIGHT_LG  = 64      # Large primary buttons (glove-friendly)
    BTN_HEIGHT_MD  = 54      # Medium buttons
    BTN_HEIGHT_SM  = 42      # Small / secondary buttons
    STATUS_BAR_H   = 44      # Status bar height

    # --- Helpers ---
    @staticmethod
    def rgba_str(color):
        """Convert tuple to KV rgba string."""
        return f'{color[0]}, {color[1]}, {color[2]}, {color[3]}'

    @staticmethod
    def hex_markup(color):
        """Convert rgba tuple to markup hex color string (6 chars)."""
        r = int(color[0] * 255)
        g = int(color[1] * 255)
        b = int(color[2] * 255)
        return f'{r:02x}{g:02x}{b:02x}'


# ============================================================
# GLOBAL KV STYLES
# ============================================================
Builder.load_string('''
#:import utils kivy.utils

# --------------------------------------------------------
# STATUS BAR - slim, dark, always visible at top
# --------------------------------------------------------
<StatusBar@BoxLayout>:
    size_hint_y: None
    height: '44dp'
    padding: [12, 4]
    spacing: 8
    canvas.before:
        Color:
            rgba: 0.05, 0.06, 0.09, 1
        Rectangle:
            pos: self.pos
            size: self.size
        # Bottom accent line (subtle gradient feel)
        Color:
            rgba: 0.00, 0.82, 0.73, 0.25
        Rectangle:
            pos: self.x, self.y
            size: self.width, 1

# --------------------------------------------------------
# BACK BUTTON - consistent across screens
# --------------------------------------------------------
<BackButton@Button>:
    text: '<'
    font_size: '22sp'
    bold: True
    size_hint: (None, None)
    size: ('50dp', '36dp')
    background_normal: ''
    background_color: 0.13, 0.15, 0.20, 1
    color: 0.60, 0.64, 0.72, 1

# --------------------------------------------------------
# PRIMARY BUTTON - teal, high contrast, large
# --------------------------------------------------------
<PrimaryButton@Button>:
    background_normal: ''
    background_color: 0.00, 0.82, 0.73, 1
    color: 0.02, 0.05, 0.08, 1
    font_size: '18sp'
    bold: True
    size_hint_y: None
    height: '64dp'
    markup: True

# --------------------------------------------------------
# SECONDARY BUTTON - blue outline feel
# --------------------------------------------------------
<SecondaryButton@Button>:
    background_normal: ''
    background_color: 0.13, 0.15, 0.20, 1
    color: 0.60, 0.64, 0.72, 1
    font_size: '16sp'
    bold: True
    size_hint_y: None
    height: '54dp'
    markup: True

# --------------------------------------------------------
# DANGER BUTTON - red/coral
# --------------------------------------------------------
<DangerButton@Button>:
    background_normal: ''
    background_color: 0.93, 0.27, 0.32, 1
    color: 1, 1, 1, 1
    font_size: '16sp'
    bold: True
    size_hint_y: None
    height: '54dp'

# --------------------------------------------------------
# ACCENT BUTTON - amber/orange
# --------------------------------------------------------
<AccentButton@Button>:
    background_normal: ''
    background_color: 0.98, 0.65, 0.25, 1
    color: 0.06, 0.07, 0.10, 1
    font_size: '16sp'
    bold: True
    size_hint_y: None
    height: '54dp'

# --------------------------------------------------------
# GHOST BUTTON - transparent with text only
# --------------------------------------------------------
<GhostButton@Button>:
    background_normal: ''
    background_color: 0, 0, 0, 0
    color: 0.60, 0.64, 0.72, 1
    font_size: '15sp'
    size_hint_y: None
    height: '44dp'
    markup: True

# --------------------------------------------------------
# NAV BUTTON - for home screen navigation tiles
# --------------------------------------------------------
<NavButton@Button>:
    background_normal: ''
    background_color: 0.10, 0.12, 0.16, 1
    color: 1, 1, 1, 1
    font_size: '17sp'
    bold: True
    size_hint_y: None
    height: '64dp'
    markup: True

# --------------------------------------------------------
# SIM BUTTON - test/simulation mode (amber tint)
# --------------------------------------------------------
<SimButton@Button>:
    background_normal: ''
    background_color: 0.30, 0.22, 0.08, 1
    color: 0.98, 0.76, 0.22, 1
    font_size: '15sp'
    bold: True
    size_hint_y: None
    height: '54dp'
    markup: True

# --------------------------------------------------------
# SCREEN TITLE
# --------------------------------------------------------
<ScreenTitle@Label>:
    font_size: '20sp'
    bold: True
    color: 0.96, 0.97, 0.98, 1
    size_hint_y: None
    height: '36dp'
    halign: 'center'
    text_size: self.size
    valign: 'middle'
    markup: True

# --------------------------------------------------------
# INFO LABEL - secondary readable text
# --------------------------------------------------------
<InfoLabel@Label>:
    font_size: '15sp'
    color: 0.60, 0.64, 0.72, 1
    halign: 'left'
    text_size: self.size
    valign: 'top'
    markup: True

# --------------------------------------------------------
# CARD LAYOUT - rounded dark card container
# --------------------------------------------------------
<Card@BoxLayout>:
    orientation: 'vertical'
    padding: [10, 10]
    spacing: 6
    canvas.before:
        Color:
            rgba: 0.10, 0.12, 0.16, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [12]

# --------------------------------------------------------
# GREEN BUTTON (compat alias for PrimaryButton)
# --------------------------------------------------------
<GreenButton@PrimaryButton>:
    background_color: 0.00, 0.82, 0.73, 1
''')


class SmartLockerApp(App):
    """Main Kivy application for the SmartLocker touchscreen."""

    title = 'SmartLocker'

    def build(self):
        """Initialize system and create UI."""
        # Dark carbon background
        Window.clearcolor = DS.BG_DARK

        # Initialize system components
        self._init_system()

        # Create screen manager with a smooth fade transition
        self.sm = ScreenManager(transition=FadeTransition(duration=0.15))

        # Import and add screens
        from ui.screens.home import HomeScreen
        from ui.screens.inventory import InventoryScreen
        from ui.screens.mixing import MixingScreen
        from ui.screens.demo import DemoScreen
        from ui.screens.pairing import PairingScreen
        from ui.screens.settings import SettingsScreen
        from ui.screens.paint_now import PaintNowScreen
        from ui.screens.chart_viewer import ChartViewerScreen
        from ui.screens.admin import AdminScreen
        from ui.screens.alarm_screen import AlarmScreen
        from ui.screens.system_health import SystemHealthScreen

        # Add pairing screen FIRST (so it's the default if not paired)
        self.sm.add_widget(PairingScreen(name='pairing'))
        self.sm.add_widget(HomeScreen(name='home'))
        self.sm.add_widget(InventoryScreen(name='inventory'))
        self.sm.add_widget(MixingScreen(name='mixing'))
        self.sm.add_widget(DemoScreen(name='demo'))
        self.sm.add_widget(SettingsScreen(name='settings'))
        self.sm.add_widget(PaintNowScreen(name='paint_now'))
        self.sm.add_widget(ChartViewerScreen(name='chart_viewer'))
        self.sm.add_widget(AdminScreen(name='admin'))
        self.sm.add_widget(AlarmScreen(name='alarm'))
        self.sm.add_widget(SystemHealthScreen(name='system_health'))

        # ---- Alarm callbacks (v1.0.6) ----
        self._previous_screen = 'home'

        def _on_critical_alarm(alarm):
            def _show(dt):
                if self.sm.current != 'alarm':
                    self._previous_screen = self.sm.current
                    self.sm.current = 'alarm'
            Clock.schedule_once(_show, 0)

        self.alarm_manager.on_critical_alarm = _on_critical_alarm

        # Decide initial screen based on pairing status
        if self.cloud.is_paired:
            # Already paired -> go straight to home
            self.sm.current = 'home'

            # Start background sync
            self.sync_engine.start()
            print("  Cloud: PAIRED -- sync started")

            # Start system monitor (paired mode)
            self.system_monitor.start(interval_s=60)
        else:
            # Not paired -> show pairing screen
            self.sm.current = 'pairing'
            print("  Cloud: NOT PAIRED -- showing pairing screen")

            # Start system monitor in test mode too
            if self.mode == 'test':
                self.system_monitor.start(interval_s=60)

        # Start backup manager
        self.backup_manager.start()

        # Start sensor polling loop (every 500ms)
        Clock.schedule_interval(self._poll_sensors, 0.5)

        return self.sm

    def _init_system(self):
        """Initialize all system components (same as main.py)."""
        from config.settings import (
            MODE, DEVICE_ID,
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

        self.device_id = DEVICE_ID
        self.logger = setup_logging()

        # Resolve per-sensor driver selections
        # Legacy MODE support: "test" forces all fake, "live" forces all real
        # "auto" (default) uses individual DRIVER_* settings
        if MODE == "test":
            drv_rfid = drv_weight = drv_led = drv_buzzer = "fake"
        elif MODE == "live":
            drv_rfid = drv_weight = drv_led = drv_buzzer = "real"
        else:
            drv_rfid = DRIVER_RFID
            drv_weight = DRIVER_WEIGHT
            drv_led = DRIVER_LED
            drv_buzzer = DRIVER_BUZZER

        # ---- Apply admin overrides from DB (if any) ----
        # This must happen after DB connect but we need a temp DB here.
        # We do a lightweight check using a temporary Database instance
        # to read admin config before the main DB is created below.
        try:
            _tmp_db = Database()
            _tmp_db.connect()
            admin_config = _tmp_db.get_admin_config()
            _tmp_db.close()
            if admin_config and MODE == "auto":
                if 'driver_rfid' in admin_config:
                    drv_rfid = admin_config['driver_rfid']
                if 'driver_weight' in admin_config:
                    drv_weight = admin_config['driver_weight']
                if 'driver_led' in admin_config:
                    drv_led = admin_config['driver_led']
                if 'driver_buzzer' in admin_config:
                    drv_buzzer = admin_config['driver_buzzer']
                print("  Admin overrides applied from DB")
        except Exception:
            admin_config = {}
            pass

        # Determine overall system mode
        drivers = [drv_rfid, drv_weight, drv_led, drv_buzzer]
        any_real = any(d == "real" for d in drivers)
        all_real = all(d == "real" for d in drivers)
        if all_real:
            self.mode = "live"
        elif any_real:
            self.mode = "hybrid"
        else:
            self.mode = "test"

        # Store per-driver status for UI display
        self.driver_status = {
            'rfid': drv_rfid,
            'weight': drv_weight,
            'led': drv_led,
            'buzzer': drv_buzzer,
        }

        # Create event bus
        self.event_bus = EventBus()

        # Create database
        self.db = Database()
        self.db.connect()

        # Create backup manager (daemon thread, started in build())
        from core.backup_manager import BackupManager
        self.backup_manager = BackupManager(db_path=self.db.db_path)

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

        # ---- RFID Driver ----
        if drv_rfid == "real":
            from hal.real.real_rfid import RealRFIDDriver
            self.rfid = RealRFIDDriver()
        else:
            from hal.fake.fake_rfid import FakeRFIDDriver
            self.rfid = FakeRFIDDriver()

        # ---- Weight Driver ----
        if drv_weight == "real":
            from hal.real.real_weight import RealWeightDriver
            self.weight = RealWeightDriver()
        else:
            from hal.fake.fake_weight import FakeWeightDriver
            self.weight = FakeWeightDriver(channels=['shelf1', 'mixing_scale'])

        # ---- LED Driver ----
        if drv_led == "real":
            from hal.real.real_led import RealLEDDriver
            self.led = RealLEDDriver()
        else:
            from hal.fake.fake_led import FakeLEDDriver
            self.led = FakeLEDDriver()

        # ---- Buzzer Driver ----
        if drv_buzzer == "real":
            from hal.real.real_buzzer import RealBuzzerDriver
            self.buzzer = RealBuzzerDriver()
        else:
            from hal.fake.fake_buzzer import FakeBuzzerDriver
            self.buzzer = FakeBuzzerDriver()

        # Create engines
        self.inventory = InventoryEngine(
            rfid=self.rfid, weight=self.weight,
            led=self.led, buzzer=self.buzzer,
            event_bus=self.event_bus,
        )
        self.inventory.set_database(self.db)

        self.mixing = MixingEngine(
            weight=self.weight, led=self.led,
            buzzer=self.buzzer, event_bus=self.event_bus,
        )
        self.mixing.set_inventory(self.inventory)
        self.mixing.set_database(self.db)

        self.usage = UsageCalculator(event_bus=self.event_bus)

        # ---- Alarm System (v1.0.6) ----
        from core.alarm_manager import AlarmManager
        from core.system_monitor import SystemMonitor

        self.alarm_manager = AlarmManager(self.event_bus, self.db)
        self.system_monitor = SystemMonitor(self.alarm_manager)

        # ---- Cloud Sync ----
        self.cloud = CloudClient()
        self.sync_engine = SyncEngine(self.db, self.cloud)

        # Set monitoring references so heartbeats include sensor health + telemetry
        self.cloud.set_monitoring_refs(
            driver_status=self.driver_status,
            sensors={
                'rfid': self.rfid,
                'weight': self.weight,
            },
            db_ref=self.db,
            system_monitor=self.system_monitor,
        )

        # Paint Now context (for passing data between screens)
        self.paint_now_context = None
        # Maintenance chart (loaded from DB or demo)
        self.maintenance_chart = None

        # Setup demo data in TEST mode, or load from DB
        if self.mode == 'test' and not self.cloud.is_paired:
            self._setup_demo_data()
        else:
            self._reload_catalog_from_db()

        # Initialize hardware
        if not self.inventory.initialize():
            print("WARNING: Failed to initialize sensors!")

        # Log mode and driver status
        mode_str = self.mode.upper()
        if self.mode == 'hybrid':
            real_drivers = [k for k, v in self.driver_status.items() if v == 'real']
            fake_drivers = [k for k, v in self.driver_status.items() if v == 'fake']
            print(f"  SmartLocker UI initialized in {mode_str} mode")
            print(f"    Real: {', '.join(real_drivers)}")
            print(f"    Fake: {', '.join(fake_drivers)}")
        else:
            print(f"  SmartLocker UI initialized in {mode_str} mode")

    def _setup_demo_data(self):
        """Create demo products, RFID tag mapping, recipe, and chart for TEST mode."""
        from core.models import MixingRecipe

        # --- Demo Products ---
        demo_products = [
            {
                'product_id': 'PROD-001',
                'ppg_code': 'SC-280',
                'name': 'SIGMACOVER 280',
                'product_type': 'base_paint',
                'density_g_per_ml': 1.30,
                'pot_life_minutes': 480,
                'hazard_class': 'GHS02',
                'can_sizes_ml': [5000, 20000],
                'can_tare_weight_g': {'5000': 400, '20000': 1200},
            },
            {
                'product_id': 'PROD-002',
                'ppg_code': 'SC-280H',
                'name': 'SIGMACOVER 280 Hardener',
                'product_type': 'hardener',
                'density_g_per_ml': 1.10,
                'pot_life_minutes': None,
                'hazard_class': 'GHS07',
                'can_sizes_ml': [1000, 5000],
                'can_tare_weight_g': {'1000': 150, '5000': 400},
            },
            {
                'product_id': 'PROD-003',
                'ppg_code': 'T-21',
                'name': 'THINNER 21-06',
                'product_type': 'thinner',
                'density_g_per_ml': 0.87,
                'pot_life_minutes': None,
                'hazard_class': 'GHS02',
                'can_sizes_ml': [5000, 20000],
                'can_tare_weight_g': {'5000': 400},
            },
            {
                'product_id': 'PROD-004',
                'ppg_code': 'SP-200',
                'name': 'SIGMAPRIME 200',
                'product_type': 'primer',
                'density_g_per_ml': 1.40,
                'pot_life_minutes': 360,
                'hazard_class': 'GHS02',
                'can_sizes_ml': [5000, 20000],
                'can_tare_weight_g': {'5000': 400},
            },
        ]
        for p in demo_products:
            self.db.upsert_product(p)

        # --- RFID Tag -> Product Mapping ---
        self.db.upsert_rfid_tag('TAG-BASE-001', 'PROD-001', can_size_ml=20000)
        self.db.upsert_rfid_tag('TAG-HARD-001', 'PROD-002', can_size_ml=5000)
        self.db.upsert_rfid_tag('TAG-THIN-001', 'PROD-003', can_size_ml=5000)
        self.db.upsert_rfid_tag('TAG-PRIM-001', 'PROD-004', can_size_ml=20000)

        # --- Demo Recipe ---
        self.db.upsert_recipe({
            'recipe_id': 'RCP-001',
            'name': 'SIGMACOVER 280 System',
            'base_product_id': 'PROD-001',
            'hardener_product_id': 'PROD-002',
            'ratio_base': 4.0,
            'ratio_hardener': 1.0,
            'tolerance_pct': 5.0,
            'thinner_pct_brush': 5.0,
            'thinner_pct_roller': 5.0,
            'thinner_pct_spray': 10.0,
            'recommended_thinner_id': 'PROD-003',
            'pot_life_minutes': 480,
        })

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

        # --- Demo Maintenance Chart ---
        demo_chart = {
            'vessel_name': 'MED TOSCANA (DEMO)',
            'imo_number': '9999999',
            'products': [
                {
                    'name': 'SIGMACOVER 280',
                    'thinner': 'THINNER 21-06',
                    'components': 2,
                    'base_ratio': 4,
                    'hardener_ratio': 1,
                    'coverage_m2_per_liter': 6.0,
                },
                {
                    'name': 'SIGMAPRIME 200',
                    'thinner': 'THINNER 21-06',
                    'components': 2,
                    'base_ratio': 3,
                    'hardener_ratio': 1,
                    'coverage_m2_per_liter': 5.0,
                },
            ],
            'areas': [
                {
                    'name': 'TOPSIDE / SUPERSTRUCTURE',
                    'notes': 'Above waterline',
                    'layers': [
                        {'layer_number': 1, 'product': 'SIGMAPRIME 200', 'color': 'GREY'},
                        {'layer_number': 2, 'product': 'SIGMACOVER 280', 'color': 'GREY'},
                        {'layer_number': 3, 'product': 'SIGMACOVER 280', 'color': 'WHITE'},
                    ],
                },
                {
                    'name': 'CARGO HOLDS',
                    'notes': 'Interior cargo areas',
                    'layers': [
                        {'layer_number': 1, 'product': 'SIGMAPRIME 200', 'color': 'RED'},
                        {'layer_number': 2, 'product': 'SIGMACOVER 280', 'color': 'RED'},
                    ],
                },
                {
                    'name': 'BALLAST TANKS',
                    'notes': 'Water ballast tanks',
                    'layers': [
                        {'layer_number': 1, 'product': 'SIGMAPRIME 200', 'color': 'GREY'},
                        {'layer_number': 2, 'product': 'SIGMACOVER 280', 'color': 'GREY'},
                        {'layer_number': 3, 'product': 'SIGMACOVER 280', 'color': 'GREY'},
                    ],
                },
            ],
            'marking_colors': [
                {'purpose': 'Draft Marks', 'color': 'WHITE'},
                {'purpose': 'Plimsoll Mark', 'color': 'RED'},
            ],
        }
        self.db.save_maintenance_chart(demo_chart)
        self.maintenance_chart = demo_chart
        print("  TEST mode: demo products, tags, recipe, and chart loaded")

    def _reload_catalog_from_db(self):
        """Reload products, recipes, and chart from local database into memory."""
        from core.models import MixingRecipe

        # Load maintenance chart
        self.maintenance_chart = self.db.get_maintenance_chart()

        # Load recipes from DB into MixingEngine
        recipes_data = self.db.get_recipes()
        recipes = {}
        for r in recipes_data:
            recipe = MixingRecipe(
                recipe_id=r['recipe_id'],
                name=r['name'],
                base_product_id=r['base_product_id'],
                hardener_product_id=r['hardener_product_id'],
                ratio_base=r['ratio_base'],
                ratio_hardener=r['ratio_hardener'],
                tolerance_pct=r.get('tolerance_pct', 5.0),
                pot_life_minutes=r.get('pot_life_minutes', 480),
            )
            recipes[r['recipe_id']] = recipe

        if recipes:
            self.mixing.load_recipes(recipes)
            print(f"  Loaded {len(recipes)} recipes from DB")

        if self.maintenance_chart:
            print(f"  Maintenance chart loaded: {self.maintenance_chart.get('vessel_name', '?')}")

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

    def dismiss_alarm(self):
        """Called when user acknowledges all critical alarms. Returns to previous screen."""
        self.sm.current = self._previous_screen if self._previous_screen != 'alarm' else 'home'

    def on_stop(self):
        """Clean shutdown when app closes."""
        try:
            self.backup_manager.stop()
            self.system_monitor.stop()
            self.sync_engine.stop()
            self.inventory.shutdown()
            self.db.close()
        except Exception:
            pass
        print("SmartLocker UI stopped.")
