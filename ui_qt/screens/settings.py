"""
SmartLocker Settings Screen

Scrollable card-based layout showing device info, cloud connection,
and system navigation buttons.
"""

import time
import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QGridLayout, QSizePolicy, QDialog, QTextEdit,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from ui_qt.theme import C, F, S, enable_touch_scroll
from ui_qt.icons import (
    Icon, icon_badge, icon_label, status_dot, type_badge, section_header,
    screen_header,
)

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
        self._drv_badges = {}       # driver_name -> type_badge QLabel
        self._cloud_dot = None
        self._lbl_cloud_status = None
        self._lbl_vessel = None
        self._lbl_last_sync = None
        self._lbl_events = None
        self._btn_sync = None
        self._btn_view_queue = None
        self._btn_flush = None
        self._btn_unpair = None

        self._build_ui()

    # ══════════════════════════════════════════════════════
    # UI BUILD
    # ══════════════════════════════════════════════════════

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Screen header (consistent) ──
        header, header_layout = screen_header(
            self.app, "SETTINGS", Icon.SETTINGS
        )
        root.addWidget(header)

        # ── Scroll area ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

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
        card = self._make_card(C.SECONDARY)
        lay = QVBoxLayout(card)
        lay.setSpacing(S.GAP)

        # Section header with icon
        lay.addWidget(section_header(Icon.INFO, "DEVICE", C.SECONDARY))

        # Info grid
        grid = QGridLayout()
        grid.setHorizontalSpacing(S.PAD)
        grid.setVerticalSpacing(6)

        # Row 0: Device ID
        r = 0
        grid.addWidget(icon_label(Icon.LOCK, color=C.TEXT_MUTED, size=14),
                        r, 0)
        grid.addWidget(self._muted_label("Device ID"), r, 1)
        self._lbl_device_id = QLabel("---")
        self._lbl_device_id.setStyleSheet(
            f"color: {C.TEXT}; font-weight: bold; font-size: {F.BODY}px;"
        )
        grid.addWidget(self._lbl_device_id, r, 2)

        # Row 1: Mode
        r = 1
        grid.addWidget(icon_label(Icon.SETTINGS, color=C.TEXT_MUTED, size=14),
                        r, 0)
        grid.addWidget(self._muted_label("Mode"), r, 1)
        self._lbl_mode = QLabel("---")
        self._lbl_mode.setStyleSheet(
            f"color: {C.PRIMARY}; font-weight: bold; font-size: {F.BODY}px;"
        )
        grid.addWidget(self._lbl_mode, r, 2)

        # Row 2: Version
        r = 2
        grid.addWidget(icon_label(Icon.INFO, color=C.TEXT_MUTED, size=14),
                        r, 0)
        grid.addWidget(self._muted_label("Version"), r, 1)
        self._lbl_version = QLabel("---")
        self._lbl_version.setStyleSheet(
            f"color: {C.TEXT}; font-size: {F.BODY}px;"
        )
        grid.addWidget(self._lbl_version, r, 2)

        lay.addLayout(grid)

        # Driver chips section
        lay.addWidget(section_header(Icon.SENSORS, "DRIVERS", C.TEXT_MUTED))

        drv_row = QHBoxLayout()
        drv_row.setSpacing(S.GAP)
        for name in ("rfid", "weight", "led", "buzzer"):
            badge = type_badge(name.upper(), "muted")
            self._drv_badges[name] = badge
            drv_row.addWidget(badge)
        drv_row.addStretch()
        lay.addLayout(drv_row)

        return card

    # ──────────────────────────────────────────────────────
    # CLOUD CONNECTION card
    # ──────────────────────────────────────────────────────

    def _build_cloud_card(self) -> QFrame:
        card = self._make_card(C.PRIMARY)
        lay = QVBoxLayout(card)
        lay.setSpacing(S.GAP)

        # Section header
        lay.addWidget(section_header(Icon.CLOUD, "CLOUD CONNECTION", C.PRIMARY))

        # Status row with dot
        status_row = QHBoxLayout()
        status_row.setSpacing(S.GAP)
        self._cloud_dot = status_dot(active=False, size=10)
        status_row.addWidget(self._cloud_dot)

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

        grid.addWidget(icon_label(Icon.SHELF, color=C.TEXT_MUTED, size=14),
                        0, 0)
        grid.addWidget(self._muted_label("Vessel"), 0, 1)
        self._lbl_vessel = QLabel("---")
        self._lbl_vessel.setStyleSheet(
            f"color: {C.TEXT}; font-size: {F.BODY}px;"
        )
        grid.addWidget(self._lbl_vessel, 0, 2)

        grid.addWidget(icon_label(Icon.REFRESH, color=C.TEXT_MUTED, size=14),
                        1, 0)
        grid.addWidget(self._muted_label("Last Sync"), 1, 1)
        self._lbl_last_sync = QLabel("---")
        self._lbl_last_sync.setStyleSheet(
            f"color: {C.TEXT}; font-size: {F.BODY}px;"
        )
        grid.addWidget(self._lbl_last_sync, 1, 2)

        grid.addWidget(icon_label(Icon.DOT, color=C.TEXT_MUTED, size=14),
                        2, 0)
        grid.addWidget(self._muted_label("Events"), 2, 1)
        self._lbl_events = QLabel("---")
        self._lbl_events.setStyleSheet(
            f"color: {C.TEXT}; font-size: {F.BODY}px;"
        )
        grid.addWidget(self._lbl_events, 2, 2)

        lay.addLayout(grid)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(S.GAP)

        self._btn_sync = QPushButton(f"{Icon.REFRESH}  SYNC NOW")
        self._btn_sync.setObjectName("secondary")
        self._btn_sync.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_sync.clicked.connect(self._on_sync_now)
        btn_row.addWidget(self._btn_sync)

        self._btn_view_queue = QPushButton(f"{Icon.CHART}  VIEW QUEUE")
        self._btn_view_queue.setObjectName("secondary")
        self._btn_view_queue.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_view_queue.clicked.connect(self._on_view_queue)
        btn_row.addWidget(self._btn_view_queue)

        self._btn_flush = QPushButton(f"{Icon.DELETE}  FLUSH")
        self._btn_flush.setObjectName("danger")
        self._btn_flush.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_flush.setToolTip("Force-clear all stuck pending events")
        self._btn_flush.clicked.connect(self._on_flush_queue)
        btn_row.addWidget(self._btn_flush)

        self._btn_unpair = QPushButton(f"{Icon.CLOSE}  UNPAIR")
        self._btn_unpair.setObjectName("danger")
        self._btn_unpair.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_unpair.clicked.connect(self._on_unpair)
        btn_row.addWidget(self._btn_unpair)

        lay.addLayout(btn_row)

        return card

    # ──────────────────────────────────────────────────────
    # SYSTEM card
    # ──────────────────────────────────────────────────────

    def _build_system_card(self) -> QFrame:
        card = self._make_card(C.ACCENT)
        lay = QVBoxLayout(card)
        lay.setSpacing(S.GAP)

        # Section header
        lay.addWidget(section_header(Icon.HEALTH, "SYSTEM", C.ACCENT))

        # Button grid with icon badges
        grid = QGridLayout()
        grid.setSpacing(S.GAP)

        btn_sensor = self._system_button(
            Icon.SENSORS, "SENSOR TESTING", C.ACCENT, "accent"
        )
        btn_sensor.clicked.connect(
            lambda: self.app.go_screen("sensor_test")
        )
        grid.addWidget(btn_sensor, 0, 0)

        btn_health = self._system_button(
            Icon.HEALTH, "SYSTEM HEALTH", C.ACCENT, "accent"
        )
        btn_health.clicked.connect(
            lambda: self.app.go_screen("system_health")
        )
        grid.addWidget(btn_health, 0, 1)

        btn_admin = self._system_button(
            Icon.SETTINGS, "ADMIN", C.ACCENT, "accent"
        )
        btn_admin.clicked.connect(
            lambda: self.app.go_screen("admin")
        )
        grid.addWidget(btn_admin, 0, 2)

        btn_tag = self._system_button(
            Icon.TAG, "TAG WRITER", C.SECONDARY, "secondary"
        )
        btn_tag.clicked.connect(
            lambda: self.app.go_screen("tag_writer")
        )
        grid.addWidget(btn_tag, 1, 0)

        lay.addLayout(grid)

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
        self._lbl_mode.setText(
            self.app.mode.upper() if self.app.mode else "---"
        )

        # Version
        try:
            from sync.update_manager import read_version
            version = read_version()
        except Exception:
            version = "?.?.?"
        self._lbl_version.setText(f"v{version}")

        # Driver badges (type_badge style update)
        driver_status = getattr(self.app, "driver_status", {})
        for name, badge_lbl in self._drv_badges.items():
            status = driver_status.get(name, "fake")
            is_real = status == "real"
            if is_real:
                bg, fg, border = C.SUCCESS_BG, C.SUCCESS, C.SUCCESS
            else:
                bg, fg, border = C.BG_CARD_ALT, C.TEXT_MUTED, C.TEXT_MUTED
            badge_lbl.setStyleSheet(
                f"background-color: {bg}; color: {fg};"
                f"border: 1px solid {border}; border-radius: 4px;"
                f"padding: 2px 8px; font-size: {F.TINY}px; font-weight: bold;"
            )

        # ── Cloud info ──
        is_paired = getattr(self.app.cloud, "is_paired", False)

        if is_paired:
            self._cloud_dot.setStyleSheet(
                f"background-color: {C.SUCCESS};"
                f"border-radius: 5px; border: none;"
            )
            self._lbl_cloud_status.setText("CONNECTED")
            self._lbl_cloud_status.setStyleSheet(
                f"color: {C.SUCCESS}; font-weight: bold;"
                f"font-size: {F.BODY}px;"
            )
        else:
            self._cloud_dot.setStyleSheet(
                f"background-color: {C.DANGER};"
                f"border-radius: 5px; border: none;"
            )
            self._lbl_cloud_status.setText("NOT PAIRED")
            self._lbl_cloud_status.setStyleSheet(
                f"color: {C.DANGER}; font-weight: bold;"
                f"font-size: {F.BODY}px;"
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
        if unsynced > 10:
            self._lbl_events.setText(
                f"{total} total, {unsynced} pending"
            )
            self._lbl_events.setStyleSheet(
                f"color: {C.WARNING}; font-size: {F.BODY}px;"
            )
        else:
            self._lbl_events.setText(
                f"{total} total, {unsynced} pending"
            )
            self._lbl_events.setStyleSheet(
                f"color: {C.TEXT}; font-size: {F.BODY}px;"
            )

        # Button states
        self._btn_sync.setEnabled(is_paired)
        self._btn_flush.setEnabled(is_paired and unsynced > 0)
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

    def _on_view_queue(self):
        """Show a dialog with details of all pending sync events."""
        db = getattr(self.app, "db", None)
        if not db:
            return

        try:
            events = db.get_unsynced_events(limit=100)
        except Exception as e:
            events = []
            logger.error(f"Failed to get unsynced events: {e}")

        # Build summary text
        if not events:
            summary = "No pending events in sync queue."
        else:
            # Group by event_type
            type_counts = {}
            for ev in events:
                et = ev.get("event_type", "unknown")
                retries = ev.get("sync_retries", 0) or 0
                if et not in type_counts:
                    type_counts[et] = {"count": 0, "max_retries": 0}
                type_counts[et]["count"] += 1
                type_counts[et]["max_retries"] = max(
                    type_counts[et]["max_retries"], retries
                )

            lines = [f"PENDING EVENTS: {len(events)}\n"]
            lines.append(
                f"{'TYPE':<30} {'COUNT':>5}  {'MAX RETRIES':>11}"
            )
            lines.append("-" * 50)
            for et, info in sorted(
                type_counts.items(), key=lambda x: -x[1]["count"]
            ):
                lines.append(
                    f"{et:<30} {info['count']:>5}"
                    f"  {info['max_retries']:>11}"
                )

            lines.append("\n\nLAST 10 EVENTS (newest first):")
            lines.append("-" * 70)
            import time as _time
            for ev in reversed(events[-10:]):
                ts = ev.get("timestamp", 0)
                try:
                    ts_str = _time.strftime(
                        "%Y-%m-%d %H:%M:%S", _time.localtime(ts)
                    )
                except Exception:
                    ts_str = str(ts)
                et = ev.get("event_type", "?")
                eid = ev.get("event_id", "?")[:12]
                retries = ev.get("sync_retries", 0) or 0
                tag = ev.get("tag_id", "") or ""
                slot = ev.get("slot_id", "") or ""
                lines.append(
                    f"{ts_str}  {et:<25} retries={retries}"
                    f"  tag={tag}  slot={slot}"
                )

            summary = "\n".join(lines)

        # Show in dialog
        dlg = QDialog(self)
        dlg.setWindowTitle("Sync Queue")
        dlg.setMinimumSize(600, 400)
        dlg.setStyleSheet(
            f"background-color: {C.BG_DARK}; color: {C.TEXT};"
        )
        layout = QVBoxLayout(dlg)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setFont(QFont("Courier", 10))
        text.setStyleSheet(
            f"background-color: {C.BG_CARD}; color: {C.TEXT}; "
            f"border: 1px solid {C.BORDER}; padding: 8px;"
        )
        text.setPlainText(summary)
        layout.addWidget(text)

        btn_close = QPushButton("CLOSE")
        btn_close.setObjectName("secondary")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(dlg.accept)
        layout.addWidget(btn_close)

        dlg.exec()

    def _on_flush_queue(self):
        """Force-mark all pending events as synced to clear the queue."""
        db = getattr(self.app, "db", None)
        if db:
            try:
                count = db.get_event_count(synced=False)
                if count == 0:
                    logger.info("No pending events to flush")
                    return
                # Force mark ALL unsynced as synced
                db.conn.execute(
                    "UPDATE event_log SET synced = 1 WHERE synced = 0"
                )
                db.conn.commit()
                # Also flush mixing sessions
                try:
                    db.conn.execute(
                        "UPDATE mixing_session SET synced = 1"
                        " WHERE synced = 0"
                    )
                    db.conn.commit()
                except Exception:
                    pass
                logger.warning(
                    f"FLUSH: Force-cleared {count} pending events from queue"
                )
            except Exception as e:
                logger.error(f"Flush queue failed: {e}")
        QTimer.singleShot(1000, self._refresh_info)

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
    def _make_card(accent_color: str = C.BORDER) -> QFrame:
        """Create a styled card frame with left accent border."""
        card = QFrame()
        card.setObjectName("card")
        card.setProperty("card", True)
        card.setStyleSheet(
            f"QFrame#card {{"
            f"  background-color: {C.BG_CARD};"
            f"  border: 1px solid {C.BORDER};"
            f"  border-left: 4px solid {accent_color};"
            f"  border-radius: {S.RADIUS}px;"
            f"  padding: {S.PAD_CARD}px;"
            f"}}"
        )
        return card

    @staticmethod
    def _muted_label(text: str) -> QLabel:
        """Create a muted-color label for field names."""
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-size: {F.SMALL}px;"
        )
        lbl.setFixedWidth(90)
        return lbl

    @staticmethod
    def _system_button(glyph: str, text: str, color: str,
                       style_name: str) -> QPushButton:
        """Create a system action button with icon text."""
        btn = QPushButton(f"{glyph}  {text}")
        btn.setObjectName(style_name)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumHeight(44)
        return btn

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
