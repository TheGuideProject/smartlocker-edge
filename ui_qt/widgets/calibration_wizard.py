"""
Calibration Wizard -- 4-step modal dialog for HX711 scale calibration.

Steps:
1. Remove all weight -> SET ZERO (reads offset)
2. Enter known weight in grams (presets: 500, 1000, 2000, 5000)
3. Place known weight -> READ value
4. Review results -> SAVE or CANCEL
"""

import json
import logging
import time

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QWidget, QLineEdit, QFrame, QGridLayout,
    QProgressBar, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QIntValidator

from ui_qt.theme import C, F, S
from ui_qt.icons import Icon, icon_badge, icon_label, type_badge

logger = logging.getLogger("smartlocker.calibration")


def _reading_card() -> QFrame:
    """Create a styled reading card with left accent border."""
    f = QFrame()
    f.setObjectName("reading_card")
    f.setStyleSheet(
        f"QFrame#reading_card {{"
        f"  background-color: {C.BG_CARD};"
        f"  border: 1px solid {C.BORDER};"
        f"  border-left: 4px solid {C.ACCENT};"
        f"  border-radius: {S.RADIUS}px;"
        f"  padding: {S.PAD}px;"
        f"}}"
    )
    return f


class CalibrationWizard(QDialog):
    """4-step calibration wizard for HX711 weight channels."""

    def __init__(self, app, channel: str, parent=None):
        super().__init__(parent)
        self.app = app
        self.channel = channel
        self.setWindowTitle(f"Calibrate: {channel}")
        self.setFixedSize(720, 420)
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

        # Calibration data
        self._offset = 0
        self._known_grams = 0
        self._loaded_raw = 0
        self._scale = 0.0

        # Live reading timer
        self._live_timer = QTimer()
        self._live_timer.setInterval(300)
        self._live_timer.timeout.connect(self._update_live_reading)

        # Build UI
        self._build_ui()
        self._go_step(0)

    # ══════════════════════════════════════════════════════
    # MAIN LAYOUT
    # ══════════════════════════════════════════════════════

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 14, 20, 14)
        root.setSpacing(S.GAP)

        # ── Title bar: icon + title + step badge ──
        title_row = QHBoxLayout()
        title_row.setSpacing(S.GAP)

        badge = icon_badge(Icon.WEIGHT, bg_color=C.ACCENT_BG, fg_color=C.ACCENT, size=32)
        title_row.addWidget(badge)

        title_lbl = QLabel("CALIBRATION")
        title_lbl.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.ACCENT};"
            f"letter-spacing: 1px;"
        )
        title_row.addWidget(title_lbl)

        title_row.addStretch()

        self._step_badge = type_badge("Step 1/4", "accent")
        title_row.addWidget(self._step_badge)

        root.addLayout(title_row)

        # ── Progress bar (6px, animated) ──
        self._progress = QProgressBar()
        self._progress.setFixedHeight(6)
        self._progress.setRange(0, 100)
        self._progress.setValue(25)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet(
            f"QProgressBar {{"
            f"  background-color: {C.BG_INPUT};"
            f"  border: none;"
            f"  border-radius: 3px;"
            f"}}"
            f"QProgressBar::chunk {{"
            f"  background-color: {C.ACCENT};"
            f"  border-radius: 3px;"
            f"}}"
        )
        root.addWidget(self._progress)

        # ── Stacked pages ──
        self._stack = QStackedWidget()
        root.addWidget(self._stack, stretch=1)

        self._stack.addWidget(self._build_step1())  # 0: Remove weight
        self._stack.addWidget(self._build_step2())  # 1: Enter known weight
        self._stack.addWidget(self._build_step3())  # 2: Place weight
        self._stack.addWidget(self._build_step4())  # 3: Results

    # ══════════════════════════════════════════════════════
    # STEP 1: Remove all weight -> read zero offset
    # ══════════════════════════════════════════════════════

    def _build_step1(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(S.PAD)
        lay.setContentsMargins(0, S.GAP, 0, 0)

        instr = QLabel("Remove all weight from the scale")
        instr.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.TEXT};"
        )
        instr.setWordWrap(True)
        lay.addWidget(instr)

        desc = QLabel("Make sure the scale is completely empty and stable before setting zero.")
        desc.setStyleSheet(f"font-size: {F.BODY}px; color: {C.TEXT_SEC};")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        # Live reading card
        card = _reading_card()
        card_lay = QVBoxLayout(card)
        card_lay.setSpacing(4)

        self._s1_live_grams = QLabel("--- g")
        self._s1_live_grams.setStyleSheet(
            f"font-size: {F.H1}px; font-weight: bold; color: {C.ACCENT};"
        )
        self._s1_live_grams.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(self._s1_live_grams)

        self._s1_live_raw = QLabel("RAW: ---")
        self._s1_live_raw.setStyleSheet(
            f"font-size: {F.TINY}px; color: {C.TEXT_MUTED}; font-family: monospace;"
        )
        self._s1_live_raw.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(self._s1_live_raw)

        # Stability badge row
        stab_row = QHBoxLayout()
        stab_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._s1_stability_badge = type_badge("STABILIZING...", "warning")
        stab_row.addWidget(self._s1_stability_badge)
        card_lay.addLayout(stab_row)

        lay.addWidget(card)
        lay.addStretch()

        # ── Buttons ──
        btn_row = QHBoxLayout()

        cancel = QPushButton("CANCEL")
        cancel.setObjectName("ghost")
        cancel.setMinimumHeight(40)
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        btn_row.addStretch()

        self._s1_set_zero_btn = QPushButton(f"{Icon.SENSORS}  SET ZERO")
        self._s1_set_zero_btn.setObjectName("accent")
        self._s1_set_zero_btn.setMinimumHeight(S.BTN_H)
        self._s1_set_zero_btn.setMinimumWidth(160)
        self._s1_set_zero_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._s1_set_zero_btn.clicked.connect(self._do_set_zero)
        btn_row.addWidget(self._s1_set_zero_btn)

        lay.addLayout(btn_row)
        return page

    def _do_set_zero(self):
        """Read current raw value as zero offset."""
        try:
            reading = self.app.weight.read_weight(self.channel)
            self._offset = reading.raw_value
            logger.info(f"[CAL] Zero offset set: {self._offset} for {self.channel}")

            # Visual feedback: flash card green briefly
            self._s1_live_grams.setStyleSheet(
                f"font-size: {F.H1}px; font-weight: bold; color: {C.SUCCESS};"
            )
            self._s1_set_zero_btn.setEnabled(False)
            QTimer.singleShot(500, lambda: self._go_step(1))
        except Exception as e:
            # Flash card red on error
            self._s1_live_grams.setStyleSheet(
                f"font-size: {F.H1}px; font-weight: bold; color: {C.DANGER};"
            )
            self._s1_live_grams.setText(f"ERROR")
            QTimer.singleShot(2000, lambda: (
                self._s1_live_grams.setStyleSheet(
                    f"font-size: {F.H1}px; font-weight: bold; color: {C.ACCENT};"
                ),
                self._s1_live_grams.setText("--- g"),
            ))

    # ══════════════════════════════════════════════════════
    # STEP 2: Enter known weight
    # ══════════════════════════════════════════════════════

    def _build_step2(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(S.PAD)
        lay.setContentsMargins(0, S.GAP, 0, 0)

        instr = QLabel("Enter the known weight")
        instr.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.TEXT};"
        )
        instr.setWordWrap(True)
        lay.addWidget(instr)

        desc = QLabel("How many grams does your reference weight weigh? Select a preset or enter custom value.")
        desc.setStyleSheet(f"font-size: {F.BODY}px; color: {C.TEXT_SEC};")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        # Preset buttons
        preset_row = QHBoxLayout()
        preset_row.setSpacing(S.GAP)
        self._preset_btns = []
        for grams in [500, 1000, 2000, 5000]:
            b = QPushButton(f"{grams}g")
            b.setMinimumHeight(44)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton {{"
                f"  background: {C.BG_CARD}; color: {C.TEXT};"
                f"  border: 1px solid {C.BORDER}; border-radius: 8px;"
                f"  padding: 8px 14px; font-size: {F.BODY}px; font-weight: bold;"
                f"}}"
                f"QPushButton:hover {{"
                f"  background: {C.BG_HOVER}; border-color: {C.ACCENT};"
                f"}}"
            )
            b.clicked.connect(lambda checked, g=grams, btn=b: self._set_known_weight(g, btn))
            preset_row.addWidget(b)
            self._preset_btns.append(b)
        lay.addLayout(preset_row)

        # Manual input row
        input_row = QHBoxLayout()
        input_row.setSpacing(S.GAP)

        lbl = QLabel("Custom:")
        lbl.setStyleSheet(f"font-size: {F.BODY}px; color: {C.TEXT_SEC};")
        input_row.addWidget(lbl)

        self._s2_input = QLineEdit()
        self._s2_input.setPlaceholderText("Enter grams...")
        self._s2_input.setValidator(QIntValidator(1, 99999))
        self._s2_input.setFixedWidth(160)
        self._s2_input.setStyleSheet(
            f"font-size: {F.BODY}px; padding: 8px 12px; font-weight: bold;"
        )
        input_row.addWidget(self._s2_input)

        g_lbl = QLabel("g")
        g_lbl.setStyleSheet(f"font-size: {F.BODY}px; color: {C.TEXT_SEC};")
        input_row.addWidget(g_lbl)
        input_row.addStretch()
        lay.addLayout(input_row)

        # Selected weight display
        self._s2_selected = QLabel("--- g")
        self._s2_selected.setStyleSheet(
            f"font-size: {F.H1}px; font-weight: bold; color: {C.ACCENT};"
        )
        self._s2_selected.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._s2_selected)

        lay.addStretch()

        # ── Buttons ──
        btn_row = QHBoxLayout()

        back = QPushButton(f"{Icon.BACK}  BACK")
        back.setObjectName("ghost")
        back.setMinimumHeight(40)
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.clicked.connect(lambda: self._go_step(0))
        btn_row.addWidget(back)

        btn_row.addStretch()

        self._s2_next_btn = QPushButton(f"NEXT  {Icon.FORWARD}")
        self._s2_next_btn.setObjectName("accent")
        self._s2_next_btn.setEnabled(False)
        self._s2_next_btn.setMinimumHeight(S.BTN_H)
        self._s2_next_btn.setMinimumWidth(140)
        self._s2_next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._s2_next_btn.clicked.connect(self._confirm_known_weight)
        btn_row.addWidget(self._s2_next_btn)
        lay.addLayout(btn_row)

        # Connect input change
        self._s2_input.textChanged.connect(self._on_input_changed)

        return page

    def _set_known_weight(self, grams: int, clicked_btn=None):
        self._known_grams = grams
        self._s2_input.setText(str(grams))
        self._s2_selected.setText(f"{grams} g")
        self._s2_next_btn.setEnabled(True)

        # Highlight the selected preset, reset others
        for b in self._preset_btns:
            if b is clicked_btn:
                b.setStyleSheet(
                    f"QPushButton {{"
                    f"  background: {C.ACCENT_BG}; color: {C.ACCENT};"
                    f"  border: 2px solid {C.ACCENT}; border-radius: 8px;"
                    f"  padding: 8px 14px; font-size: {F.BODY}px; font-weight: bold;"
                    f"}}"
                )
            else:
                b.setStyleSheet(
                    f"QPushButton {{"
                    f"  background: {C.BG_CARD}; color: {C.TEXT};"
                    f"  border: 1px solid {C.BORDER}; border-radius: 8px;"
                    f"  padding: 8px 14px; font-size: {F.BODY}px; font-weight: bold;"
                    f"}}"
                    f"QPushButton:hover {{"
                    f"  background: {C.BG_HOVER}; border-color: {C.ACCENT};"
                    f"}}"
                )

    def _on_input_changed(self, text):
        try:
            val = int(text)
            if val > 0:
                self._known_grams = val
                self._s2_selected.setText(f"{val} g")
                self._s2_next_btn.setEnabled(True)
            else:
                self._s2_next_btn.setEnabled(False)
        except ValueError:
            self._s2_next_btn.setEnabled(False)

    def _confirm_known_weight(self):
        if self._known_grams > 0:
            self._go_step(2)

    # ══════════════════════════════════════════════════════
    # STEP 3: Place weight -> read loaded value
    # ══════════════════════════════════════════════════════

    def _build_step3(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(S.PAD)
        lay.setContentsMargins(0, S.GAP, 0, 0)

        self._s3_instr = QLabel("Place the weight on the scale")
        self._s3_instr.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.TEXT};"
        )
        self._s3_instr.setWordWrap(True)
        lay.addWidget(self._s3_instr)

        self._s3_desc = QLabel("Place your reference weight and wait for a stable reading.")
        self._s3_desc.setStyleSheet(f"font-size: {F.BODY}px; color: {C.TEXT_SEC};")
        self._s3_desc.setWordWrap(True)
        lay.addWidget(self._s3_desc)

        # Live reading card
        card = _reading_card()
        card_lay = QVBoxLayout(card)
        card_lay.setSpacing(4)

        self._s3_live_grams = QLabel("--- g")
        self._s3_live_grams.setStyleSheet(
            f"font-size: {F.H1}px; font-weight: bold; color: {C.ACCENT};"
        )
        self._s3_live_grams.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(self._s3_live_grams)

        self._s3_live_raw = QLabel("RAW: ---")
        self._s3_live_raw.setStyleSheet(
            f"font-size: {F.TINY}px; color: {C.TEXT_MUTED}; font-family: monospace;"
        )
        self._s3_live_raw.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(self._s3_live_raw)

        # Stability badge row
        stab_row = QHBoxLayout()
        stab_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._s3_stability_badge = type_badge("STABILIZING...", "warning")
        stab_row.addWidget(self._s3_stability_badge)
        card_lay.addLayout(stab_row)

        lay.addWidget(card)
        lay.addStretch()

        # ── Buttons ──
        btn_row = QHBoxLayout()

        back = QPushButton(f"{Icon.BACK}  BACK")
        back.setObjectName("ghost")
        back.setMinimumHeight(40)
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.clicked.connect(lambda: self._go_step(1))
        btn_row.addWidget(back)

        btn_row.addStretch()

        self._s3_read_btn = QPushButton(f"{Icon.WEIGHT}  READ")
        self._s3_read_btn.setObjectName("accent")
        self._s3_read_btn.setMinimumHeight(S.BTN_H)
        self._s3_read_btn.setMinimumWidth(140)
        self._s3_read_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._s3_read_btn.clicked.connect(self._do_read_loaded)
        btn_row.addWidget(self._s3_read_btn)

        lay.addLayout(btn_row)
        return page

    def _do_read_loaded(self):
        """Read the loaded raw value and calculate scale factor."""
        try:
            reading = self.app.weight.read_weight(self.channel)
            self._loaded_raw = reading.raw_value

            # Calculate scale factor
            # For inverted sensors: scale = abs(offset - loaded_raw) / known_grams
            raw_diff = abs(self._offset - self._loaded_raw)
            if self._known_grams > 0 and raw_diff > 0:
                self._scale = raw_diff / self._known_grams
            else:
                self._scale = 0.0

            logger.info(
                f"[CAL] Loaded raw={self._loaded_raw}, offset={self._offset}, "
                f"diff={raw_diff}, known={self._known_grams}g, scale={self._scale:.4f}"
            )

            # Visual feedback: flash green
            self._s3_live_grams.setStyleSheet(
                f"font-size: {F.H1}px; font-weight: bold; color: {C.SUCCESS};"
            )
            self._s3_read_btn.setEnabled(False)
            QTimer.singleShot(500, lambda: self._go_step(3))
        except Exception as e:
            # Flash red on error
            self._s3_live_grams.setStyleSheet(
                f"font-size: {F.H1}px; font-weight: bold; color: {C.DANGER};"
            )
            self._s3_live_grams.setText("ERROR")
            QTimer.singleShot(2000, lambda: (
                self._s3_live_grams.setStyleSheet(
                    f"font-size: {F.H1}px; font-weight: bold; color: {C.ACCENT};"
                ),
                self._s3_live_grams.setText("--- g"),
                self._s3_read_btn.setEnabled(True),
            ))

    # ══════════════════════════════════════════════════════
    # STEP 4: Results -> Save or Cancel
    # ══════════════════════════════════════════════════════

    def _build_step4(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(S.PAD)
        lay.setContentsMargins(0, S.GAP, 0, 0)

        instr = QLabel("Calibration Results")
        instr.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.TEXT};"
        )
        lay.addWidget(instr)

        # Results card
        results_card = QFrame()
        results_card.setObjectName("results_card")
        results_card.setStyleSheet(
            f"QFrame#results_card {{"
            f"  background-color: {C.BG_CARD};"
            f"  border: 1px solid {C.BORDER};"
            f"  border-radius: {S.RADIUS}px;"
            f"  padding: {S.PAD}px;"
            f"}}"
        )
        card_lay = QVBoxLayout(results_card)
        card_lay.setSpacing(0)

        # Result rows with alternating backgrounds
        self._s4_rows = {}
        row_defs = [
            ("Channel",       "channel"),
            ("Zero Offset",   "offset"),
            ("Loaded Raw",    "loaded"),
            ("Raw Difference","diff"),
            ("Known Weight",  "known"),
            ("Scale Factor",  "scale"),
            ("Resolution",    "resolution"),
            ("Status",        "status"),
        ]

        for idx, (label_text, key) in enumerate(row_defs):
            bg = C.BG_CARD if idx % 2 == 0 else C.BG_CARD_ALT
            row_frame = QFrame()
            row_frame.setStyleSheet(
                f"background-color: {bg}; border: none;"
                f"border-radius: 4px; padding: 2px 8px;"
            )
            row_lay = QHBoxLayout(row_frame)
            row_lay.setContentsMargins(8, 4, 8, 4)
            row_lay.setSpacing(S.PAD)

            lbl = QLabel(label_text)
            lbl.setStyleSheet(
                f"font-size: {F.SMALL}px; color: {C.TEXT_MUTED};"
                f"font-weight: bold; background: transparent;"
            )
            lbl.setFixedWidth(130)
            row_lay.addWidget(lbl)

            val = QLabel("---")
            val.setStyleSheet(
                f"font-size: {F.BODY}px; color: {C.TEXT};"
                f"font-weight: bold; font-family: monospace;"
                f"background: transparent;"
            )
            row_lay.addWidget(val, stretch=1)

            self._s4_rows[key] = val
            card_lay.addWidget(row_frame)

        lay.addWidget(results_card)
        lay.addStretch()

        # ── Buttons ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(S.GAP)

        cancel = QPushButton(f"{Icon.CLOSE}  CANCEL")
        cancel.setObjectName("danger")
        cancel.setMinimumHeight(44)
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        redo = QPushButton(f"{Icon.REFRESH}  REDO")
        redo.setObjectName("ghost")
        redo.setMinimumHeight(44)
        redo.setCursor(Qt.CursorShape.PointingHandCursor)
        redo.clicked.connect(lambda: self._go_step(0))
        btn_row.addWidget(redo)

        btn_row.addStretch()

        self._s4_save_btn = QPushButton(f"{Icon.SAVE}  SAVE")
        self._s4_save_btn.setObjectName("success")
        self._s4_save_btn.setMinimumHeight(S.BTN_H)
        self._s4_save_btn.setMinimumWidth(140)
        self._s4_save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._s4_save_btn.clicked.connect(self._do_save)
        btn_row.addWidget(self._s4_save_btn)

        lay.addLayout(btn_row)
        return page

    def _populate_results(self):
        """Fill in the results page with calculated values."""
        self._s4_rows["channel"].setText(self.channel)
        self._s4_rows["offset"].setText(str(self._offset))
        self._s4_rows["loaded"].setText(str(self._loaded_raw))

        raw_diff = abs(self._offset - self._loaded_raw)
        self._s4_rows["diff"].setText(str(raw_diff))
        self._s4_rows["known"].setText(f"{self._known_grams} g")

        # Scale factor: highlighted in SUCCESS, larger font
        self._s4_rows["scale"].setText(f"{self._scale:.4f}")
        self._s4_rows["scale"].setStyleSheet(
            f"font-size: {F.H3}px; color: {C.SUCCESS};"
            f"font-weight: bold; font-family: monospace;"
            f"background: transparent;"
        )

        # Resolution: 1 raw unit = how many grams
        if self._scale > 0:
            resolution = 1.0 / self._scale
            self._s4_rows["resolution"].setText(f"{resolution:.2f} g/unit")
        else:
            self._s4_rows["resolution"].setText("N/A")

        # Status badge (replace the label with a type_badge)
        status_val = self._s4_rows["status"]
        if self._scale <= 0:
            status_val.setText("INVALID")
            status_val.setStyleSheet(
                f"font-size: {F.BODY}px; color: {C.DANGER};"
                f"font-weight: bold; background: transparent;"
            )
            self._s4_save_btn.setEnabled(False)
        elif raw_diff < 100:
            status_val.setText("LOW SIGNAL")
            status_val.setStyleSheet(
                f"font-size: {F.BODY}px; color: {C.WARNING};"
                f"font-weight: bold; background: transparent;"
            )
            self._s4_save_btn.setEnabled(True)
        else:
            status_val.setText(f"{Icon.OK}  GOOD")
            status_val.setStyleSheet(
                f"font-size: {F.BODY}px; color: {C.SUCCESS};"
                f"font-weight: bold; background: transparent;"
            )
            self._s4_save_btn.setEnabled(True)

    def _do_save(self):
        """Apply calibration to driver and persist to database."""
        try:
            # Apply to driver
            if hasattr(self.app.weight, 'set_calibration'):
                self.app.weight.set_calibration(self.channel, self._offset, self._scale)

            # Persist to database
            cal_data = {
                "offset": self._offset,
                "scale": self._scale,
                "known_grams": self._known_grams,
                "loaded_raw": self._loaded_raw,
                "calibrated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            key = f"hx711_cal_{self.channel}"
            self.app.db.save_config(key, json.dumps(cal_data))
            logger.info(f"[CAL] Saved calibration for {self.channel}: {cal_data}")

            # Visual feedback: green flash on save button
            self._s4_save_btn.setObjectName("success")
            self._s4_save_btn.setEnabled(False)
            self._s4_save_btn.setText(f"{Icon.OK}  SAVED")
            QTimer.singleShot(1000, self.accept)
        except Exception as e:
            logger.error(f"[CAL] Save failed: {e}")
            self._s4_save_btn.setText(f"{Icon.ERROR}  ERROR")
            self._s4_save_btn.setStyleSheet(
                f"background: {C.DANGER_BG}; color: {C.DANGER};"
                f"border: 1px solid {C.DANGER};"
            )
            QTimer.singleShot(2000, lambda: (
                self._s4_save_btn.setText(f"{Icon.SAVE}  SAVE"),
                self._s4_save_btn.setObjectName("success"),
                self._s4_save_btn.setEnabled(True),
            ))

    # ══════════════════════════════════════════════════════
    # NAVIGATION
    # ══════════════════════════════════════════════════════

    def _go_step(self, step: int):
        self._stack.setCurrentIndex(step)

        # Update step badge
        self._step_badge.setText(f"Step {step + 1}/4")

        # Animate progress bar
        target_pct = (step + 1) * 25
        self._progress.setValue(target_pct)

        # Start/stop live timer
        if step in (0, 2):
            self._live_timer.start()
        else:
            self._live_timer.stop()

        # Populate results on step 4
        if step == 3:
            self._populate_results()

        # Update step 3 description with known weight
        if step == 2:
            self._s3_desc.setText(
                f"Place your {self._known_grams}g reference weight and wait for a stable reading."
            )

        # Reset button states when revisiting steps
        if step == 0:
            self._s1_set_zero_btn.setEnabled(True)
            self._s1_set_zero_btn.setText(f"{Icon.SENSORS}  SET ZERO")
            self._s1_live_grams.setStyleSheet(
                f"font-size: {F.H1}px; font-weight: bold; color: {C.ACCENT};"
            )
        if step == 2:
            self._s3_read_btn.setEnabled(True)
            self._s3_read_btn.setText(f"{Icon.WEIGHT}  READ")
            self._s3_live_grams.setStyleSheet(
                f"font-size: {F.H1}px; font-weight: bold; color: {C.ACCENT};"
            )

    def _update_live_reading(self):
        """Update live weight display on steps 1 and 3."""
        try:
            reading = self.app.weight.read_weight(self.channel)
            grams_text = f"{reading.grams:.1f} g"
            raw_text = f"RAW: {reading.raw_value}"
            stable = reading.stable

            step = self._stack.currentIndex()
            if step == 0:
                self._s1_live_grams.setText(grams_text)
                self._s1_live_raw.setText(raw_text)
                # Replace stability badge
                old_badge = self._s1_stability_badge
                if stable:
                    self._s1_stability_badge = type_badge(f"{Icon.OK} STABLE", "success")
                else:
                    self._s1_stability_badge = type_badge("STABILIZING...", "warning")
                parent_layout = old_badge.parentWidget().layout()
                if parent_layout:
                    # Find the HBoxLayout containing the badge
                    for i in range(parent_layout.count()):
                        item = parent_layout.itemAt(i)
                        if item and item.layout():
                            inner = item.layout()
                            for j in range(inner.count()):
                                w = inner.itemAt(j).widget()
                                if w is old_badge:
                                    inner.replaceWidget(old_badge, self._s1_stability_badge)
                                    old_badge.deleteLater()
                                    break

            elif step == 2:
                self._s3_live_grams.setText(grams_text)
                self._s3_live_raw.setText(raw_text)
                # Replace stability badge
                old_badge = self._s3_stability_badge
                if stable:
                    self._s3_stability_badge = type_badge(f"{Icon.OK} STABLE", "success")
                else:
                    self._s3_stability_badge = type_badge("STABILIZING...", "warning")
                parent_layout = old_badge.parentWidget().layout()
                if parent_layout:
                    for i in range(parent_layout.count()):
                        item = parent_layout.itemAt(i)
                        if item and item.layout():
                            inner = item.layout()
                            for j in range(inner.count()):
                                w = inner.itemAt(j).widget()
                                if w is old_badge:
                                    inner.replaceWidget(old_badge, self._s3_stability_badge)
                                    old_badge.deleteLater()
                                    break
        except Exception:
            pass

    def closeEvent(self, event):
        self._live_timer.stop()
        event.accept()
