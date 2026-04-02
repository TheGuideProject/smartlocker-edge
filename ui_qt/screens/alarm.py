"""
SmartLocker Alarm Screen

Displays active alarms and alarm history. Allows acknowledging and
resolving alarms. Logs are NEVER deleted — resolved alarms move to
the history section and remain in the database permanently.

Layout:
  - Header with active alarm count badge
  - ACTIVE ALARMS section (red accent) — acknowledge / resolve buttons
  - ALARM HISTORY section (muted accent) — all past alarms, read-only
  - Auto-refresh every 2 seconds
"""

import time
import logging
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QGridLayout, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer

from ui_qt.theme import C, F, S, enable_touch_scroll
from ui_qt.icons import (
    Icon, icon_badge, icon_label, status_dot, type_badge,
    section_header, screen_header,
)

logger = logging.getLogger("smartlocker.ui.alarm")

# Severity → (badge_variant, accent_color)
_SEV = {
    "critical": ("danger", C.DANGER),
    "warning":  ("warning", C.WARNING),
    "info":     ("primary", C.SECONDARY),
}

# Category → glyph
_CAT_ICON = {
    "sensor":    Icon.SENSORS,
    "system":    Icon.HEALTH,
    "software":  Icon.SETTINGS,
    "inventory": Icon.INVENTORY,
    "mixing":    Icon.MIXING,
}


def _ts(epoch) -> str:
    """Format epoch timestamp as readable string."""
    if not epoch:
        return "—"
    try:
        return datetime.fromtimestamp(float(epoch)).strftime("%d/%m %H:%M:%S")
    except (ValueError, TypeError, OSError):
        return "—"


def _ago(epoch) -> str:
    """Format epoch as relative time (e.g. '3m ago')."""
    if not epoch:
        return ""
    try:
        delta = time.time() - float(epoch)
        if delta < 60:
            return f"{int(delta)}s ago"
        if delta < 3600:
            return f"{int(delta // 60)}m ago"
        if delta < 86400:
            return f"{int(delta // 3600)}h ago"
        return f"{int(delta // 86400)}d ago"
    except (ValueError, TypeError):
        return ""


