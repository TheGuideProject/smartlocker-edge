"""
Barcode Inventory Popup — Load/Unload confirmation dialog.

Shown when a barcode is scanned outside of mixing mode.
Asks the user to confirm if they are loading or unloading a product,
and verifies with shelf weight sensors.
"""

import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer

from ui_qt.theme import C, F, S

logger = logging.getLogger("smartlocker.barcode_popup")


class BarcodeInventoryPopup(QDialog):
    """Popup shown when barcode is scanned outside mixing mode.

    Shows product info and asks: LOAD (put on shelf) or UNLOAD (take from shelf).
    Monitors weight change to confirm the action.
    """

    def __init__(self, app, product_info: dict, parent=None):
        super().__init__(parent)
        self.app = app
        self.product_info = product_info
        self._action = None  # "load" or "unload"
        self._initial_weight = None
        self._final_weight = None
        self._weight_diff = 0.0
        self._confirmed = False

        self.setWindowTitle("Barcode Scan")
        self.setFixedSize(500, 380)
        self.setStyleSheet(f"background-color: {C.BG_DARK}; color: {C.TEXT};")

        self._weight_timer = QTimer(self)
        self._weight_timer.timeout.connect(self._check_weight)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        # Title
        title = QLabel("BARCODE SCANNED")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.PRIMARY};"
        )
        layout.addWidget(title)

        # Product info card
        card = QFrame()
        card.setObjectName("card")
        card_lay = QVBoxLayout(card)
        card_lay.setSpacing(6)

        name = self.product_info.get("product_name", "Unknown")
        ppg = self.product_info.get("ppg_code", "")
        ptype = self.product_info.get("product_type", "")
        color = self.product_info.get("color", "")
        batch = self.product_info.get("batch_number", "")

        lbl_name = QLabel(name)
        lbl_name.setStyleSheet(
            f"font-size: {F.H2}px; font-weight: bold; color: {C.TEXT};"
        )
        lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(lbl_name)

        details = []
        if ppg:
            details.append(f"PPG: {ppg}")
        if ptype:
            details.append(ptype.replace("_", " ").title())
        if color:
            details.append(f"Color: {color}")
        if batch:
            details.append(f"Batch: {batch}")

        if details:
            lbl_details = QLabel("  |  ".join(details))
            lbl_details.setStyleSheet(
                f"font-size: {F.SMALL}px; color: {C.TEXT_SEC};"
            )
            lbl_details.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_lay.addWidget(lbl_details)

        layout.addWidget(card)

        # Status / weight label
        self._status_label = QLabel("What do you want to do?")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet(
            f"font-size: {F.BODY}px; color: {C.TEXT_SEC}; padding: 8px;"
        )
        layout.addWidget(self._status_label)

        # Weight display (hidden until action selected)
        self._weight_label = QLabel("")
        self._weight_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._weight_label.setStyleSheet(
            f"font-size: {F.H1}px; font-weight: bold; color: {C.PRIMARY};"
        )
        self._weight_label.setVisible(False)
        layout.addWidget(self._weight_label)

        # Buttons
        self._btn_container = QFrame()
        self._btn_container.setStyleSheet("background: transparent; border: none;")
        btn_lay = QHBoxLayout(self._btn_container)
        btn_lay.setSpacing(12)

        # LOAD button (green)
        self._btn_load = QPushButton("LOAD\n(Put on shelf)")
        self._btn_load.setObjectName("success")
        self._btn_load.setMinimumHeight(70)
        self._btn_load.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_load.setStyleSheet(
            f"background-color: {C.SUCCESS_BG}; color: {C.SUCCESS};"
            f"border: 2px solid {C.SUCCESS}; border-radius: 10px;"
            f"font-size: {F.BODY}px; font-weight: bold;"
        )
        self._btn_load.clicked.connect(lambda: self._on_action("load"))
        btn_lay.addWidget(self._btn_load)

        # UNLOAD button (orange)
        self._btn_unload = QPushButton("UNLOAD\n(Take from shelf)")
        self._btn_unload.setMinimumHeight(70)
        self._btn_unload.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_unload.setStyleSheet(
            f"background-color: {C.WARNING_BG}; color: {C.WARNING};"
            f"border: 2px solid {C.WARNING}; border-radius: 10px;"
            f"font-size: {F.BODY}px; font-weight: bold;"
        )
        self._btn_unload.clicked.connect(lambda: self._on_action("unload"))
        btn_lay.addWidget(self._btn_unload)

        layout.addWidget(self._btn_container)

        # Confirm/Cancel after weight verification
        self._confirm_container = QFrame()
        self._confirm_container.setStyleSheet("background: transparent; border: none;")
        self._confirm_container.setVisible(False)
        confirm_lay = QHBoxLayout(self._confirm_container)
        confirm_lay.setSpacing(12)

        self._btn_confirm = QPushButton("CONFIRM")
        self._btn_confirm.setMinimumHeight(56)
        self._btn_confirm.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_confirm.setStyleSheet(
            f"background-color: {C.PRIMARY}; color: {C.BG_DARK};"
            f"border: none; border-radius: 10px;"
            f"font-size: {F.BODY}px; font-weight: bold;"
        )
        self._btn_confirm.clicked.connect(self._on_confirm)
        self._btn_confirm.setEnabled(False)
        confirm_lay.addWidget(self._btn_confirm)

        btn_cancel = QPushButton("CANCEL")
        btn_cancel.setObjectName("danger")
        btn_cancel.setMinimumHeight(56)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        confirm_lay.addWidget(btn_cancel)

        layout.addWidget(self._confirm_container)

    def _on_action(self, action: str):
        """User selected Load or Unload."""
        self._action = action
        self._btn_container.setVisible(False)
        self._confirm_container.setVisible(True)
        self._weight_label.setVisible(True)

        # Read initial shelf weight
        try:
            reading = self.app.weight.read_weight("shelf1")
            self._initial_weight = reading.grams
        except Exception:
            self._initial_weight = 0

        if action == "load":
            self._status_label.setText(
                "Place the can on the shelf now..."
            )
            self._status_label.setStyleSheet(
                f"font-size: {F.BODY}px; color: {C.SUCCESS}; padding: 8px;"
            )
        else:
            self._status_label.setText(
                "Remove the can from the shelf now..."
            )
            self._status_label.setStyleSheet(
                f"font-size: {F.BODY}px; color: {C.WARNING}; padding: 8px;"
            )

        # Start weight monitoring
        self._weight_timer.start(500)

    def _check_weight(self):
        """Monitor shelf weight to detect load/unload."""
        try:
            reading = self.app.weight.read_weight("shelf1")
            current = reading.grams
        except Exception:
            self._weight_label.setText("-- kg")
            return

        if self._initial_weight is None:
            self._initial_weight = current
            return

        diff = current - self._initial_weight
        self._weight_label.setText(f"{current / 1000:.2f} kg")

        self._final_weight = current
        self._weight_diff = diff

        if self._action == "load":
            # Expect weight increase (> 100g = can placed)
            if diff > 100:
                self._weight_label.setStyleSheet(
                    f"font-size: {F.H1}px; font-weight: bold; color: {C.SUCCESS};"
                )
                self._status_label.setText(
                    f"Weight increased +{diff / 1000:.2f} kg -- product detected!"
                )
                self._btn_confirm.setEnabled(True)
                self._confirmed = True
            else:
                self._weight_label.setStyleSheet(
                    f"font-size: {F.H1}px; font-weight: bold; color: {C.PRIMARY};"
                )
                self._btn_confirm.setEnabled(False)
        else:
            # Expect weight decrease (> 100g = can removed)
            if diff < -100:
                self._weight_label.setStyleSheet(
                    f"font-size: {F.H1}px; font-weight: bold; color: {C.WARNING};"
                )
                self._status_label.setText(
                    f"Weight decreased {diff / 1000:.2f} kg -- product removed!"
                )
                self._btn_confirm.setEnabled(True)
                self._confirmed = True
            else:
                self._weight_label.setStyleSheet(
                    f"font-size: {F.H1}px; font-weight: bold; color: {C.PRIMARY};"
                )
                self._btn_confirm.setEnabled(False)

    def _on_confirm(self):
        """User confirmed the action after weight verification."""
        self._weight_timer.stop()
        self.accept()

    def get_result(self) -> dict:
        """Get the result after dialog is accepted."""
        return {
            "action": self._action,
            "product_info": self.product_info,
            "weight_confirmed": self._confirmed,
            "weight_before_g": self._initial_weight or 0,
            "weight_after_g": self._final_weight or 0,
            "weight_diff_g": abs(self._weight_diff),
        }

    def reject(self):
        self._weight_timer.stop()
        super().reject()
