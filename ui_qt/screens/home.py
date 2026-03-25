"""
SmartLocker Home Dashboard Screen

Main dashboard with hero action button, status panel, navigation tiles,
and dynamic alarm/mixing bars.
"""

import time
import logging
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy, QSpacerItem, QGridLayout,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from ui_qt.theme import C, F, S

logger = logging.getLogger("smartlocker.ui.home")


class HomeScreen(QWidget):
    """Main dashboard screen for SmartLocker."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        self._build_ui()

    # ══════════════════════════════════════════════════════
    # UI CONSTRUCTION
    # ══════════════════════════════════════════════════════

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Status Bar ────────────────────────────────
        root.addWidget(self._build_status_bar())

        # ── Body (scrollable area) ────────────────────
        body = QVBoxLayout()
        body.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
        body.setSpacing(S.GAP)

        # Top row: hero button + status panel
        top_row = QHBoxLayout()
        top_row.setSpacing(S.GAP)
        top_row.addWidget(self._build_hero_card(), stretch=1)
        top_row.addWidget(self._build_status_panel(), stretch=1)
        body.addLayout(top_row)

        # Navigation tiles row
        body.addWidget(self._build_nav_section())

        # Alarm bar (hidden by default)
        self._alarm_bar = self._build_alarm_bar()
        self._alarm_bar.setVisible(False)
        body.addWidget(self._alarm_bar)

        # Mixing bar (hidden by default)
        self._mixing_bar = self._build_mixing_bar()
        self._mixing_bar.setVisible(False)
        body.addWidget(self._mixing_bar)

        # Push remaining space to bottom
        body.addStretch(1)

        root.addLayout(body, stretch=1)

    # ── Status Bar ────────────────────────────────────

    def _build_status_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("status_bar")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(S.PAD, 0, S.PAD, 0)
        layout.setSpacing(S.GAP)

        # Brand name
        brand = QLabel("PPG SMARTLOCKER")
        brand.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.PRIMARY};"
        )
        layout.addWidget(brand)

        layout.addStretch(1)

        # Mode badge
        self._mode_badge = QLabel()
        layout.addWidget(self._mode_badge)

        # Cloud status badge
        self._cloud_badge = QLabel()
        layout.addWidget(self._cloud_badge)

        # Separator
        sep = QLabel("|")
        sep.setStyleSheet(f"color: {C.TEXT_MUTED}; font-size: {F.BODY}px;")
        layout.addWidget(sep)

        # Clock
        self._clock_label = QLabel("--:--")
        self._clock_label.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.TEXT};"
        )
        layout.addWidget(self._clock_label)

        return bar

    # ── Hero Card ─────────────────────────────────────

    def _build_hero_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(
            f"QFrame#card {{ border-top: 3px solid {C.PRIMARY}; }}"
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(S.PAD_CARD, S.PAD_CARD, S.PAD_CARD, S.PAD_CARD)
        layout.setSpacing(8)

        # Title
        title = QLabel("PAINT NOW!")
        title.setObjectName("hero")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Subtitle
        sub = QLabel("Start a mixing operation")
        sub.setObjectName("subtitle")
        sub.setAlignment(Qt.AlignCenter)
        layout.addWidget(sub)

        layout.addSpacerItem(QSpacerItem(0, 8, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # Big action button
        btn = QPushButton("START MIXING")
        btn.setObjectName("primary")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumHeight(S.BTN_H_LG)
        btn.clicked.connect(self._on_paint_now)
        layout.addWidget(btn)

        return card

    # ── Status Panel ──────────────────────────────────

    def _build_status_panel(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(S.PAD_CARD, S.PAD_CARD, S.PAD_CARD, S.PAD_CARD)
        layout.setSpacing(6)

        # Section header
        header = QLabel("STATUS")
        header.setObjectName("section")
        layout.addWidget(header)

        # Slot count row
        self._slot_label = self._status_row(layout, "Slots:", "--")

        # Cloud status row
        self._cloud_status_label = self._status_row(layout, "Cloud:", "--")

        # Last sync row
        self._sync_label = self._status_row(layout, "Sync:", "--")

        # Driver status row
        self._driver_label = self._status_row(layout, "Drivers:", "--")

        # Pending events row
        self._pending_label = self._status_row(layout, "Queue:", "--")

        layout.addStretch(1)

        return card

    def _status_row(self, parent_layout: QVBoxLayout, label_text: str,
                    default_value: str) -> QLabel:
        """Create a label: value row and return the value label for updates."""
        row = QHBoxLayout()
        row.setSpacing(6)

        key = QLabel(label_text)
        key.setStyleSheet(f"color: {C.TEXT_SEC}; font-size: {F.BODY}px;")
        key.setFixedWidth(60)
        row.addWidget(key)

        val = QLabel(default_value)
        val.setStyleSheet(f"color: {C.TEXT}; font-size: {F.BODY}px; font-weight: bold;")
        row.addWidget(val)
        row.addStretch(1)

        parent_layout.addLayout(row)
        return val

    # ── Navigation Tiles ──────────────────────────────

    def _build_nav_section(self) -> QWidget:
        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(S.GAP)

        tiles = [
            ("CHECK CHART", "View maintenance\nschedule & paint specs",
             C.SECONDARY, "chart_viewer"),
            ("INVENTORY", "Browse slot contents\n& stock levels",
             C.SUCCESS, "inventory"),
            ("SENSORS", "Test RFID, weight,\nLED & buzzer",
             C.ACCENT, "sensor_test"),
            ("SETTINGS", "Device config,\npairing & system",
             C.TEXT_MUTED, "settings"),
        ]

        for col, (title, subtitle, accent, target) in enumerate(tiles):
            tile = self._make_nav_tile(title, subtitle, accent, target)
            grid.addWidget(tile, 0, col)

        return container

    def _make_nav_tile(self, title: str, subtitle: str,
                       accent_color: str, target_screen: str) -> QPushButton:
        btn = QPushButton()
        btn.setObjectName("nav_tile")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumHeight(90)

        # Use style with accent top border
        btn.setStyleSheet(
            f"QPushButton#nav_tile {{ border-top: 3px solid {accent_color}; }}"
            f"QPushButton#nav_tile:hover {{ border-color: {accent_color}; }}"
        )

        # Build internal layout via a child widget
        inner = QWidget(btn)
        inner.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(8, 6, 8, 6)
        inner_layout.setSpacing(4)

        lbl_title = QLabel(title, inner)
        lbl_title.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.TEXT};"
        )
        lbl_title.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        inner_layout.addWidget(lbl_title)

        lbl_sub = QLabel(subtitle, inner)
        lbl_sub.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.TEXT_SEC};"
        )
        lbl_sub.setWordWrap(True)
        lbl_sub.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        inner_layout.addWidget(lbl_sub)

        inner_layout.addStretch(1)

        btn.clicked.connect(lambda checked=False, s=target_screen: self.app.go_screen(s))
        return btn

    # ── Alarm Bar ─────────────────────────────────────

    def _build_alarm_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("card")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(S.PAD_CARD, 8, S.PAD_CARD, 8)
        layout.setSpacing(S.GAP)

        self._alarm_icon = QLabel("[!]")
        self._alarm_icon.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.DANGER};"
        )
        layout.addWidget(self._alarm_icon)

        self._alarm_text = QLabel("No active alarms")
        self._alarm_text.setStyleSheet(
            f"font-size: {F.BODY}px; font-weight: bold; color: {C.TEXT};"
        )
        layout.addWidget(self._alarm_text, stretch=1)

        btn = QPushButton("VIEW")
        btn.setObjectName("danger")
        btn.setFixedWidth(80)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda: self.app.go_screen("alarm"))
        layout.addWidget(btn)

        return bar

    # ── Mixing Bar ────────────────────────────────────

    def _build_mixing_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("card")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(S.PAD_CARD, 8, S.PAD_CARD, 8)
        layout.setSpacing(S.GAP)

        self._mix_icon = QLabel("[MIX]")
        self._mix_icon.setStyleSheet(
            f"font-size: {F.BODY}px; font-weight: bold; color: {C.PRIMARY};"
        )
        layout.addWidget(self._mix_icon)

        self._mix_text = QLabel("Mixing in progress...")
        self._mix_text.setStyleSheet(
            f"font-size: {F.BODY}px; font-weight: bold; color: {C.TEXT};"
        )
        layout.addWidget(self._mix_text, stretch=1)

        btn = QPushButton("RESUME")
        btn.setObjectName("primary")
        btn.setFixedWidth(100)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda: self.app.go_screen("mixing"))
        layout.addWidget(btn)

        return bar

    # ══════════════════════════════════════════════════════
    # LIFECYCLE
    # ══════════════════════════════════════════════════════

    def on_enter(self):
        """Called when this screen becomes visible. Start periodic updates."""
        self._tick()  # Immediate update
        self._timer.start(1000)

    def on_leave(self):
        """Called when navigating away. Stop periodic updates."""
        self._timer.stop()

    # ══════════════════════════════════════════════════════
    # PERIODIC UPDATE
    # ══════════════════════════════════════════════════════

    def _tick(self):
        """Update all dynamic elements every second."""
        self._update_clock()
        self._update_mode_badge()
        self._update_cloud_badge()
        self._update_status_panel()
        self._update_alarm_bar()
        self._update_mixing_bar()

    def _update_clock(self):
        now = datetime.now()
        self._clock_label.setText(now.strftime("%H:%M"))

    def _update_mode_badge(self):
        mode = getattr(self.app, "mode", "test").upper()
        if mode == "LIVE":
            bg, fg, border = C.SUCCESS_BG, C.SUCCESS, C.SUCCESS
        elif mode == "HYBRID":
            bg, fg, border = C.ACCENT_BG, C.ACCENT, C.ACCENT
        else:
            bg, fg, border = C.BG_CARD_ALT, C.TEXT_MUTED, C.TEXT_MUTED

        self._mode_badge.setText(mode)
        self._mode_badge.setStyleSheet(
            f"background-color: {bg}; color: {fg}; border: 1px solid {border};"
            f"border-radius: 4px; padding: 2px 8px;"
            f"font-size: {F.TINY}px; font-weight: bold;"
        )

    def _update_cloud_badge(self):
        is_paired = getattr(self.app.cloud, "is_paired", False)
        if is_paired:
            self._cloud_badge.setText("CLOUD")
            self._cloud_badge.setStyleSheet(
                f"background-color: {C.SUCCESS_BG}; color: {C.SUCCESS};"
                f"border: 1px solid {C.SUCCESS}; border-radius: 4px;"
                f"padding: 2px 8px; font-size: {F.TINY}px; font-weight: bold;"
            )
        else:
            self._cloud_badge.setText("OFFLINE")
            self._cloud_badge.setStyleSheet(
                f"background-color: {C.DANGER_BG}; color: {C.DANGER};"
                f"border: 1px solid {C.DANGER}; border-radius: 4px;"
                f"padding: 2px 8px; font-size: {F.TINY}px; font-weight: bold;"
            )

    def _update_status_panel(self):
        # Slot count
        try:
            inv = self.app.inventory_engine
            all_slots = inv.get_all_slots()
            occupied = inv.get_occupied_slots()
            total = len(all_slots)
            occ = len(occupied)
            self._slot_label.setText(f"{occ}/{total} occupied")
            if occ >= total:
                self._slot_label.setStyleSheet(
                    f"color: {C.WARNING}; font-size: {F.BODY}px; font-weight: bold;"
                )
            else:
                self._slot_label.setStyleSheet(
                    f"color: {C.TEXT}; font-size: {F.BODY}px; font-weight: bold;"
                )
        except Exception:
            self._slot_label.setText("--/--")

        # Cloud status
        is_paired = getattr(self.app.cloud, "is_paired", False)
        if is_paired:
            self._cloud_status_label.setText("(*) Connected")
            self._cloud_status_label.setStyleSheet(
                f"color: {C.SUCCESS}; font-size: {F.BODY}px; font-weight: bold;"
            )
        else:
            self._cloud_status_label.setText("(x) Disconnected")
            self._cloud_status_label.setStyleSheet(
                f"color: {C.DANGER}; font-size: {F.BODY}px; font-weight: bold;"
            )

        # Last sync time
        try:
            last_ts = self.app.sync_engine._last_sync_time
            if last_ts > 0:
                elapsed = time.time() - last_ts
                if elapsed < 60:
                    self._sync_label.setText("Just now")
                elif elapsed < 3600:
                    mins = int(elapsed / 60)
                    self._sync_label.setText(f"{mins} min ago")
                else:
                    hours = int(elapsed / 3600)
                    self._sync_label.setText(f"{hours}h ago")
            else:
                self._sync_label.setText("Not yet")
        except Exception:
            self._sync_label.setText("N/A")

        # Driver status summary
        try:
            ds = self.app.driver_status
            real_count = sum(1 for v in ds.values() if v == "real")
            total_drv = len(ds)
            self._driver_label.setText(f"{real_count}/{total_drv} real")
        except Exception:
            self._driver_label.setText("--")

        # Pending sync queue
        try:
            stats = self.app.sync_engine.get_status()
            unsynced = stats.get("events_unsynced", 0)
            if unsynced > 0:
                self._pending_label.setText(f"{unsynced} pending")
                self._pending_label.setStyleSheet(
                    f"color: {C.ACCENT}; font-size: {F.BODY}px; font-weight: bold;"
                )
            else:
                self._pending_label.setText("All synced")
                self._pending_label.setStyleSheet(
                    f"color: {C.SUCCESS}; font-size: {F.BODY}px; font-weight: bold;"
                )
        except Exception:
            self._pending_label.setText("--")

    def _update_alarm_bar(self):
        try:
            alarm_mgr = self.app.alarm_manager
            active = alarm_mgr.get_active_alarms()
            count = len(active)

            if count == 0:
                self._alarm_bar.setVisible(False)
                return

            self._alarm_bar.setVisible(True)

            has_critical = alarm_mgr.has_critical()
            if has_critical:
                bg = C.DANGER_BG
                border = C.DANGER
                icon_color = C.DANGER
                self._alarm_icon.setText("[!!]")
            else:
                bg = C.WARNING_BG
                border = C.WARNING
                icon_color = C.WARNING
                self._alarm_icon.setText("[!]")

            self._alarm_bar.setStyleSheet(
                f"QFrame#card {{ background-color: {bg};"
                f"border: 1px solid {border}; border-radius: {S.RADIUS}px;"
                f"padding: {S.PAD_CARD}px; }}"
            )
            self._alarm_icon.setStyleSheet(
                f"font-size: {F.H3}px; font-weight: bold; color: {icon_color};"
            )

            if count == 1:
                title = active[0].get("error_title", "Alarm")
                self._alarm_text.setText(f"ALARM: {title}")
            else:
                self._alarm_text.setText(f"{count} ACTIVE ALARMS")

        except Exception as e:
            logger.debug(f"Alarm bar update error: {e}")
            self._alarm_bar.setVisible(False)

    def _update_mixing_bar(self):
        try:
            session = self.app.mixing_engine.session
            if session is None:
                self._mixing_bar.setVisible(False)
                return

            # Session exists and is not idle
            from core.mixing_engine import MixingState
            if session.state == MixingState.IDLE:
                self._mixing_bar.setVisible(False)
                return

            self._mixing_bar.setVisible(True)

            state_name = session.state.name.replace("_", " ").title()
            recipe_id = getattr(session, "recipe_id", "")
            if recipe_id:
                self._mix_text.setText(
                    f"Mixing: {recipe_id} -- {state_name}"
                )
            else:
                self._mix_text.setText(f"Mixing in progress -- {state_name}")

            self._mixing_bar.setStyleSheet(
                f"QFrame#card {{ background-color: {C.PRIMARY_BG};"
                f"border: 1px solid {C.PRIMARY}; border-radius: {S.RADIUS}px;"
                f"padding: {S.PAD_CARD}px; }}"
            )

        except Exception as e:
            logger.debug(f"Mixing bar update error: {e}")
            self._mixing_bar.setVisible(False)

    # ══════════════════════════════════════════════════════
    # ACTIONS
    # ══════════════════════════════════════════════════════

    def _on_paint_now(self):
        """Navigate to the paint/mixing screen."""
        self.app.go_screen("paint_now")