class AlarmScreen(QWidget):
    """Alarm viewer: active alarms + full history. Logs are never deleted."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._active_container = None
        self._history_container = None
        self._count_badge = None
        self._no_active_label = None
        self._no_history_label = None
        self._build_ui()

    # ================================================================
    # UI BUILD
    # ================================================================

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ──
        header_frame, header_layout = screen_header(
            self.app, "ALARMS", Icon.ALARM, C.DANGER
        )
        # Active count badge
        self._count_badge = type_badge("0", "danger")
        header_layout.addWidget(self._count_badge)

        # RESOLVE ALL button in header
        btn_resolve_all = QPushButton(f"{Icon.OK} RESOLVE ALL")
        btn_resolve_all.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_resolve_all.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {C.DANGER}; color: {C.BG_DARK};"
            f"  border: none; border-radius: 6px;"
            f"  font-size: {F.SMALL}px; font-weight: bold;"
            f"  padding: 6px 14px; min-height: 32px;"
            f"}}"
            f"QPushButton:hover {{ background-color: #ff5a6a; }}"
        )
        btn_resolve_all.clicked.connect(self._resolve_all)
        header_layout.addWidget(btn_resolve_all)

        root.addWidget(header_frame)

        # ── Scrollable body ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        body_widget = QWidget()
        body = QVBoxLayout(body_widget)
        body.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
        body.setSpacing(S.GAP + 4)

        # ── ACTIVE ALARMS section ──
        body.addWidget(section_header(Icon.WARN, "ACTIVE ALARMS", C.DANGER))

        self._no_active_label = QLabel("No active alarms")
        self._no_active_label.setStyleSheet(
            f"font-size: {F.BODY}px; color: {C.TEXT_MUTED}; padding: 16px;"
        )
        self._no_active_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.addWidget(self._no_active_label)

        self._active_container = QVBoxLayout()
        self._active_container.setSpacing(S.GAP)
        body.addLayout(self._active_container)

        # ── HISTORY section ──
        body.addWidget(section_header(Icon.INFO, "ALARM HISTORY", C.TEXT_MUTED))

        self._no_history_label = QLabel("No alarm history")
        self._no_history_label.setStyleSheet(
            f"font-size: {F.BODY}px; color: {C.TEXT_MUTED}; padding: 16px;"
        )
        self._no_history_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.addWidget(self._no_history_label)

        self._history_container = QVBoxLayout()
        self._history_container.setSpacing(S.GAP)
        body.addLayout(self._history_container)

        body.addStretch()
        scroll.setWidget(body_widget)
        enable_touch_scroll(scroll)
        root.addWidget(scroll)

    # ================================================================
    # ALARM CARD BUILDERS
    # ================================================================

    def _build_active_card(self, alarm: dict) -> QFrame:
        """Build a card for an active/acknowledged alarm with action buttons."""
        sev = alarm.get("severity", "info")
        variant, accent = _SEV.get(sev, ("primary", C.SECONDARY))
        cat = alarm.get("category", "system")
        glyph = _CAT_ICON.get(cat, Icon.WARN)
        status = alarm.get("status", "active")

        card = QFrame()
        card.setObjectName("alarm_card")
        card.setStyleSheet(
            f"QFrame#alarm_card {{"
            f"  background-color: {C.BG_CARD};"
            f"  border: 1px solid {accent};"
            f"  border-left: 4px solid {accent};"
            f"  border-radius: {S.RADIUS}px;"
            f"  padding: {S.PAD_CARD}px;"
            f"}}"
        )

        outer = QVBoxLayout(card)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(4)

        # Row 1: icon + code + title + severity badge + time
        row1 = QHBoxLayout()
        row1.setSpacing(6)
        row1.addWidget(icon_label(glyph, color=accent, size=18))

        code_lbl = QLabel(alarm.get("error_code", ""))
        code_lbl.setStyleSheet(
            f"font-size: {F.BODY}px; font-weight: bold; color: {accent};"
        )
        row1.addWidget(code_lbl)

        title_lbl = QLabel(alarm.get("error_title", "Unknown"))
        title_lbl.setStyleSheet(
            f"font-size: {F.BODY}px; font-weight: bold; color: {C.TEXT};"
        )
        title_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row1.addWidget(title_lbl, stretch=1)

        row1.addWidget(type_badge(sev.upper(), variant))

        time_lbl = QLabel(_ago(alarm.get("raised_at")))
        time_lbl.setStyleSheet(f"font-size: {F.TINY}px; color: {C.TEXT_MUTED};")
        row1.addWidget(time_lbl)

        outer.addLayout(row1)

        # Row 2: details + source
        details = alarm.get("details", "")
        source = alarm.get("source", "")
        info_parts = []
        if details:
            info_parts.append(details)
        if source:
            info_parts.append(f"[{source}]")
        if info_parts:
            detail_lbl = QLabel(" ".join(info_parts))
            detail_lbl.setStyleSheet(
                f"font-size: {F.SMALL}px; color: {C.TEXT_SEC};"
            )
            detail_lbl.setWordWrap(True)
            outer.addWidget(detail_lbl)

        # Row 3: action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        alarm_id = alarm.get("alarm_id", "")

        if status == "active":
            btn_ack = QPushButton(f"{Icon.OK} ACKNOWLEDGE")
            btn_ack.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_ack.setStyleSheet(self._btn_style(C.WARNING, C.BG_DARK))
            btn_ack.clicked.connect(lambda checked, aid=alarm_id: self._acknowledge(aid))
            btn_row.addWidget(btn_ack)

        btn_resolve = QPushButton(f"{Icon.OK} RESOLVE")
        btn_resolve.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_resolve.setStyleSheet(self._btn_style(C.SUCCESS, C.BG_DARK))
        btn_resolve.clicked.connect(lambda checked, aid=alarm_id: self._resolve(aid))
        btn_row.addWidget(btn_resolve)

        btn_row.addStretch()

        # Status label
        if status == "acknowledged":
            ack_lbl = QLabel(f"Acknowledged {_ts(alarm.get('acknowledged_at'))}")
            ack_lbl.setStyleSheet(f"font-size: {F.TINY}px; color: {C.WARNING};")
            btn_row.addWidget(ack_lbl)

        outer.addLayout(btn_row)

        return card

    def _build_history_card(self, alarm: dict) -> QFrame:
        """Build a compact read-only card for resolved/past alarms."""
        sev = alarm.get("severity", "info")
        variant, accent = _SEV.get(sev, ("primary", C.SECONDARY))
        status = alarm.get("status", "resolved")
        cat = alarm.get("category", "system")
        glyph = _CAT_ICON.get(cat, Icon.INFO)

        # Resolved → muted style, active/ack → normal
        is_resolved = status == "resolved"
        border_color = C.BORDER if is_resolved else accent

        card = QFrame()
        card.setObjectName("hist_card")
        card.setStyleSheet(
            f"QFrame#hist_card {{"
            f"  background-color: {C.BG_CARD};"
            f"  border: 1px solid {border_color};"
            f"  border-left: 3px solid {border_color};"
            f"  border-radius: {S.RADIUS}px;"
            f"  padding: 4px {S.PAD_CARD}px;"
            f"}}"
        )

        row = QHBoxLayout(card)
        row.setContentsMargins(4, 4, 4, 4)
        row.setSpacing(6)

        # Icon
        row.addWidget(icon_label(glyph, color=accent if not is_resolved else C.TEXT_MUTED, size=14))

        # Code
        code_lbl = QLabel(alarm.get("error_code", ""))
        code_lbl.setStyleSheet(
            f"font-size: {F.SMALL}px; font-weight: bold;"
            f"color: {accent if not is_resolved else C.TEXT_MUTED};"
        )
        row.addWidget(code_lbl)

        # Title
        title_lbl = QLabel(alarm.get("error_title", ""))
        title_lbl.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.TEXT_SEC if is_resolved else C.TEXT};"
        )
        title_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row.addWidget(title_lbl, stretch=1)

        # Status badge
        if is_resolved:
            row.addWidget(type_badge("RESOLVED", "success"))
        elif status == "acknowledged":
            row.addWidget(type_badge("ACK", "warning"))
        else:
            row.addWidget(type_badge("ACTIVE", "danger"))

        # Time
        time_lbl = QLabel(_ts(alarm.get("raised_at")))
        time_lbl.setStyleSheet(f"font-size: {F.TINY}px; color: {C.TEXT_MUTED};")
        row.addWidget(time_lbl)

        return card

    # ================================================================
    # ACTIONS
    # ================================================================

    def _acknowledge(self, alarm_id: str):
        """Acknowledge an alarm (status: active → acknowledged). Log remains."""
        if hasattr(self.app, 'alarm_manager'):
            self.app.alarm_manager.acknowledge_alarm(alarm_id)
            logger.info(f"Alarm acknowledged: {alarm_id[:8]}...")
        self._refresh()

    def _resolve(self, alarm_id: str):
        """Resolve an alarm (status → resolved). Log remains in DB permanently."""
        if hasattr(self.app, 'alarm_manager'):
            self.app.alarm_manager.resolve_alarm(alarm_id)
            logger.info(f"Alarm resolved: {alarm_id[:8]}...")
        self._refresh()

    def _resolve_all(self):
        """Resolve all active alarms at once. Logs remain in DB permanently."""
        if hasattr(self.app, 'alarm_manager'):
            alarms = self.app.alarm_manager.get_active_alarms()
            for a in alarms:
                self.app.alarm_manager.resolve_alarm(a["alarm_id"])
            logger.info(f"Resolved all {len(alarms)} active alarms")
        self._refresh()

    # ================================================================
    # DATA REFRESH
    # ================================================================

    def _refresh(self):
        """Reload active alarms and history from alarm_manager + DB."""
        # --- Active alarms ---
        active = []
        if hasattr(self.app, 'alarm_manager'):
            active = self.app.alarm_manager.get_active_alarms()

        # Clear active container
        self._clear_layout(self._active_container)

        if active:
            self._no_active_label.setVisible(False)
            for a in active:
                self._active_container.addWidget(self._build_active_card(a))
        else:
            self._no_active_label.setVisible(True)

        # Update count badge
        count = len(active)
        if self._count_badge:
            self._count_badge.setText(str(count))

        # --- History (last 30 from DB, includes resolved) ---
        history = []
        if hasattr(self.app, 'db'):
            history = self.app.db.get_alarm_history(30)

        # Filter out currently active (already shown above)
        active_ids = {a["alarm_id"] for a in active}
        history = [h for h in history if h["alarm_id"] not in active_ids]

        self._clear_layout(self._history_container)

        if history:
            self._no_history_label.setVisible(False)
            for h in history:
                self._history_container.addWidget(self._build_history_card(h))
        else:
            self._no_history_label.setVisible(True)

    # ================================================================
    # LIFECYCLE
    # ================================================================

    def on_enter(self):
        """Start refresh timer when screen becomes visible."""
        self._refresh()
        self._timer.start(2000)

    def on_leave(self):
        """Stop refresh timer when leaving screen."""
        self._timer.stop()

    # ================================================================
    # HELPERS
    # ================================================================

    @staticmethod
    def _clear_layout(layout):
        """Remove all widgets from a layout."""
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

    @staticmethod
    def _btn_style(bg: str, fg: str) -> str:
        return (
            f"QPushButton {{"
            f"  background-color: {bg}; color: {fg};"
            f"  border: none; border-radius: 6px;"
            f"  font-size: {F.SMALL}px; font-weight: bold;"
            f"  padding: 6px 14px; min-height: 30px;"
            f"}}"
            f"QPushButton:hover {{ opacity: 0.9; }}"
        )
