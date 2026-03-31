"""
Weight Alarm Popup — Shown when RFID is down and shelf weight changes.

Requires the user to scan the barcode of the product within 30 seconds.
Shows a loud visual + countdown timer. If no scan, closes automatically
and logs an unauthorized removal event.
"""

import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QFrame,
)
from PyQt6.QtCore import Qt, QTimer

from ui_qt.theme import C, F

logger = logging.getLogger("smartlocker.weight_alarm")

ALARM_TIMEOUT_S = 30


class WeightAlarmPopup(QDialog):
    """Full-screen alarm popup when shelf weight changes without RFID."""

    def __init__(self, alarm_data: dict, parent=None):
        super().__init__(parent)
        self.alarm_data = alarm_data
        self._remaining_s = ALARM_TIMEOUT_S
        self._resolved = False

        action = alarm_data.get("action", "removed")
        self._is_removal = (action == "removed")

        self.setWindowTitle("WEIGHT ALARM")
        self.setMinimumSize(600, 400)
        self.setStyleSheet(f"background-color: #1a0000; color: {C.TEXT};")
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        self._build_ui()

        # Countdown timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

        # Flash timer (red pulse effect)
        self._flash_on = True
        self._flash_timer = QTimer(self)
        self._flash_timer.timeout.connect(self._flash)
        self._flash_timer.start(500)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(30, 24, 30, 24)

        # ALARM ICON
        icon = QLabel("!!")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            f"font-size: 64px; font-weight: bold; color: #FF2222;"
            f"background: transparent;"
        )
        layout.addWidget(icon)

        # TITLE
        action_text = "PRODUCT REMOVED" if self._is_removal else "PRODUCT PLACED"
        self._title = QLabel(f"RFID OFFLINE - {action_text}")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setStyleSheet(
            f"font-size: {F.H1}px; font-weight: bold; color: #FF2222;"
            f"background: transparent;"
        )
        layout.addWidget(self._title)

        # Weight info
        diff_g = self.alarm_data.get("weight_diff_g", 0)
        direction = "-" if self._is_removal else "+"
        weight_lbl = QLabel(f"Weight change: {direction}{diff_g / 1000:.2f} kg")
        weight_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        weight_lbl.setStyleSheet(
            f"font-size: {F.H2}px; color: {C.WARNING}; background: transparent;"
        )
        layout.addWidget(weight_lbl)

        # Separator
        sep = QFrame()
        sep.setFixedHeight(2)
        sep.setStyleSheet("background: #FF2222;")
        layout.addWidget(sep)

        # INSTRUCTION
        instr = QLabel("SCAN THE BARCODE OF THE PRODUCT NOW")
        instr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instr.setWordWrap(True)
        instr.setStyleSheet(
            f"font-size: {F.H2}px; font-weight: bold; color: {C.TEXT};"
            f"background: transparent; padding: 12px;"
        )
        layout.addWidget(instr)

        # COUNTDOWN
        self._countdown_label = QLabel(f"{self._remaining_s}s")
        self._countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._countdown_label.setStyleSheet(
            f"font-size: 72px; font-weight: bold; color: #FF2222;"
            f"background: transparent;"
        )
        layout.addWidget(self._countdown_label)

        # Status (changes when barcode scanned)
        self._status_label = QLabel("Waiting for barcode scan...")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet(
            f"font-size: {F.BODY}px; color: {C.TEXT_SEC}; background: transparent;"
        )
        layout.addWidget(self._status_label)

        # CANCEL button (skip / ignore)
        btn_skip = QPushButton("SKIP (UNAUTHORIZED)")
        btn_skip.setMinimumHeight(50)
        btn_skip.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_skip.setStyleSheet(
            f"background-color: #331111; color: #FF4444;"
            f"border: 1px solid #FF4444; border-radius: 8px;"
            f"font-size: {F.SMALL}px;"
        )
        btn_skip.clicked.connect(self._on_skip)
        layout.addWidget(btn_skip)

    def _tick(self):
        """Countdown tick — every second."""
        self._remaining_s -= 1
        self._countdown_label.setText(f"{self._remaining_s}s")

        if self._remaining_s <= 10:
            self._countdown_label.setStyleSheet(
                f"font-size: 72px; font-weight: bold; color: #FF0000;"
                f"background: transparent;"
            )

        if self._remaining_s <= 0:
            self._timer.stop()
            self._flash_timer.stop()
            if not self._resolved:
                self.reject()  # Timeout — no barcode scanned

    def _flash(self):
        """Alternating red flash effect."""
        self._flash_on = not self._flash_on
        if self._flash_on:
            self.setStyleSheet(f"background-color: #1a0000; color: {C.TEXT};")
        else:
            self.setStyleSheet(f"background-color: #330000; color: {C.TEXT};")

    def on_barcode_resolved(self, product_info: dict):
        """Called by app when barcode is scanned successfully during alarm."""
        self._resolved = True
        self._timer.stop()
        self._flash_timer.stop()

        name = product_info.get("product_name", "Unknown")
        self.setStyleSheet(f"background-color: #001a00; color: {C.TEXT};")
        self._title.setText("PRODUCT IDENTIFIED")
        self._title.setStyleSheet(
            f"font-size: {F.H1}px; font-weight: bold; color: #33D17A;"
            f"background: transparent;"
        )
        self._countdown_label.setText(name)
        self._countdown_label.setStyleSheet(
            f"font-size: {F.H1}px; font-weight: bold; color: {C.TEXT};"
            f"background: transparent;"
        )
        self._status_label.setText("Inventory updated successfully")
        self._status_label.setStyleSheet(
            f"font-size: {F.BODY}px; color: #33D17A; background: transparent;"
        )

        # Auto-close after 2 seconds
        QTimer.singleShot(2000, self.accept)

    def _on_skip(self):
        """User explicitly skips — treat as unauthorized."""
        self._timer.stop()
        self._flash_timer.stop()
        self.reject()

    def closeEvent(self, event):
        self._timer.stop()
        self._flash_timer.stop()
        event.accept()
