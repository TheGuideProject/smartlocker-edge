"""
SmartLocker Home Dashboard Screen

Main dashboard with hero action button, status panel, navigation tiles,
and dynamic alarm/mixing bars. Optimized for 800x480 touchscreen.
"""

import time
import logging
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from ui_qt.theme import C, F, S
from ui_qt.animations import PulsingDot
from ui_qt.icons import (
    Icon, icon_badge, icon_label, status_dot, type_badge, section_header,
)

logger = logging.getLogger("smartlocker.ui.home")


class ClickableTile(QFrame):
    """A nav tile frame that responds to taps."""

    def __init__(self, callback):
        super().__init__()
        self._callback = callback
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        self._callback()
        super().mousePressEvent(event)


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

        # ── Body ──────────────────────────────────────
        body = QVBoxLayout()
        body.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
        body.setSpacing(S.GAP)

        # Top row: hero button + status panel
        top_row = QHBoxLayout()
        top_row.setSpacing(S.GAP)
        top_row.addWidget(self._build_hero_card(), stretch=3)
        top_row.addWidget(self._build_status_panel(), stretch=2)
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
            f"  min-height: 44px; max-height: 44px;"
            f"}}"
        )

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(S.PAD, 0, S.PAD, 0)
        layout.setSpacing(6)

        # Lock icon
        lock_icon = icon_badge(Icon.LOCK, bg_color=C.PRIMARY_BG,
                               fg_color=C.PRIMARY, size=26)
        layout.addWidget(lock_icon)

        # Brand name
        brand = QLabel("PPG SMARTLOCKER")
        brand.setStyleSheet(
            f"font-size: {F.BODY}px; font-weight: bold; color: {C.PRIMARY};"
            f"letter-spacing: 2px;"
        )
        layout.addWidget(brand)

        layout.addStretch(1)

        # Mode badge
        self._mode_badge = QLabel()
        layout.addWidget(self._mode_badge)

        # Cloud status badge with pulsing dot
        self._cloud_dot = PulsingDot(color=C.TEXT_MUTED, size=8)
        layout.addWidget(self._cloud_dot)
        self._cloud_badge = QLabel()
        layout.addWidget(self._cloud_badge)

        # Clock
        self._clock_label = QLabel("--:--")
        self._clock_label.setStyleSheet(
            f"font-size: {F.BODY}px; font-weight: bold; color: {C.TEXT};"
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
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Icon + Title row (centered)
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        mixing_icon = icon_badge(Icon.MIXING, bg_color=C.PRIMARY_BG,
                                 fg_color=C.PRIMARY, size=32)
        title_row.addWidget(mixing_icon)

        title = QLabel("PAINT NOW!")
        title.setStyleSheet(
            f"font-size: {F.H1}px; font-weight: bold; color: {C.PRIMARY};"
            f"letter-spacing: 2px;"
        )
        title_row.addWidget(title)
        layout.addLayout(title_row)

        # Subtitle
        sub = QLabel("Tap to start a guided mixing operation")
        sub.setStyleSheet(f"font-size: {F.SMALL}px; color: {C.TEXT_SEC};")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

        layout.addSpacing(2)

        # Big action button
        btn = QPushButton(f"{Icon.PLAY}  START MIXING")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumHeight(48)
        btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            f"    stop:0 {C.PRIMARY}, stop:1 {C.SECONDARY});"
            f"  color: {C.BG_DARK};"
            f"  border: none; border-radius: {S.RADIUS}px;"
            f"  font-size: {F.H3}px; font-weight: bold;"
            f"  letter-spacing: 2px; min-height: 48px;"
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
            f"  border-left: 3px solid {C.SECONDARY};"
            f"  border-radius: {S.RADIUS}px;"
            f"}}"
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 6, 8, 6)
        layout.setSpacing(1)

        # Section header
        hdr = QHBoxLayout()
        hdr.setSpacing(4)
        hdr.addWidget(icon_label(Icon.HEALTH, color=C.SECONDARY, size=14))
        lbl_hdr = QLabel("LIVE STATUS")
        lbl_hdr.setStyleSheet(
            f"font-size: {F.TINY}px; font-weight: bold; color: {C.SECONDARY};"
            f"letter-spacing: 1px;"
        )
        hdr.addWidget(lbl_hdr)
        hdr.addStretch(1)
        layout.addLayout(hdr)

        # Status rows using grid for perfect alignment
        grid = QGridLayout()
        grid.setContentsMargins(0, 2, 0, 0)
        grid.setSpacing(2)
        grid.setColumnMinimumWidth(0, 12)  # dot column
        grid.setColumnMinimumWidth(1, 52)  # label column
        grid.setColumnStretch(2, 1)        # value column stretches

        self._slot_dot = status_dot(active=True, size=7)
        self._slot_label = QLabel("--")
        grid.addWidget(self._slot_dot, 0, 0, Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(self._make_key("Slots"), 0, 1)
        grid.addWidget(self._slot_label, 0, 2)

        self._cloud_panel_dot = status_dot(active=False, size=7)
        self._cloud_status_label = QLabel("--")
        grid.addWidget(self._cloud_panel_dot, 1, 0, Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(self._make_key("Cloud"), 1, 1)
        grid.addWidget(self._cloud_status_label, 1, 2)

        self._sync_dot = status_dot(active=True, size=7)
        self._sync_label = QLabel("--")
        grid.addWidget(self._sync_dot, 2, 0, Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(self._make_key("Sync"), 2, 1)
        grid.addWidget(self._sync_label, 2, 2)

        self._driver_dot = status_dot(active=True, size=7)
        self._driver_label = QLabel("--")
        grid.addWidget(self._driver_dot, 3, 0, Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(self._make_key("Drivers"), 3, 1)
        grid.addWidget(self._driver_label, 3, 2)

        self._pending_dot = status_dot(active=True, size=7)
        self._pending_label = QLabel("--")
        grid.addWidget(self._pending_dot, 4, 0, Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(self._make_key("Queue"), 4, 1)
        grid.addWidget(self._pending_label, 4, 2)

        layout.addLayout(grid)
        layout.addStretch(1)

        # Style all value labels
        for lbl in (self._slot_label, self._cloud_status_label,
                    self._sync_label, self._driver_label, self._pending_label):
            lbl.setStyleSheet(
                f"color: {C.TEXT}; font-size: {F.SMALL}px; font-weight: bold;"
            )

        return card

    def _make_key(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {C.TEXT_SEC}; font-size: {F.SMALL}px;"
        )
        return lbl

    # ── Navigation Tiles ──────────────────────────────

    def _build_nav_section(self) -> QWidget:
        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(S.GAP)

        tiles = [
            (Icon.CHART, "CHART", "Maintenance\n& paint specs",
             C.SECONDARY, "chart_viewer"),
            (Icon.INVENTORY, "INVENTORY", "Slot contents\n& stock levels",
             C.SUCCESS, "inventory"),
            (Icon.ADD, "CARICO", "Carica latte\nsullo scaffale",
             C.PRIMARY, "stock_loading"),
            (Icon.SENSORS, "SENSORS", "Test RFID, weight\nLED & buzzer",
             C.ACCENT, "sensor_test"),
            (Icon.SETTINGS, "SETTINGS", "Config, pairing\n& system",
             C.TEXT_MUTED, "settings"),
        ]

        for col, (icon, title, subtitle, accent, target) in enumerate(tiles):
            tile = self._make_nav_tile(icon, title, subtitle, accent, target)
            grid.addWidget(tile, 0, col)

        # Equal column stretch
        for col in range(5):
            grid.setColumnStretch(col, 1)

        return container

    def _make_nav_tile(self, glyph: str, title: str, subtitle: str,
                       accent_color: str,
                       target_screen: str) -> QFrame:
        tile = ClickableTile(lambda s=target_screen: self.app.go_screen(s))
        tile.setObjectName("nav_tile_frame")
        tile.setStyleSheet(
            f"QFrame#nav_tile_frame {{"
            f"  background-color: {C.BG_CARD};"
            f"  border: 1px solid {C.BORDER};"
            f"  border-top: 3px solid {accent_color};"
            f"  border-radius: {S.RADIUS}px;"
            f"}}"
            f"QFrame#nav_tile_frame:hover {{"
            f"  border-color: {accent_color};"
            f"}}"
        )

        layout = QVBoxLayout(tile)
        layout.setContentsMargins(8, 8, 8, 6)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Icon badge (centered)
        badge = icon_badge(glyph, bg_color=C.BG_CARD_ALT,
                           fg_color=accent_color, size=26)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignCenter)

        # Title (centered, bold)
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(
            f"font-size: {F.BODY}px; font-weight: bold; color: {C.TEXT};"
        )
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_title)

        # Subtitle (centered, muted)
        lbl_sub = QLabel(subtitle)
        lbl_sub.setStyleSheet(
            f"font-size: {F.TINY}px; color: {C.TEXT_SEC};"
        )
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_sub.setWordWrap(True)
        layout.addWidget(lbl_sub)

        return tile

    # ── Alarm Bar ─────────────────────────────────────

    def _build_alarm_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("alarm_bar")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(S.PAD_CARD, 6, S.PAD_CARD, 6)
        layout.setSpacing(S.GAP)

        self._alarm_icon_badge = icon_badge(
            Icon.ALARM, bg_color=C.DANGER_BG, fg_color=C.DANGER, size=24
        )
        layout.addWidget(self._alarm_icon_badge)

        self._alarm_text = QLabel("No active alarms")
        self._alarm_text.setStyleSheet(
            f"font-size: {F.SMALL}px; font-weight: bold; color: {C.TEXT};"
        )
        self._alarm_text.setMaximumWidth(550)
        layout.addWidget(self._alarm_text, stretch=1)

        btn = QPushButton(f"{Icon.WARN} VIEW")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumWidth(90)
        btn.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {C.DANGER}; color: {C.BG_DARK};"
            f"  border: none; border-radius: 6px;"
            f"  font-size: {F.BODY}px; font-weight: bold;"
            f"  padding: 8px 12px; min-height: 36px;"
            f"}}"
        )
        btn.clicked.connect(lambda: self.app.go_screen("alarm"))
        layout.addWidget(btn)

        return bar

    # ── Mixing Bar ────────────────────────────────────

    def _build_mixing_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("mixing_bar")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(S.PAD_CARD, 6, S.PAD_CARD, 6)
        layout.setSpacing(S.GAP)

        self._mix_icon_badge = icon_badge(
            Icon.MIXING, bg_color=C.PRIMARY_BG, fg_color=C.PRIMARY, size=24
        )
        layout.addWidget(self._mix_icon_badge)

        self._mix_text = QLabel("Mixing in progress...")
        self._mix_text.setStyleSheet(
            f"font-size: {F.SMALL}px; font-weight: bold; color: {C.TEXT};"
        )
        self._mix_text.setMaximumWidth(550)
        layout.addWidget(self._mix_text, stretch=1)

        btn = QPushButton(f"{Icon.PLAY} RESUME")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumWidth(110)
        btn.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {C.PRIMARY}; color: {C.BG_DARK};"
            f"  border: none; border-radius: 6px;"
            f"  font-size: {F.BODY}px; font-weight: bold;"
            f"  padding: 8px 16px; min-height: 36px;"
            f"}}"
        )
        btn.clicked.connect(lambda: self.app.go_screen("mixing"))
        layout.addWidget(btn)

        return bar

    # ══════════════════════════════════════════════════════
    # LIFECYCLE
    # ══════════════════════════════════════════════════════

    def on_enter(self):
        self._tick()
        self._timer.start(1000)

    def on_leave(self):
        self._timer.stop()

    # ══════════════════════════════════════════════════════
    # PERIODIC UPDATE
    # ══════════════════════════════════════════════════════

    def _tick(self):
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
        colors = {
            "LIVE": (C.SUCCESS_BG, C.SUCCESS, C.SUCCESS),
            "HYBRID": (C.ACCENT_BG, C.ACCENT, C.ACCENT),
        }
        bg, fg, border = colors.get(mode, (C.BG_CARD_ALT, C.TEXT_MUTED, C.TEXT_MUTED))
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
            warn = occ >= total
            color = C.WARNING if warn else C.TEXT
            dot_color = C.WARNING if warn else C.SUCCESS
            self._slot_label.setStyleSheet(
                f"color: {color}; font-size: {F.SMALL}px; font-weight: bold;"
            )
            self._slot_dot.setStyleSheet(
                f"background-color: {dot_color}; border-radius: 3px; border: none;"
            )
        except Exception:
            self._slot_label.setText("--/--")

        # Cloud status
        is_paired = getattr(self.app.cloud, "is_paired", False)
        if is_paired:
            self._cloud_status_label.setText("Connected")
            self._cloud_status_label.setStyleSheet(
                f"color: {C.SUCCESS}; font-size: {F.SMALL}px; font-weight: bold;"
            )
            self._cloud_panel_dot.setStyleSheet(
                f"background-color: {C.SUCCESS}; border-radius: 3px; border: none;"
            )
        else:
            self._cloud_status_label.setText("Disconnected")
            self._cloud_status_label.setStyleSheet(
                f"color: {C.DANGER}; font-size: {F.SMALL}px; font-weight: bold;"
            )
            self._cloud_panel_dot.setStyleSheet(
                f"background-color: {C.DANGER}; border-radius: 3px; border: none;"
            )

        # Last sync time
        try:
            last_ts = self.app.sync_engine._last_sync_time
            if last_ts > 0:
                elapsed = time.time() - last_ts
                if elapsed < 60:
                    self._sync_label.setText("Just now")
                elif elapsed < 3600:
                    self._sync_label.setText(f"{int(elapsed / 60)} min ago")
                else:
                    self._sync_label.setText(f"{int(elapsed / 3600)}h ago")
            else:
                self._sync_label.setText("Not yet")
        except Exception:
            self._sync_label.setText("N/A")

        # Driver status
        try:
            ds = self.app.driver_status
            real_count = sum(1 for v in ds.values() if v in ("real", "socket"))
            total_drv = len(ds)
            has_socket = any(v == "socket" for v in ds.values())
            if has_socket:
                self._driver_label.setText(f"Daemon ({real_count}/{total_drv})")
            else:
                self._driver_label.setText(f"{real_count}/{total_drv} real")
            if real_count == total_drv:
                dot_c = C.SUCCESS
            elif real_count > 0:
                dot_c = C.ACCENT
            else:
                dot_c = C.TEXT_MUTED
            self._driver_dot.setStyleSheet(
                f"background-color: {dot_c}; border-radius: 3px; border: none;"
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
                    f"color: {C.ACCENT}; font-size: {F.SMALL}px; font-weight: bold;"
                )
                self._pending_dot.setStyleSheet(
                    f"background-color: {C.ACCENT}; border-radius: 3px; border: none;"
                )
            else:
                self._pending_label.setText("All synced")
                self._pending_label.setStyleSheet(
                    f"color: {C.SUCCESS}; font-size: {F.SMALL}px; font-weight: bold;"
                )
                self._pending_dot.setStyleSheet(
                    f"background-color: {C.SUCCESS}; border-radius: 3px; border: none;"
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
                bg, border, icon_fg = C.DANGER_BG, C.DANGER, C.DANGER
            else:
                bg, border, icon_fg = C.WARNING_BG, C.WARNING, C.WARNING

            self._alarm_bar.setStyleSheet(
                f"QFrame#alarm_bar {{ background-color: {bg};"
                f"border: 1px solid {border}; border-radius: {S.RADIUS}px; }}"
            )
            self._alarm_icon_badge.setStyleSheet(
                f"background-color: {bg}; color: {icon_fg};"
                f"border-radius: 12px; font-size: 13px; font-weight: bold;"
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

            from core.mixing_engine import MixingState
            if session.state == MixingState.IDLE:
                self._mixing_bar.setVisible(False)
                return

            self._mixing_bar.setVisible(True)

            state_name = session.state.name.replace("_", " ").title()
            recipe_id = getattr(session, "recipe_id", "")
            if recipe_id:
                # Truncate long recipe IDs
                short_id = recipe_id if len(recipe_id) <= 25 else recipe_id[:22] + "..."
                self._mix_text.setText(f"{short_id} - {state_name}")
            else:
                self._mix_text.setText(f"Mixing - {state_name}")

            self._mixing_bar.setStyleSheet(
                f"QFrame#mixing_bar {{ background-color: {C.PRIMARY_BG};"
                f"border: 1px solid {C.PRIMARY}; border-radius: {S.RADIUS}px; }}"
            )

        except Exception as e:
            logger.debug(f"Mixing bar update error: {e}")
            self._mixing_bar.setVisible(False)

    # ══════════════════════════════════════════════════════
    # ACTIONS
    # ══════════════════════════════════════════════════════

    def _on_paint_now(self):
        self.app.go_screen("paint_now")
