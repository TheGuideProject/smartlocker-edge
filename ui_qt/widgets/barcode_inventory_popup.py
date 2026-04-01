"""
Barcode Inventory Popup -- Load/Unload confirmation dialog.

Shown when a barcode is scanned outside of mixing mode.
Asks the user to confirm if they are loading or unloading a product,
and verifies with shelf weight sensors.
"""

import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy, QWidget,
)
from PyQt6.QtCore import Qt, QTimer

from ui_qt.theme import C, F, S
from ui_qt.icons import Icon, icon_badge, icon_label, type_badge

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
        self.setFixedSize(520, 400)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
        )
        self.setStyleSheet(
            f"QDialog {{"
            f"  background-color: {C.BG_DARK};"
            f"  color: {C.TEXT};"
            f"  border: 1px solid {C.BORDER};"
            f"  border-radius: {S.RADIUS}px;"
            f"}}"
        )

        self._weight_timer = QTimer(self)
        self._weight_timer.timeout.connect(self._check_weight)

        self._build_ui()

    # ──────────────────────────────────────────────
    # BUILD UI
    # ──────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(S.PAD)
        layout.setContentsMargins(20, 16, 20, 16)

        # ── Title row: icon badge + text ──
        title_row = QHBoxLayout()
        title_row.setSpacing(S.GAP)
        title_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        badge = icon_badge(Icon.TAG, bg_color=C.PRIMARY_BG, fg_color=C.PRIMARY, size=36)
        title_row.addWidget(badge)

        title = QLabel("BARCODE SCANNED")
        title.setStyleSheet(
            f"font-size: {F.H2}px; font-weight: bold; color: {C.PRIMARY};"
            f"letter-spacing: 1px;"
        )
        title_row.addWidget(title)

        layout.addLayout(title_row)

        # ── Product info card ──
        card = QFrame()
        card.setObjectName("product_card")
        card.setStyleSheet(
            f"QFrame#product_card {{"
            f"  background-color: {C.BG_CARD};"
            f"  border: 1px solid {C.BORDER};"
            f"  border-left: 4px solid {C.PRIMARY};"
            f"  border-radius: {S.RADIUS}px;"
            f"  padding: {S.PAD_CARD}px;"
            f"}}"
        )
        card_lay = QVBoxLayout(card)
        card_lay.setSpacing(6)
        card_lay.setContentsMargins(S.PAD, S.PAD_CARD, S.PAD_CARD, S.PAD_CARD)

        name = self.product_info.get("product_name", "Unknown")
        ppg = self.product_info.get("ppg_code", "")
        ptype = self.product_info.get("product_type", "")
        color = self.product_info.get("color", "")
        batch = self.product_info.get("batch_number", "")

        # Product name + type badge row
        name_row = QHBoxLayout()
        name_row.setSpacing(S.GAP)

        lbl_name = QLabel(name)
        lbl_name.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.TEXT};"
        )
        name_row.addWidget(lbl_name)

        if ptype:
            badge_variant = "accent"
            if "base" in ptype.lower():
                badge_variant = "primary"
            elif "hardener" in ptype.lower():
                badge_variant = "secondary"
            elif "thinner" in ptype.lower():
                badge_variant = "warning"
            tb = type_badge(ptype.replace("_", " ").upper(), badge_variant)
            name_row.addWidget(tb)

        name_row.addStretch()
        card_lay.addLayout(name_row)

        # Detail lines: muted label + value
        details = []
        if ppg:
            details.append(("PPG CODE", ppg))
        if batch:
            details.append(("BATCH", batch))
        if color:
            details.append(("COLOR", color))

        for label_text, value_text in details:
            row = QHBoxLayout()
            row.setSpacing(6)

            lbl = QLabel(label_text)
            lbl.setStyleSheet(
                f"font-size: {F.TINY}px; color: {C.TEXT_MUTED};"
                f"font-weight: bold; letter-spacing: 1px;"
            )
            lbl.setFixedWidth(80)
            row.addWidget(lbl)

            val = QLabel(value_text)
            val.setStyleSheet(
                f"font-size: {F.SMALL}px; color: {C.TEXT_SEC};"
            )
            row.addWidget(val)
            row.addStretch()
            card_lay.addLayout(row)

        layout.addWidget(card)

        # ── Weight display (hidden until action selected) ──
        self._weight_label = QLabel("")
        self._weight_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._weight_label.setStyleSheet(
            f"font-size: {F.H1}px; font-weight: bold; color: {C.PRIMARY};"
        )
        self._weight_label.setVisible(False)
        layout.addWidget(self._weight_label)

        # ── Status text ──
        self._status_label = QLabel("What do you want to do?")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet(
            f"font-size: {F.BODY}px; color: {C.TEXT_SEC}; padding: 4px;"
        )
        layout.addWidget(self._status_label)

        # ── Action buttons: LOAD / UNLOAD ──
        self._btn_container = QFrame()
        self._btn_container.setStyleSheet("background: transparent; border: none;")
        btn_lay = QHBoxLayout(self._btn_container)
        btn_lay.setSpacing(S.PAD)

        # LOAD button
        self._btn_load = QPushButton()
        self._btn_load.setObjectName("success")
        self._btn_load.setMinimumHeight(60)
        self._btn_load.setCursor(Qt.CursorShape.PointingHandCursor)
        load_lay = QHBoxLayout(self._btn_load)
        load_lay.setContentsMargins(0, 0, 0, 0)
        load_lay.setSpacing(6)
        load_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        load_icon = QLabel(Icon.ADD)
        load_icon.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.SUCCESS};"
        )
        load_lay.addWidget(load_icon)
        load_text = QLabel("LOAD")
        load_text.setStyleSheet(
            f"font-size: {F.BODY}px; font-weight: bold; color: {C.SUCCESS};"
        )
        load_lay.addWidget(load_text)
        self._btn_load.clicked.connect(lambda: self._on_action("load"))
        btn_lay.addWidget(self._btn_load)

        # UNLOAD button
        self._btn_unload = QPushButton()
        self._btn_unload.setObjectName("accent")
        self._btn_unload.setMinimumHeight(60)
        self._btn_unload.setCursor(Qt.CursorShape.PointingHandCursor)
        unload_lay = QHBoxLayout(self._btn_unload)
        unload_lay.setContentsMargins(0, 0, 0, 0)
        unload_lay.setSpacing(6)
        unload_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        unload_icon = QLabel(Icon.DELETE)
        unload_icon.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.ACCENT};"
        )
        unload_lay.addWidget(unload_icon)
        unload_text = QLabel("UNLOAD")
        unload_text.setStyleSheet(
            f"font-size: {F.BODY}px; font-weight: bold; color: {C.ACCENT};"
        )
        unload_lay.addWidget(unload_text)
        self._btn_unload.clicked.connect(lambda: self._on_action("unload"))
        btn_lay.addWidget(self._btn_unload)

        layout.addWidget(self._btn_container)

        # ── Confirm/Cancel (hidden until weight verified) ──
        self._confirm_container = QFrame()
        self._confirm_container.setStyleSheet("background: transparent; border: none;")
        self._confirm_container.setVisible(False)
        confirm_lay = QVBoxLayout(self._confirm_container)
        confirm_lay.setSpacing(S.GAP)

        # CONFIRM (full width)
        self._btn_confirm = QPushButton(f"{Icon.SAVE}  CONFIRM")
        self._btn_confirm.setObjectName("primary")
        self._btn_confirm.setMinimumHeight(S.BTN_H)
        self._btn_confirm.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_confirm.clicked.connect(self._on_confirm)
        self._btn_confirm.setEnabled(False)
        confirm_lay.addWidget(self._btn_confirm)

        # CANCEL (full width, ghost)
        btn_cancel = QPushButton("CANCEL")
        btn_cancel.setObjectName("ghost")
        btn_cancel.setMinimumHeight(40)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet(
            f"QPushButton#ghost {{"
            f"  background: transparent; color: {C.TEXT_SEC};"
            f"  border: none; font-size: {F.SMALL}px;"
            f"}}"
            f"QPushButton#ghost:hover {{ color: {C.TEXT}; }}"
        )
        btn_cancel.clicked.connect(self.reject)
        confirm_lay.addWidget(btn_cancel)

        layout.addWidget(self._confirm_container)

    # ──────────────────────────────────────────────
    # LOGIC
    # ──────────────────────────────────────────────

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
                f"font-size: {F.BODY}px; color: {C.SUCCESS}; padding: 4px;"
            )
        else:
            self._status_label.setText(
                "Remove the can from the shelf now..."
            )
            self._status_label.setStyleSheet(
                f"font-size: {F.BODY}px; color: {C.ACCENT}; padding: 4px;"
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
                self._status_label.setStyleSheet(
                    f"font-size: {F.BODY}px; color: {C.SUCCESS}; padding: 4px;"
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
                    f"font-size: {F.H1}px; font-weight: bold; color: {C.ACCENT};"
                )
                self._status_label.setText(
                    f"Weight decreased {diff / 1000:.2f} kg -- product removed!"
                )
                self._status_label.setStyleSheet(
                    f"font-size: {F.BODY}px; color: {C.ACCENT}; padding: 4px;"
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
