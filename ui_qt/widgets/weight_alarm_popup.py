"""
Weight Alarm Popup -- Shown when RFID is down and shelf weight changes.

Requires the user to scan the barcode of the product within 30 seconds.
Shows a visual alarm + countdown ring. If no scan, closes automatically
and logs an unauthorized removal event.
"""

import math
import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QWidget, QGraphicsOpacityEffect,
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve

from ui_qt.theme import C, F, S
from ui_qt.icons import Icon, icon_badge, icon_label, type_badge
from ui_qt.animations import ProgressRing

logger = logging.getLogger("smartlocker.weight_alarm")

ALARM_TIMEOUT_S = 30

# Dark red background for alarm state
_BG_ALARM = "#1A0505"
_BG_ALARM_RESOLVED = "#051A0A"
_BORDER_ALARM = "#4D1117"
_BORDER_ALARM_DIM = "#3A0C11"


class WeightAlarmPopup(QDialog):
    """Alarm popup when shelf weight changes without RFID."""

    def __init__(self, alarm_data: dict, parent=None):
        super().__init__(parent)
        self.alarm_data = alarm_data
        self._remaining_s = ALARM_TIMEOUT_S
        self._resolved = False

        action = alarm_data.get("action", "removed")
        self._is_removal = (action == "removed")

        self.setWindowTitle("WEIGHT ALARM")
        self.setFixedSize(620, 420)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self._border_opacity = 1.0
        self._border_phase = 0.0
        self._apply_border_style(1.0)

        self._build_ui()

        # Countdown timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

        # Gentle border pulse timer (~30fps)
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._pulse_border)
        self._pulse_timer.start(33)

    # ──────────────────────────────────────────────
    # BUILD UI
    # ──────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(S.PAD)
        layout.setContentsMargins(30, 20, 30, 20)

        # ── Alarm icon (centered) ──
        icon_row = QHBoxLayout()
        icon_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        alarm_icon = icon_badge(
            Icon.WARN, bg_color=C.DANGER_BG, fg_color=C.DANGER, size=48
        )
        icon_row.addWidget(alarm_icon)
        layout.addLayout(icon_row)

        # ── Title ──
        self._title = QLabel("RFID OFFLINE")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setStyleSheet(
            f"font-size: {F.H2}px; font-weight: bold; color: {C.DANGER};"
        )
        layout.addWidget(self._title)

        # ── Subtitle ──
        self._subtitle = QLabel("Product removed/placed without identification")
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle.setStyleSheet(
            f"font-size: {F.BODY}px; color: {C.TEXT_SEC};"
        )
        layout.addWidget(self._subtitle)

        # ── Weight change ──
        diff_g = self.alarm_data.get("weight_diff_g", 0)
        action_word = "removed" if self._is_removal else "placed"
        direction = "-" if self._is_removal else "+"
        weight_text = f"{direction}{diff_g / 1000:.2f} kg {action_word}"
        self._weight_lbl = QLabel(weight_text)
        self._weight_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._weight_lbl.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.ACCENT};"
        )
        layout.addWidget(self._weight_lbl)

        # ── Separator ──
        sep = QFrame()
        sep.setFixedHeight(2)
        sep.setStyleSheet(f"background: {C.DANGER}; border: none;")
        layout.addWidget(sep)

        # ── Instruction ──
        self._instr = QLabel("SCAN THE BARCODE NOW")
        self._instr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._instr.setWordWrap(True)
        self._instr.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.TEXT};"
            f"padding: 4px 0px;"
        )
        layout.addWidget(self._instr)

        # ── Countdown ring + status (centered) ──
        ring_row = QHBoxLayout()
        ring_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ring_row.setSpacing(16)

        # Progress ring with seconds overlay
        ring_container = QWidget()
        ring_container.setFixedSize(80, 80)
        ring_container.setStyleSheet("background: transparent; border: none;")

        self._ring = ProgressRing(size=80, thickness=6, parent=ring_container)
        self._ring.set_color(C.DANGER)
        self._ring.set_value(1.0)
        self._ring._show_text = False  # We draw our own text

        # Seconds label overlaid on ring
        self._seconds_lbl = QLabel(str(self._remaining_s), ring_container)
        self._seconds_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._seconds_lbl.setGeometry(0, 0, 80, 80)
        self._seconds_lbl.setStyleSheet(
            f"font-size: {F.H2}px; font-weight: bold; color: {C.DANGER};"
            f"background: transparent; border: none;"
        )

        ring_row.addWidget(ring_container)

        # Status text next to ring
        status_col = QVBoxLayout()
        status_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._status_label = QLabel("Waiting for barcode scan...")
        self._status_label.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.TEXT_MUTED};"
        )
        status_col.addWidget(self._status_label)
        ring_row.addLayout(status_col)

        layout.addLayout(ring_row)

        layout.addStretch()

        # ── SKIP button ──
        btn_skip = QPushButton(f"SKIP  {Icon.FORWARD}")
        btn_skip.setObjectName("danger")
        btn_skip.setMinimumHeight(44)
        btn_skip.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_skip.clicked.connect(self._on_skip)
        layout.addWidget(btn_skip)

    # ──────────────────────────────────────────────
    # BORDER PULSE
    # ──────────────────────────────────────────────

    def _apply_border_style(self, opacity: float):
        """Apply dialog style with border at given opacity."""
        # Interpolate border color between dim and bright
        alpha = int(opacity * 255)
        self.setStyleSheet(
            f"QDialog {{"
            f"  background-color: {_BG_ALARM};"
            f"  color: {C.TEXT};"
            f"  border: 2px solid rgba(237, 68, 82, {alpha});"
            f"  border-radius: {S.RADIUS}px;"
            f"}}"
        )

    def _pulse_border(self):
        """Gentle opacity pulse on border only (0.85 to 1.0)."""
        self._border_phase += 0.06
        # Oscillate between 0.85 and 1.0
        opacity = 0.85 + 0.15 * (0.5 + 0.5 * math.sin(self._border_phase))
        self._apply_border_style(opacity)

    # ──────────────────────────────────────────────
    # COUNTDOWN
    # ──────────────────────────────────────────────

    def _tick(self):
        """Countdown tick -- every second."""
        self._remaining_s -= 1
        self._seconds_lbl.setText(str(max(0, self._remaining_s)))

        # Update ring progress (1.0 -> 0.0 as time runs out)
        progress = max(0.0, self._remaining_s / ALARM_TIMEOUT_S)
        self._ring.set_value(progress)

        # Urgency color shift in final 10 seconds
        if self._remaining_s <= 10:
            self._seconds_lbl.setStyleSheet(
                f"font-size: {F.H2}px; font-weight: bold; color: #FF2222;"
                f"background: transparent; border: none;"
            )

        if self._remaining_s <= 0:
            self._timer.stop()
            self._pulse_timer.stop()
            if not self._resolved:
                self.reject()  # Timeout -- no barcode scanned

    # ──────────────────────────────────────────────
    # BARCODE RESOLUTION
    # ──────────────────────────────────────────────

    def on_barcode_resolved(self, product_info: dict):
        """Called by app when barcode is scanned successfully during alarm."""
        self._resolved = True
        self._timer.stop()
        self._pulse_timer.stop()

        name = product_info.get("product_name", "Unknown")

        # Switch to resolved (green) state
        self.setStyleSheet(
            f"QDialog {{"
            f"  background-color: {_BG_ALARM_RESOLVED};"
            f"  color: {C.TEXT};"
            f"  border: 2px solid {C.SUCCESS};"
            f"  border-radius: {S.RADIUS}px;"
            f"}}"
        )

        self._title.setText("PRODUCT IDENTIFIED")
        self._title.setStyleSheet(
            f"font-size: {F.H2}px; font-weight: bold; color: {C.SUCCESS};"
        )

        self._subtitle.setText(name)
        self._subtitle.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.TEXT};"
        )

        self._instr.setText("Inventory updated successfully")
        self._instr.setStyleSheet(
            f"font-size: {F.BODY}px; color: {C.SUCCESS}; padding: 4px 0px;"
        )

        self._ring.set_color(C.SUCCESS)
        self._ring.set_value(1.0)
        self._seconds_lbl.setText(Icon.OK)
        self._seconds_lbl.setStyleSheet(
            f"font-size: {F.H1}px; font-weight: bold; color: {C.SUCCESS};"
            f"background: transparent; border: none;"
        )

        self._status_label.setText("Closing automatically...")
        self._status_label.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.SUCCESS};"
        )

        # Auto-close after 2 seconds
        QTimer.singleShot(2000, self.accept)

    # ──────────────────────────────────────────────
    # ACTIONS
    # ──────────────────────────────────────────────

    def _on_skip(self):
        """User explicitly skips -- treat as unauthorized."""
        self._timer.stop()
        self._pulse_timer.stop()
        self.reject()

    def closeEvent(self, event):
        self._timer.stop()
        self._pulse_timer.stop()
        event.accept()
