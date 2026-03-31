"""
SmartLocker PySide6 Application

Main window with stacked widget navigation (replaces Kivy ScreenManager).
Initializes all hardware drivers, engines, and screens.
"""

import sys
import os
import time
import logging

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)
from PyQt6.QtCore import Qt, QTimer, QEvent, QObject
from PyQt6.QtGui import QFont

from ui_qt.theme import STYLESHEET, C, F, S

logger = logging.getLogger("smartlocker.qt_app")


class ClickSoundFilter(QObject):
    """Global event filter: plays buzzer TICK on every button press."""

    def __init__(self, app_window):
        super().__init__()
        self._app = app_window

    def eventFilter(self, obj, event):
        if (event.type() == QEvent.Type.MouseButtonPress
                and isinstance(obj, QPushButton)):
            try:
                from hal.interfaces import BuzzerPattern
                self._app.buzzer.play(BuzzerPattern.TICK)
            except Exception:
                pass
        return False  # Don't consume the event


class SmartLockerWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SmartLocker")
        self.setMinimumSize(800, 480)

        # Initialize system (drivers, engines, DB)
        self._init_system()

        # Navigation stack
        self._nav_stack = []

        # Central stacked widget
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # Import and create screens
        from ui_qt.screens.home import HomeScreen
        from ui_qt.screens.sensor_test import SensorTestScreen
        from ui_qt.screens.settings import SettingsScreen

        self._screens = {}
        self._add_screen("home", HomeScreen(self))
        self._add_screen("sensor_test", SensorTestScreen(self))
        self._add_screen("settings", SettingsScreen(self))

        # Lazy screens (created on first navigation)
        self._lazy_screens = {
            "pairing": "ui_qt.screens.pairing:PairingScreen",
            "inventory": "ui_qt.screens.inventory:InventoryScreen",
            "mixing": "ui_qt.screens.mixing:MixingScreen",
            "paint_now": "ui_qt.screens.paint_now:PaintNowScreen",
            "chart_viewer": "ui_qt.screens.chart_viewer:ChartViewerScreen",
            "admin": "ui_qt.screens.admin:AdminScreen",
            "system_health": "ui_qt.screens.system_health:SystemHealthScreen",
            "shelf_map": "ui_qt.screens.shelf_map:ShelfMapScreen",
            "alarm": "ui_qt.screens.alarm:AlarmScreen",
            "demo": "ui_qt.screens.demo:DemoScreen",
            "tag_writer": "ui_qt.screens.tag_writer:TagWriterScreen",
        }

        # Start on home (or pairing if not paired)
        if self.cloud.is_paired:
            self.go_screen("home")
            self.sync_engine.start()
            logger.info("Cloud: PAIRED — sync started")
        else:
            self.go_screen("home")  # Home for now, can switch to pairing
            logger.info("Cloud: NOT PAIRED")

        # Sensor polling timer
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll_sensors)
        self._poll_timer.start(500)

        # Global click sound: buzzer TICK on every button press
        self._click_filter = ClickSoundFilter(self)
        QApplication.instance().installEventFilter(self._click_filter)

    def _add_screen(self, name, widget):
        self._screens[name] = widget
        self.stack.addWidget(widget)

    def go_screen(self, name):
        """Navigate to a screen by name."""
        if name not in self._screens:
            # Try lazy loading
            if name in self._lazy_screens:
                self._lazy_load_screen(name)
            else:
                logger.warning(f"Screen not found: {name}")
                return

        self._nav_stack.append(name)
        screen = self._screens[name]
        self.stack.setCurrentWidget(screen)
        if hasattr(screen, "on_enter"):
            screen.on_enter()

    def go_back(self):
        """Navigate to previous screen."""
        if len(self._nav_stack) > 1:
            current = self._nav_stack.pop()
            if hasattr(self._screens.get(current), "on_leave"):
                self._screens[current].on_leave()
            target = self._nav_stack[-1]
            self.stack.setCurrentWidget(self._screens[target])
            if hasattr(self._screens[target], "on_enter"):
                self._screens[target].on_enter()
        else:
            self.go_screen("home")

    def _lazy_load_screen(self, name):
        """Load a screen module on demand."""
        spec = self._lazy_screens.get(name)
        if not spec:
            return
        module_path, class_name = spec.split(":")
        try:
            import importlib
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            self._add_screen(name, cls(self))
            del self._lazy_screens[name]
        except Exception as e:
            logger.error(f"Failed to load screen {name}: {e}")

    # ══════════════════════════════════════════════════════
    # SYSTEM INIT
    # ══════════════════════════════════════════════════════

    def _init_system(self):
        """Initialize drivers, engines, database — same logic as Kivy app."""
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
        from core.alarm_manager import AlarmManager
        from core.system_monitor import SystemMonitor
        from core.backup_manager import BackupManager
        from persistence.database import Database
        from sync.cloud_client import CloudClient
        from sync.sync_engine import SyncEngine

        setup_logging()

        self.device_id = DEVICE_ID
        self.event_log = []

        # Resolve driver modes (check DB overrides)
        cfg_mode = MODE
        drv_rfid = DRIVER_RFID
        drv_weight = DRIVER_WEIGHT
        drv_led = DRIVER_LED
        drv_buzzer = DRIVER_BUZZER

        # Database
        self.db = Database()
        self.db.connect()

        # Check admin DB overrides
        admin_cfg = self.db.get_admin_config()
        if admin_cfg:
            drv_rfid = admin_cfg.get("driver_rfid", drv_rfid)
            drv_weight = admin_cfg.get("driver_weight", drv_weight)
            drv_led = admin_cfg.get("driver_led", drv_led)
            drv_buzzer = admin_cfg.get("driver_buzzer", drv_buzzer)
            print("  Admin overrides applied from DB")

        self.driver_status = {
            "rfid": drv_rfid, "weight": drv_weight,
            "led": drv_led, "buzzer": drv_buzzer,
        }

        # Determine mode
        drivers = [drv_rfid, drv_weight, drv_led, drv_buzzer]
        if all(d == "real" for d in drivers):
            self.mode = "live"
        elif any(d == "real" for d in drivers):
            self.mode = "hybrid"
        else:
            self.mode = "test"

        # ── RFID ──
        if drv_rfid == "real":
            from config.settings import RFID_MODULE
            if RFID_MODULE == "pn532_usb":
                from hal.real.real_rfid_pn532_usb import RealRFIDDriverPN532USB
                self.rfid = RealRFIDDriverPN532USB()
            elif RFID_MODULE == "rc522":
                from hal.real.real_rfid_rc522 import RealRFIDDriverRC522
                self.rfid = RealRFIDDriverRC522()
            else:
                from hal.real.real_rfid import RealRFIDDriver
                self.rfid = RealRFIDDriver()
        else:
            from hal.fake.fake_rfid import FakeRFIDDriver
            self.rfid = FakeRFIDDriver()

        # ── Weight ──
        if drv_weight == "real":
            from config.settings import WEIGHT_MODE
            if WEIGHT_MODE == "hx711_direct":
                from hal.real.real_weight_hx711 import RealWeightDriverHX711
                self.weight = RealWeightDriverHX711()
            else:
                from hal.real.real_weight import RealWeightDriver
                self.weight = RealWeightDriver()
        else:
            from hal.fake.fake_weight import FakeWeightDriver
            self.weight = FakeWeightDriver(channels=["shelf1", "mixing_scale"])

        # ── LED ──
        if drv_led == "real":
            from hal.real.real_led import RealLEDDriver
            self.led = RealLEDDriver()
        else:
            from hal.fake.fake_led import FakeLEDDriver
            self.led = FakeLEDDriver()

        # ── Buzzer ──
        if drv_buzzer == "real":
            from hal.real.real_buzzer import RealBuzzerDriver
            self.buzzer = RealBuzzerDriver()
        else:
            from hal.fake.fake_buzzer import FakeBuzzerDriver
            self.buzzer = FakeBuzzerDriver()

        # Event bus
        self.event_bus = EventBus()

        def log_event(event):
            self.event_log.append(event)
            self.db.save_event(event)
            self.db.enqueue_for_sync(event)
        self.event_bus.subscribe_all(log_event)

        # Engines
        self.inventory_engine = InventoryEngine(
            rfid=self.rfid, weight=self.weight,
            led=self.led, buzzer=self.buzzer,
            event_bus=self.event_bus,
        )
        self.inventory_engine.set_database(self.db)

        self.mixing_engine = MixingEngine(
            weight=self.weight, led=self.led,
            buzzer=self.buzzer, event_bus=self.event_bus,
        )

        self.usage_calculator = UsageCalculator(event_bus=self.event_bus)
        self.alarm_manager = AlarmManager(event_bus=self.event_bus, db=self.db)
        self.system_monitor = SystemMonitor(alarm_manager=self.alarm_manager)
        self.backup_manager = BackupManager(self.db)

        # Initialize sensors
        init_ok = self.inventory_engine.initialize()
        if not init_ok:
            print("WARNING: Failed to initialize sensors!")

        # Cloud & Sync
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

        # Start system monitor background checks
        self.system_monitor.start(interval_s=60)

        # Load maintenance chart
        self.maintenance_chart = self.db.get_maintenance_chart()
        if self.maintenance_chart:
            chart_name = self.maintenance_chart.get("name", "Unknown")
            print(f"  Maintenance chart loaded: {chart_name}")

        # Slot count
        self.slot_count = self.db.get_config("slot_count") or 4
        try:
            self.slot_count = int(self.slot_count)
        except (ValueError, TypeError):
            self.slot_count = 4

        # Print status
        real = [k for k, v in self.driver_status.items() if v == "real"]
        fake = [k for k, v in self.driver_status.items() if v == "fake"]
        print(f"  SmartLocker Qt initialized in {self.mode.upper()} mode")
        if real:
            print(f"    Real: {', '.join(real)}")
        if fake:
            print(f"    Fake: {', '.join(fake)}")

    def _poll_sensors(self):
        """Periodic sensor polling (every 500ms)."""
        try:
            self.inventory_engine.poll()
        except Exception as e:
            logger.debug(f"Poll error: {e}")

    def closeEvent(self, event):
        """Clean shutdown."""
        self._poll_timer.stop()
        try:
            self.system_monitor.stop()
        except Exception:
            pass
        try:
            self.sync_engine.stop()
        except Exception:
            pass
        try:
            self.inventory_engine.shutdown()
        except Exception:
            pass
        try:
            self.db.close()
        except Exception:
            pass
        print("SmartLocker stopped.")
        event.accept()


def run_qt_app():
    """Entry point for PySide6 UI."""
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)

    window = SmartLockerWindow()
    window.showFullScreen()  # Full screen on RPi touch display

    sys.exit(app.exec())
