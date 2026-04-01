"""
SmartLocker Home Dashboard Screen

Main dashboard with hero action button, status panel, navigation tiles,
and dynamic alarm/mixing bars.
"""

import time
import logging
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy, QSpacerItem, QGridLayout,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from ui_qt.theme import C, F, S
from ui_qt.animations import PulsingDot
from ui_qt.icons import (
    Icon, icon_badge, icon_label, status_dot, type_badge, section_header,
    screen_header,
)

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
        bar.setObjectName("top_bar")
        bar.setStyleSheet(
            f"QFrame#top_bar {{"
            f"  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            f"    stop:0 {C.BG_STATUS}, stop:0.7 {C.BG_STATUS}, stop:1 {C.PRIMARY_BG});"
            f"  border-bottom: 2px solid {C.PRIMARY};"
            f"  min-height: {S.STATUS_H}px;"
            f"  max-height: {S.STATUS_H}px;"
            f"}}"
        )

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(S.PAD, 0, S.PAD, 0)
        layout.setSpacing(S.GAP)

        # Lock icon badge
        lock_icon = icon_badge(Icon.LOCK, bg_color=C.PRIMARY_BG,
                               fg_color=C.PRIMARY, size=30)
        layout.addWidget(lock_icon)

        # Brand name
        brand = QLabel("PPG SMARTLOCKER")
        brand.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.PRIMARY};"
            f"letter-spacing: 2px;"
        )
        layout.addWidget(brand)

        layout.addStretch(1)

        # Mode badge (using type_badge style, but we create a QLabel to update)
        self._mode_badge = QLabel()
        layout.addWidget(self._mode_badge)

        # Cloud status badge with pulsing dot
        self._cloud_dot = PulsingDot(color=C.TEXT_MUTED, size=10)
        layout.addWidget(self._cloud_dot)
        self._cloud_badge = QLabel()
        layout.addWidget(self._cloud_badge)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(
            f"color: {C.BORDER}; max-width: 1px; margin: 8px 2px;"
        )
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
        card.setObjectName("hero_card")
        card.setStyleSheet(
            f"QFrame#hero_card {{"
            f"  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
            f"    stop:0 {C.PRIMARY_BG}, stop:0.5 {C.BG_CARD}, stop:1 {C.SECONDARY_BG});"
            f"  border: 2px solid {C.PRIMARY};"
            f"  border-radius: {S.RADIUS}px;"
            f"}}"
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        # Icon + Title row
        title_row = QHBoxLayout()
        title_row.setSpacing(S.GAP)

        title_row.addStretch(1)

        mixing_icon = icon_badge(Icon.MIXING, bg_color=C.PRIMARY_BG,
                                 fg_color=C.PRIMARY, size=40)
        title_row.addWidget(mixing_icon)

        title = QLabel("PAINT NOW!")
        title.setStyleSheet(
            f"font-size: {F.HERO}px; font-weight: bold; color: {C.PRIMARY};"
            f"letter-spacing: 2px;"
        )
        title_row.addWidget(title)
        title_row.addStretch(1)
        layout.addLayout(title_row)

        # Subtitle
        sub = QLabel("Tap to start a guided mixing operation")
        sub.setStyleSheet(f"font-size: {F.BODY}px; color: {C.TEXT_SEC};")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

        layout.addSpacing(4)

        # Big gradient action button
        btn = QPushButton(f"{Icon.PLAY}  START MIXING")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumHeight(S.BTN_H_LG)
        btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            f"    stop:0 {C.PRIMARY}, stop:1 {C.SECONDARY});"
            f"  color: {C.BG_DARK};"
            f"  border: none; border-radius: {S.RADIUS}px;"
            f"  font-size: {F.H2}px; font-weight: bold;"
            f"  letter-spacing: 2px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            f"    stop:0 {C.PRIMARY_DIM}, stop:1 {C.SECONDARY});"
            f"}}"
        )
        btn.clicked.connect(self._on_paint_now)
        layout.addWidget(btn)

        return card

    # ── Status Panel ──────────────────────────────────

    def _build_status_panel(self) -> QFrame:
        card = QFrame()
        card.setObjectName("status_panel")
        card.setStyleSheet(
            f"QFrame#status_panel {{"
            f"  background-color: {C.BG_CARD};"
            f"  border: 1px solid {C.BORDER};"
            f"  border-left: 4px solid {C.SECONDARY};"
            f"  border-radius: {S.RADIUS}px;"
            f"  padding: {S.PAD_CARD}px;"
            f"}}"
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 8, 8)
        layout.setSpacing(3)

        # Section header with icon
        layout.addWidget(section_header(Icon.HEALTH, "LIVE STATUS", C.SECONDARY))

        # Slot count row
        self._slot_dot = status_dot(active=True, size=8)
        self._slot_label = self._status_row(layout, "Slots", "--",
                                            self._slot_dot)

        # Cloud status row
        self._cloud_panel_dot = status_dot(active=False, size=8)
        self._cloud_status_label = self._status_row(layout, "Cloud", "--",
                                                    self._cloud_panel_dot)

        # Last sync row
        self._sync_dot = status_dot(active=True, size=8)
        self._sync_label = self._status_row(layout, "Sync", "--",
                                            self._sync_dot)

        # Driver status row
        self._driver_dot = status_dot(active=True, size=8)
        self._driver_label = self._status_row(layout, "Drivers", "--",
                                              self._driver_dot)

        # Pending events row
        self._pending_dot = status_dot(active=True, size=8)
        self._pending_label = self._status_row(layout, "Queue", "--",
                                               self._pending_dot)

        layout.addStretch(1)

        return card

    def _status_row(self, parent_layout: QVBoxLayout, label_text: str,
                    default_value: str,
                    dot_widget: QLabel = None) -> QLabel:
        """Create a dot + label: value row and return the value label."""
        row = QHBoxLayout()
        row.setSpacing(6)

        if dot_widget is not None:
            row.addWidget(dot_widget)

        key = QLabel(label_text)
        key.setStyleSheet(
            f"color: {C.TEXT_SEC}; font-size: {F.BODY}px;"
        )
        key.setFixedWidth(60)
        row.addWidget(key)

        val = QLabel(default_value)
        val.setStyleSheet(
            f"color: {C.TEXT}; font-size: {F.BODY}px; font-weight: bold;"
        )
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
            (Icon.CHART, "CHECK CHART", "Maintenance\n& paint specs",
             C.SECONDARY, "chart_viewer"),
            (Icon.INVENTORY, "INVENTORY", "Slot contents\n& stock levels",
             C.SUCCESS, "inventory"),
            (Icon.SENSORS, "SENSORS", "Test RFID, weight\nLED & buzzer",
             C.ACCENT, "sensor_test"),
            (Icon.SETTINGS, "SETTINGS", "Config, pairing\n& system",
             C.TEXT_MUTED, "settings"),
        ]

        for col, (icon, title, subtitle, accent, target) in enumerate(tiles):
            tile = self._make_nav_tile(icon, title, subtitle, accent, target)
            grid.addWidget(tile, 0, col)

        return container

    def _make_nav_tile(self, glyph: str, title: str, subtitle: str,
                       accent_color: str,
                       target_screen: str) -> QPushButton:
        btn = QPushButton()
        btn.setObjectName("nav_tile")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumHeight(60)

        # Accent top border
        btn.setStyleSheet(
            f"QPushButton#nav_tile {{ border-top: 3px solid {accent_color}; }}"
            f"QPushButton#nav_tile:hover {{ border-color: {accent_color}; }}"
        )

        # Build internal layout via a child widget
        inner = QWidget(btn)
        inner.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(8, 6, 8, 6)
        inner_layout.setSpacing(4)

        # Icon + title row
        icon_row = QHBoxLayout()
        icon_row.setSpacing(6)
        badge = icon_badge(glyph, bg_color=C.BG_CARD_ALT,
                           fg_color=accent_color, size=28)
        badge.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        icon_row.addWidget(badge)

        lbl_title = QLabel(title, inner)
        lbl_title.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.TEXT};"
        )
        lbl_title.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        icon_row.addWidget(lbl_title)
        icon_row.addStretch(1)
        inner_layout.addLayout(icon_row)

        lbl_sub = QLabel(subtitle, inner)
        lbl_sub.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.TEXT_SEC};"
        )
        lbl_sub.setWordWrap(True)
        lbl_sub.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        inner_layout.addWidget(lbl_sub)

        inner_layout.addStretch(1)

        btn.clicked.connect(
            lambda checked=False, s=target_screen: self.app.go_screen(s)
        )
        return btn

    # ── Alarm Bar ─────────────────────────────────────

    def _build_alarm_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("alarm_bar")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(S.PAD_CARD, 8, S.PAD_CARD, 8)
        layout.setSpacing(S.GAP)

        self._alarm_icon_badge = icon_badge(
            Icon.ALARM, bg_color=C.DANGER_BG, fg_color=C.DANGER, size=28
        )
        layout.addWidget(self._alarm_icon_badge)

        self._alarm_text = QLabel("No active alarms")
        self._alarm_text.setStyleSheet(
            f"font-size: {F.BODY}px; font-weight: bold; color: {C.TEXT};"
        )
        layout.addWidget(self._alarm_text, stretch=1)

        btn = QPushButton("VIEW")
        btn.setObjectName("danger")
        btn.setFixedWidth(80)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self.app.go_screen("alarm"))
        layout.addWidget(btn)

        return bar

    # ── Mixing Bar ────────────────────────────────────

    def _build_mixing_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("mixing_bar")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(S.PAD_CARD, 8, S.PAD_CARD, 8)
        layout.setSpacing(S.GAP)

        self._mix_icon_badge = icon_badge(
            Icon.MIXING, bg_color=C.PRIMARY_BG, fg_color=C.PRIMARY, size=28
        )
        layout.addWidget(self._mix_icon_badge)

        self._mix_text = QLabel("Mixing in progress...")
        self._mix_text.setStyleSheet(
            f"font-size: {F.BODY}px; font-weight: bold; color: {C.TEXT};"
        )
        layout.addWidget(self._mix_text, stretch=1)

        btn = QPushButton("RESUME")
        btn.setObjectName("primary")
        btn.setFixedWidth(100)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
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
            variant = "success"
        elif mode == "HYBRID":
            variant = "accent"
        else:
            variant = "muted"

        colors = {
            "success": (C.SUCCESS_BG, C.SUCCESS, C.SUCCESS),
            "accent": (C.ACCENT_BG, C.ACCENT, C.ACCENT),
            "muted": (C.BG_CARD_ALT, C.TEXT_MUTED, C.TEXT_MUTED),
        }
        bg, fg, border = colors[variant]
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
            self._cloud_dot.set_color(C.SUCCESS)
            self._cloud_dot.start()
        else:
            self._cloud_badge.setText("OFFLINE")
            self._cloud_badge.setStyleSheet(
                f"background-color: {C.DANGER_BG}; color: {C.DANGER};"
                f"border: 1px solid {C.DANGER}; border-radius: 4px;"
                f"padding: 2px 8px; font-size: {F.TINY}px; font-weight: bold;"
            )
            self._cloud_dot.set_color(C.DANGER)
            self._cloud_dot.stop()

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
                self._slot_dot.setStyleSheet(
                    f"background-color: {C.WARNING};"
                    f"border-radius: 4px; border: none;"
                )
            else:
                self._slot_label.setStyleSheet(
                    f"color: {C.TEXT}; font-size: {F.BODY}px; font-weight: bold;"
                )
                self._slot_dot.setStyleSheet(
                    f"background-color: {C.SUCCESS};"
                    f"border-radius: 4px; border: none;"
                )
        except Exception:
            self._slot_label.setText("--/--")

        # Cloud status
        is_paired = getattr(self.app.cloud, "is_paired", False)
        if is_paired:
            self._cloud_status_label.setText("Connected")
            self._cloud_status_label.setStyleSheet(
                f"color: {C.SUCCESS}; font-size: {F.BODY}px; font-weight: bold;"
            )
            self._cloud_panel_dot.setStyleSheet(
                f"background-color: {C.SUCCESS};"
                f"border-radius: 4px; border: none;"
            )
        else:
            self._cloud_status_label.setText("Disconnected")
            self._cloud_status_label.setStyleSheet(
                f"color: {C.DANGER}; font-size: {F.BODY}px; font-weight: bold;"
            )
            self._cloud_panel_dot.setStyleSheet(
                f"background-color: {C.DANGER};"
                f"border-radius: 4px; border: none;"
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
            if real_count == total_drv:
                self._driver_dot.setStyleSheet(
                    f"background-color: {C.SUCCESS};"
                    f"border-radius: 4px; border: none;"
                )
            elif real_count > 0:
                self._driver_dot.setStyleSheet(
                    f"background-color: {C.ACCENT};"
                    f"border-radius: 4px; border: none;"
                )
            else:
                self._driver_dot.setStyleSheet(
                    f"background-color: {C.TEXT_MUTED};"
                    f"border-radius: 4px; border: none;"
                )
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
                self._pending_dot.setStyleSheet(
                    f"background-color: {C.ACCENT};"
                    f"border-radius: 4px; border: none;"
                )
            else:
                self._pending_label.setText("All synced")
                self._pending_label.setStyleSheet(
                    f"color: {C.SUCCESS}; font-size: {F.BODY}px; font-weight: bold;"
                )
                self._pending_dot.setStyleSheet(
                    f"background-color: {C.SUCCESS};"
                    f"border-radius: 4px; border: none;"
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
                icon_fg = C.DANGER
            else:
                bg = C.WARNING_BG
                border = C.WARNING
                icon_fg = C.WARNING

            self._alarm_bar.setStyleSheet(
                f"QFrame#alarm_bar {{ background-color: {bg};"
                f"border: 1px solid {border}; border-radius: {S.RADIUS}px;"
                f"padding: {S.PAD_CARD}px; }}"
            )

            # Update icon badge colors
            self._alarm_icon_badge.setStyleSheet(
                f"background-color: {bg}; color: {icon_fg};"
                f"border-radius: 14px;"
                f"font-size: 15px; font-weight: bold;"
                f"border: 1px solid {icon_fg};"
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
                f"QFrame#mixing_bar {{ background-color: {C.PRIMARY_BG};"
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
