"""
SmartLocker Settings Screen — PySide6

Scrollable card-based layout showing device info, cloud connection,
and system navigation buttons.
"""

import time
import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QGridLayout, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer

from ui_qt.theme import C, F, S, enable_touch_scroll

logger = logging.getLogger("smartlocker.settings")


class SettingsScreen(QWidget):
    """Settings screen with device info, cloud status, and system actions."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh_info)

        # ── Label references (populated during build) ──
        self._lbl_device_id = None
        self._lbl_mode = None
        self._lbl_version = None
        self._drv_dots = {}          # driver_name -> (dot_label, text_label)
        self._lbl_cloud_dot = None
        self._lbl_cloud_status = None
        self._lbl_vessel = None
        self._lbl_last_sync = None
        self._lbl_events = None
        self._btn_sync = None
        self._btn_unpair = None

        self._build_ui()

    # ══════════════════════════════════════════════════════
    # UI BUILD
    # ══════════════════════════════════════════════════════

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top bar ──
        top_bar = QFrame()
        top_bar.setObjectName("status_bar")
        top_bar_lay = QHBoxLayout(top_bar)
        top_bar_lay.setContentsMargins(S.PAD, 0, S.PAD, 0)

        btn_back = QPushButton("<  BACK")
        btn_back.setObjectName("ghost")
        btn_back.setFixedWidth(100)
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back.clicked.connect(self.app.go_back)
        top_bar_lay.addWidget(btn_back)

        lbl_title = QLabel("SETTINGS")
        lbl_title.setObjectName("title")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_bar_lay.addWidget(lbl_title, 1)

        # Spacer to balance the back button
        spacer = QLabel()
        spacer.setFixedWidth(100)
        top_bar_lay.addWidget(spacer)

        root.addWidget(top_bar)

        # ── Scroll area ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_lay = QVBoxLayout(scroll_content)
        scroll_lay.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
        scroll_lay.setSpacing(S.PAD)

        # ── DEVICE INFO card ──
        scroll_lay.addWidget(self._build_device_card())

        # ── CLOUD CONNECTION card ──
        scroll_lay.addWidget(self._build_cloud_card())

        # ── SYSTEM card ──
        scroll_lay.addWidget(self._build_system_card())

        scroll_lay.addStretch()
        scroll.setWidget(scroll_content)
        enable_touch_scroll(scroll)
        root.addWidget(scroll, 1)

    # ──────────────────────────────────────────────────────
    # DEVICE INFO card
    # ──────────────────────────────────────────────────────

    def _build_device_card(self) -> QFrame:
        card = self._make_card()
        lay = QVBoxLayout(card)
        lay.setSpacing(S.GAP)

        section = QLabel("DEVICE INFO")
        section.setObjectName("section")
        lay.addWidget(section)

        # Info grid
        grid = QGridLayout()
        grid.setHorizontalSpacing(S.PAD)
        grid.setVerticalSpacing(6)

        # Row 0: Device ID
        grid.addWidget(self._muted_label("Device ID"), 0, 0)
        self._lbl_device_id = QLabel("---")
        self._lbl_device_id.setStyleSheet(f"color: {C.TEXT}; font-weight: bold;")
        grid.addWidget(self._lbl_device_id, 0, 1)

        # Row 1: Mode
        grid.addWidget(self._muted_label("Mode"), 1, 0)
        self._lbl_mode = QLabel("---")
        self._lbl_mode.setStyleSheet(f"color: {C.PRIMARY}; font-weight: bold;")
        grid.addWidget(self._lbl_mode, 1, 1)

        # Row 2: Version
        grid.addWidget(self._muted_label("Version"), 2, 0)
        self._lbl_version = QLabel("---")
        self._lbl_version.setStyleSheet(f"color: {C.TEXT};")
        grid.addWidget(self._lbl_version, 2, 1)

        lay.addLayout(grid)

        # Drivers row
        drv_section = QLabel("Drivers")
        drv_section.setStyleSheet(
            f"color: {C.TEXT_SEC}; font-size: {F.SMALL}px; padding-top: 6px;"
        )
        lay.addWidget(drv_section)

        drv_row = QHBoxLayout()
        drv_row.setSpacing(S.PAD)
        for name in ("rfid", "weight", "led", "buzzer"):
            dot, text, container = self._driver_chip(name)
            self._drv_dots[name] = (dot, text)
            drv_row.addWidget(container)
        drv_row.addStretch()
        lay.addLayout(drv_row)

        return card

    # ──────────────────────────────────────────────────────
    # CLOUD CONNECTION card
    # ──────────────────────────────────────────────────────

    def _build_cloud_card(self) -> QFrame:
        card = self._make_card()
        lay = QVBoxLayout(card)
        lay.setSpacing(S.GAP)

        section = QLabel("CLOUD CONNECTION")
        section.setObjectName("section")
        lay.addWidget(section)

        # Status row
        status_row = QHBoxLayout()
        self._lbl_cloud_dot = QLabel("\u25cf")
        self._lbl_cloud_dot.setFixedWidth(20)
        self._lbl_cloud_dot.setStyleSheet(f"color: {C.TEXT_MUTED}; font-size: 18px;")
        status_row.addWidget(self._lbl_cloud_dot)

        self._lbl_cloud_status = QLabel("---")
        self._lbl_cloud_status.setStyleSheet(
            f"color: {C.TEXT}; font-weight: bold; font-size: {F.BODY}px;"
        )
        status_row.addWidget(self._lbl_cloud_status)
        status_row.addStretch()
        lay.addLayout(status_row)

        # Info grid
        grid = QGridLayout()
        grid.setHorizontalSpacing(S.PAD)
        grid.setVerticalSpacing(6)

        grid.addWidget(self._muted_label("Vessel"), 0, 0)
        self._lbl_vessel = QLabel("---")
        self._lbl_vessel.setStyleSheet(f"color: {C.TEXT};")
        grid.addWidget(self._lbl_vessel, 0, 1)

        grid.addWidget(self._muted_label("Last Sync"), 1, 0)
        self._lbl_last_sync = QLabel("---")
        self._lbl_last_sync.setStyleSheet(f"color: {C.TEXT};")
        grid.addWidget(self._lbl_last_sync, 1, 1)

        grid.addWidget(self._muted_label("Events"), 2, 0)
        self._lbl_events = QLabel("---")
        self._lbl_events.setStyleSheet(f"color: {C.TEXT};")
        grid.addWidget(self._lbl_events, 2, 1)

        lay.addLayout(grid)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(S.GAP)

        self._btn_sync = QPushButton("SYNC NOW")
        self._btn_sync.setObjectName("secondary")
        self._btn_sync.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_sync.clicked.connect(self._on_sync_now)
        btn_row.addWidget(self._btn_sync)

        self._btn_unpair = QPushButton("UNPAIR")
        self._btn_unpair.setObjectName("danger")
        self._btn_unpair.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_unpair.clicked.connect(self._on_unpair)
        btn_row.addWidget(self._btn_unpair)

        btn_row.addStretch()
        lay.addLayout(btn_row)

        return card

    # ──────────────────────────────────────────────────────
    # SYSTEM card
    # ──────────────────────────────────────────────────────

    def _build_system_card(self) -> QFrame:
        card = self._make_card()
        lay = QVBoxLayout(card)
        lay.setSpacing(S.GAP)

        section = QLabel("SYSTEM")
        section.setObjectName("section")
        lay.addWidget(section)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(S.GAP)

        btn_sensor = QPushButton("SENSOR TESTING")
        btn_sensor.setObjectName("accent")
        btn_sensor.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_sensor.setMinimumHeight(40)
        btn_sensor.clicked.connect(lambda: self.app.go_screen("sensor_test"))
        btn_row.addWidget(btn_sensor)

        btn_health = QPushButton("SYSTEM HEALTH")
        btn_health.setObjectName("accent")
        btn_health.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_health.setMinimumHeight(40)
        btn_health.clicked.connect(lambda: self.app.go_screen("system_health"))
        btn_row.addWidget(btn_health)

        btn_admin = QPushButton("ADMIN")
        btn_admin.setObjectName("accent")
        btn_admin.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_admin.setMinimumHeight(40)
        btn_admin.clicked.connect(lambda: self.app.go_screen("admin"))
        btn_row.addWidget(btn_admin)

        lay.addLayout(btn_row)

        btn_row2 = QHBoxLayout()
        btn_row2.setSpacing(S.GAP)

        btn_tag = QPushButton("TAG WRITER")
        btn_tag.setObjectName("secondary")
        btn_tag.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_tag.setMinimumHeight(40)
        btn_tag.clicked.connect(lambda: self.app.go_screen("tag_writer"))
        btn_row2.addWidget(btn_tag)
        btn_row2.addStretch()

        lay.addLayout(btn_row2)

        return card

    # ══════════════════════════════════════════════════════
    # LIFECYCLE
    # ══════════════════════════════════════════════════════

    def on_enter(self):
        """Called when screen becomes visible."""
        self._refresh_info()
        self._timer.start(5000)

    def on_leave(self):
        """Called when navigating away."""
        self._timer.stop()

    # ══════════════════════════════════════════════════════
    # DATA REFRESH
    # ══════════════════════════════════════════════════════

    def _refresh_info(self):
        """Update all labels with current system state."""
        # ── Device info ──
        self._lbl_device_id.setText(self.app.device_id or "N/A")
        self._lbl_mode.setText(self.app.mode.upper() if self.app.mode else "---")

        # Version
        try:
            from sync.update_manager import read_version
            version = read_version()
        except Exception:
            version = "?.?.?"
        self._lbl_version.setText(f"v{version}")

        # Driver dots
        driver_status = getattr(self.app, "driver_status", {})
        for name, (dot_lbl, text_lbl) in self._drv_dots.items():
            status = driver_status.get(name, "fake")
            is_real = status == "real"
            color = C.SUCCESS if is_real else C.TEXT_MUTED
            dot_lbl.setStyleSheet(f"color: {color}; font-size: 14px;")
            text_lbl.setStyleSheet(f"color: {color}; font-size: {F.SMALL}px;")

        # ── Cloud info ──
        is_paired = getattr(self.app.cloud, "is_paired", False)

        if is_paired:
            self._lbl_cloud_dot.setStyleSheet(f"color: {C.SUCCESS}; font-size: 18px;")
            self._lbl_cloud_status.setText("CONNECTED")
            self._lbl_cloud_status.setStyleSheet(
                f"color: {C.SUCCESS}; font-weight: bold; font-size: {F.BODY}px;"
            )
        else:
            self._lbl_cloud_dot.setStyleSheet(f"color: {C.DANGER}; font-size: 18px;")
            self._lbl_cloud_status.setText("NOT PAIRED")
            self._lbl_cloud_status.setStyleSheet(
                f"color: {C.DANGER}; font-weight: bold; font-size: {F.BODY}px;"
            )

        # Sync engine status
        sync_info = {}
        sync_engine = getattr(self.app, "sync_engine", None)
        if sync_engine:
            try:
                sync_info = sync_engine.get_status()
            except Exception:
                pass

        vessel = sync_info.get("vessel_name", "")
        self._lbl_vessel.setText(vessel if vessel else "Not assigned")

        last_sync_ts = sync_info.get("last_sync", 0)
        if last_sync_ts and last_sync_ts > 0:
            self._lbl_last_sync.setText(self._time_ago(last_sync_ts))
        else:
            self._lbl_last_sync.setText("Never")

        total = sync_info.get("events_total", 0)
        unsynced = sync_info.get("events_unsynced", 0)
        self._lbl_events.setText(f"{total} total, {unsynced} pending")

        # Button states
        self._btn_sync.setEnabled(is_paired)
        self._btn_unpair.setEnabled(is_paired)

    # ══════════════════════════════════════════════════════
    # ACTIONS
    # ══════════════════════════════════════════════════════

    def _on_sync_now(self):
        """Trigger an immediate sync cycle."""
        sync_engine = getattr(self.app, "sync_engine", None)
        if sync_engine:
            try:
                sync_engine.force_sync()
                logger.info("Manual sync triggered from settings")
            except Exception as e:
                logger.error(f"Force sync failed: {e}")
        # Refresh after a short delay to show updated status
        QTimer.singleShot(2000, self._refresh_info)

    def _on_unpair(self):
        """Unpair device from cloud."""
        cloud = getattr(self.app, "cloud", None)
        if cloud:
            try:
                cloud.unpair()
                logger.info("Device unpaired from settings")
            except Exception as e:
                logger.error(f"Unpair failed: {e}")
        sync_engine = getattr(self.app, "sync_engine", None)
        if sync_engine:
            try:
                sync_engine.stop()
            except Exception:
                pass
        self._refresh_info()

    # ══════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════

    @staticmethod
    def _make_card() -> QFrame:
        """Create a styled card frame."""
        card = QFrame()
        card.setObjectName("card")
        card.setProperty("card", True)
        return card

    @staticmethod
    def _muted_label(text: str) -> QLabel:
        """Create a muted-color label for field names."""
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {C.TEXT_MUTED}; font-size: {F.SMALL}px;")
        lbl.setFixedWidth(90)
        return lbl

    @staticmethod
    def _driver_chip(name: str):
        """
        Build a small driver status chip: [dot] [NAME].
        Returns (dot_label, text_label, container_widget).
        """
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        h = QHBoxLayout(container)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)

        dot = QLabel("\u25cf")
        dot.setStyleSheet(f"color: {C.TEXT_MUTED}; font-size: 14px;")
        h.addWidget(dot)

        text = QLabel(name.upper())
        text.setStyleSheet(f"color: {C.TEXT_MUTED}; font-size: {F.SMALL}px;")
        h.addWidget(text)

        return dot, text, container

    @staticmethod
    def _time_ago(timestamp: float) -> str:
        """Convert a Unix timestamp to a human-readable 'time ago' string."""
        if not timestamp or timestamp <= 0:
            return "Never"
        diff = time.time() - timestamp
        if diff < 0:
            return "Just now"
        if diff < 60:
            return f"{int(diff)}s ago"
        if diff < 3600:
            minutes = int(diff / 60)
            return f"{minutes}m ago"
        if diff < 86400:
            hours = int(diff / 3600)
            return f"{hours}h ago"
        days = int(diff / 86400)
        return f"{days}d ago"
