"""
Calibration Wizard — 4-step modal dialog for HX711 scale calibration.

Steps:
1. Remove all weight → SET ZERO (reads offset)
2. Enter known weight in grams (presets: 500, 1000, 2000, 5000)
3. Place known weight → READ value
4. Review results → SAVE or CANCEL
"""

import json
import logging
import time

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QWidget, QLineEdit, QFrame, QGridLayout,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIntValidator

from ui_qt.theme import C, F, S

logger = logging.getLogger("smartlocker.calibration")

_F_BIG = 32
_F_MED = 16
_F_SM = 13


def _card(layout=None) -> QFrame:
    f = QFrame()
    f.setObjectName("card")
    if layout:
        f.setLayout(layout)
    return f


class CalibrationWizard(QDialog):
    """4-step calibration wizard for HX711 weight channels."""

    def __init__(self, app, channel: str, parent=None):
        super().__init__(parent)
        self.app = app
        self.channel = channel
        self.setWindowTitle(f"Calibrate: {channel}")
        self.setMinimumSize(700, 400)
        self.setStyleSheet(f"background-color: {C.BG_DARK}; color: {C.TEXT};")

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

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(8)

        # Title bar
        title_row = QHBoxLayout()
        self._title = QLabel("CALIBRATION")
        self._title.setStyleSheet(f"font-size: {F.H3}px; font-weight: bold; color: {C.PRIMARY};")
        title_row.addWidget(self._title)
        title_row.addStretch()
        self._step_label = QLabel("Step 1/4")
        self._step_label.setStyleSheet(f"font-size: {_F_SM}px; color: {C.TEXT_SEC};")
        title_row.addWidget(self._step_label)
        root.addLayout(title_row)

        # Progress bar (simple 4-segment)
        self._progress_bar = QFrame()
        self._progress_bar.setFixedHeight(4)
        self._progress_bar.setStyleSheet(f"background-color: {C.BORDER}; border-radius: 2px;")
        root.addWidget(self._progress_bar)

        # Stacked pages
        self._stack = QStackedWidget()
        root.addWidget(self._stack, stretch=1)

        self._stack.addWidget(self._build_step1())  # 0: Remove weight
        self._stack.addWidget(self._build_step2())  # 1: Enter known weight
        self._stack.addWidget(self._build_step3())  # 2: Place weight
        self._stack.addWidget(self._build_step4())  # 3: Results

    # ──────────────────────────────────────────────
    # STEP 1: Remove all weight → read zero offset
    # ──────────────────────────────────────────────

    def _build_step1(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)

        instr = QLabel("STEP 1: Remove all weight from the scale")
        instr.setStyleSheet(f"font-size: {_F_MED}px; font-weight: bold; color: {C.TEXT};")
        instr.setWordWrap(True)
        lay.addWidget(instr)

        desc = QLabel("Make sure the scale is completely empty and stable before setting zero.")
        desc.setStyleSheet(f"font-size: {_F_SM}px; color: {C.TEXT_SEC};")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        # Live reading display
        read_lay = QVBoxLayout()
        read_lay.setSpacing(2)
        self._s1_live_grams = QLabel("--- g")
        self._s1_live_grams.setStyleSheet(f"font-size: {_F_BIG}px; font-weight: bold; color: {C.PRIMARY};")
        self._s1_live_grams.setAlignment(Qt.AlignmentFlag.AlignCenter)
        read_lay.addWidget(self._s1_live_grams)

        self._s1_live_raw = QLabel("RAW: ---")
        self._s1_live_raw.setStyleSheet(f"font-size: {_F_SM}px; color: {C.TEXT_MUTED}; font-family: monospace;")
        self._s1_live_raw.setAlignment(Qt.AlignmentFlag.AlignCenter)
        read_lay.addWidget(self._s1_live_raw)

        self._s1_stability = QLabel("Waiting for stable reading...")
        self._s1_stability.setStyleSheet(f"font-size: {_F_SM}px; color: {C.WARNING};")
        self._s1_stability.setAlignment(Qt.AlignmentFlag.AlignCenter)
        read_lay.addWidget(self._s1_stability)

        card = _card(read_lay)
        lay.addWidget(card)

        lay.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        cancel = QPushButton("CANCEL")
        cancel.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C.TEXT_SEC}; border: 1px solid {C.BORDER};"
            f"border-radius: 8px; padding: 10px 20px; font-size: {_F_MED}px; }}"
        )
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        btn_row.addStretch()

        self._s1_set_zero_btn = QPushButton("SET ZERO")
        self._s1_set_zero_btn.setStyleSheet(
            f"QPushButton {{ background: {C.PRIMARY}; color: {C.BG_DARK}; border: none;"
            f"border-radius: 8px; padding: 10px 30px; font-size: {_F_MED}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {C.PRIMARY_DIM}; }}"
            f"QPushButton:disabled {{ background: {C.BG_CARD_ALT}; color: {C.TEXT_MUTED}; }}"
        )
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
            self._s1_set_zero_btn.setText("OK!")
            QTimer.singleShot(500, lambda: self._go_step(1))
        except Exception as e:
            self._s1_set_zero_btn.setText(f"ERROR: {e}")
            QTimer.singleShot(2000, lambda: self._s1_set_zero_btn.setText("SET ZERO"))

    # ──────────────────────────────────────────────
    # STEP 2: Enter known weight
    # ──────────────────────────────────────────────

    def _build_step2(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)

        instr = QLabel("STEP 2: Enter the known weight in grams")
        instr.setStyleSheet(f"font-size: {_F_MED}px; font-weight: bold; color: {C.TEXT};")
        instr.setWordWrap(True)
        lay.addWidget(instr)

        desc = QLabel("How many grams does your reference weight weigh? Use a precise weight.")
        desc.setStyleSheet(f"font-size: {_F_SM}px; color: {C.TEXT_SEC};")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        # Preset buttons
        preset_row = QHBoxLayout()
        preset_row.setSpacing(8)
        for grams in [500, 1000, 2000, 5000]:
            b = QPushButton(f"{grams}g")
            b.setStyleSheet(
                f"QPushButton {{ background: {C.BG_CARD}; color: {C.TEXT}; border: 1px solid {C.BORDER};"
                f"border-radius: 8px; padding: 12px 16px; font-size: {_F_MED}px; font-weight: bold; }}"
                f"QPushButton:hover {{ background: {C.BG_HOVER}; border-color: {C.PRIMARY}; }}"
            )
            b.clicked.connect(lambda checked, g=grams: self._set_known_weight(g))
            preset_row.addWidget(b)
        lay.addLayout(preset_row)

        # Manual input
        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        lbl = QLabel("Custom:")
        lbl.setStyleSheet(f"font-size: {_F_MED}px; color: {C.TEXT_SEC};")
        input_row.addWidget(lbl)

        self._s2_input = QLineEdit()
        self._s2_input.setPlaceholderText("Enter grams...")
        self._s2_input.setValidator(QIntValidator(1, 99999))
        self._s2_input.setFixedWidth(160)
        self._s2_input.setStyleSheet(
            f"font-size: {_F_MED}px; padding: 8px 12px; font-weight: bold;"
        )
        input_row.addWidget(self._s2_input)

        g_lbl = QLabel("g")
        g_lbl.setStyleSheet(f"font-size: {_F_MED}px; color: {C.TEXT_SEC};")
        input_row.addWidget(g_lbl)
        input_row.addStretch()
        lay.addLayout(input_row)

        self._s2_selected = QLabel("Selected: ---")
        self._s2_selected.setStyleSheet(f"font-size: {_F_BIG}px; font-weight: bold; color: {C.PRIMARY};")
        self._s2_selected.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._s2_selected)

        lay.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        back = QPushButton("BACK")
        back.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C.TEXT_SEC}; border: 1px solid {C.BORDER};"
            f"border-radius: 8px; padding: 10px 20px; font-size: {_F_MED}px; }}"
        )
        back.clicked.connect(lambda: self._go_step(0))
        btn_row.addWidget(back)
        btn_row.addStretch()

        self._s2_next_btn = QPushButton("NEXT")
        self._s2_next_btn.setEnabled(False)
        self._s2_next_btn.setStyleSheet(
            f"QPushButton {{ background: {C.PRIMARY}; color: {C.BG_DARK}; border: none;"
            f"border-radius: 8px; padding: 10px 30px; font-size: {_F_MED}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {C.PRIMARY_DIM}; }}"
            f"QPushButton:disabled {{ background: {C.BG_CARD_ALT}; color: {C.TEXT_MUTED}; }}"
        )
        self._s2_next_btn.clicked.connect(self._confirm_known_weight)
        btn_row.addWidget(self._s2_next_btn)
        lay.addLayout(btn_row)

        # Connect input change
        self._s2_input.textChanged.connect(self._on_input_changed)

        return page

    def _set_known_weight(self, grams: int):
        self._known_grams = grams
        self._s2_input.setText(str(grams))
        self._s2_selected.setText(f"{grams} g")
        self._s2_next_btn.setEnabled(True)

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

    # ──────────────────────────────────────────────
    # STEP 3: Place weight → read loaded value
    # ──────────────────────────────────────────────

    def _build_step3(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)

        self._s3_instr = QLabel("STEP 3: Place the weight on the scale")
        self._s3_instr.setStyleSheet(f"font-size: {_F_MED}px; font-weight: bold; color: {C.TEXT};")
        self._s3_instr.setWordWrap(True)
        lay.addWidget(self._s3_instr)

        self._s3_desc = QLabel("Place your reference weight and wait for a stable reading.")
        self._s3_desc.setStyleSheet(f"font-size: {_F_SM}px; color: {C.TEXT_SEC};")
        self._s3_desc.setWordWrap(True)
        lay.addWidget(self._s3_desc)

        # Live reading
        read_lay = QVBoxLayout()
        read_lay.setSpacing(2)
        self._s3_live_grams = QLabel("--- g")
        self._s3_live_grams.setStyleSheet(f"font-size: {_F_BIG}px; font-weight: bold; color: {C.PRIMARY};")
        self._s3_live_grams.setAlignment(Qt.AlignmentFlag.AlignCenter)
        read_lay.addWidget(self._s3_live_grams)

        self._s3_live_raw = QLabel("RAW: ---")
        self._s3_live_raw.setStyleSheet(f"font-size: {_F_SM}px; color: {C.TEXT_MUTED}; font-family: monospace;")
        self._s3_live_raw.setAlignment(Qt.AlignmentFlag.AlignCenter)
        read_lay.addWidget(self._s3_live_raw)

        self._s3_stability = QLabel("Waiting for stable reading...")
        self._s3_stability.setStyleSheet(f"font-size: {_F_SM}px; color: {C.WARNING};")
        self._s3_stability.setAlignment(Qt.AlignmentFlag.AlignCenter)
        read_lay.addWidget(self._s3_stability)

        card = _card(read_lay)
        lay.addWidget(card)

        lay.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        back = QPushButton("BACK")
        back.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C.TEXT_SEC}; border: 1px solid {C.BORDER};"
            f"border-radius: 8px; padding: 10px 20px; font-size: {_F_MED}px; }}"
        )
        back.clicked.connect(lambda: self._go_step(1))
        btn_row.addWidget(back)
        btn_row.addStretch()

        self._s3_read_btn = QPushButton("READ")
        self._s3_read_btn.setStyleSheet(
            f"QPushButton {{ background: {C.PRIMARY}; color: {C.BG_DARK}; border: none;"
            f"border-radius: 8px; padding: 10px 30px; font-size: {_F_MED}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {C.PRIMARY_DIM}; }}"
            f"QPushButton:disabled {{ background: {C.BG_CARD_ALT}; color: {C.TEXT_MUTED}; }}"
        )
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

            self._s3_read_btn.setText("OK!")
            QTimer.singleShot(500, lambda: self._go_step(3))
        except Exception as e:
            self._s3_read_btn.setText(f"ERROR: {e}")
            QTimer.singleShot(2000, lambda: self._s3_read_btn.setText("READ"))

    # ──────────────────────────────────────────────
    # STEP 4: Results → Save or Cancel
    # ──────────────────────────────────────────────

    def _build_step4(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(12)

        instr = QLabel("STEP 4: Calibration Results")
        instr.setStyleSheet(f"font-size: {_F_MED}px; font-weight: bold; color: {C.TEXT};")
        lay.addWidget(instr)

        # Results grid
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        grid.setContentsMargins(12, 8, 12, 8)

        def _lbl(text):
            l = QLabel(text)
            l.setStyleSheet(f"font-size: {_F_SM}px; color: {C.TEXT_MUTED};")
            return l

        def _val(obj_name):
            l = QLabel("---")
            l.setStyleSheet(f"font-size: {_F_MED}px; color: {C.TEXT}; font-weight: bold; font-family: monospace;")
            return l

        grid.addWidget(_lbl("Channel:"), 0, 0)
        self._s4_channel = _val("channel")
        grid.addWidget(self._s4_channel, 0, 1)

        grid.addWidget(_lbl("Zero Offset:"), 1, 0)
        self._s4_offset = _val("offset")
        grid.addWidget(self._s4_offset, 1, 1)

        grid.addWidget(_lbl("Loaded Raw:"), 1, 2)
        self._s4_loaded = _val("loaded")
        grid.addWidget(self._s4_loaded, 1, 3)

        grid.addWidget(_lbl("Raw Difference:"), 2, 0)
        self._s4_diff = _val("diff")
        grid.addWidget(self._s4_diff, 2, 1)

        grid.addWidget(_lbl("Known Weight:"), 2, 2)
        self._s4_known = _val("known")
        grid.addWidget(self._s4_known, 2, 3)

        grid.addWidget(_lbl("Scale Factor:"), 3, 0)
        self._s4_scale = _val("scale")
        self._s4_scale.setStyleSheet(f"font-size: {_F_BIG}px; color: {C.PRIMARY}; font-weight: bold; font-family: monospace;")
        grid.addWidget(self._s4_scale, 3, 1, 1, 3)

        grid.addWidget(_lbl("Resolution:"), 4, 0)
        self._s4_resolution = _val("res")
        grid.addWidget(self._s4_resolution, 4, 1)

        grid.addWidget(_lbl("Status:"), 4, 2)
        self._s4_status = _val("status")
        grid.addWidget(self._s4_status, 4, 3)

        card = _card(grid)
        lay.addWidget(card)

        lay.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        cancel = QPushButton("CANCEL")
        cancel.setStyleSheet(
            f"QPushButton {{ background: {C.DANGER_BG}; color: {C.DANGER}; border: 1px solid {C.DANGER};"
            f"border-radius: 8px; padding: 10px 20px; font-size: {_F_MED}px; font-weight: bold; }}"
        )
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        redo = QPushButton("REDO")
        redo.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C.TEXT_SEC}; border: 1px solid {C.BORDER};"
            f"border-radius: 8px; padding: 10px 20px; font-size: {_F_MED}px; }}"
        )
        redo.clicked.connect(lambda: self._go_step(0))
        btn_row.addWidget(redo)

        btn_row.addStretch()

        self._s4_save_btn = QPushButton("SAVE")
        self._s4_save_btn.setStyleSheet(
            f"QPushButton {{ background: {C.SUCCESS}; color: {C.BG_DARK}; border: none;"
            f"border-radius: 8px; padding: 10px 40px; font-size: {_F_MED}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {C.SUCCESS_BG}; color: {C.SUCCESS}; }}"
        )
        self._s4_save_btn.clicked.connect(self._do_save)
        btn_row.addWidget(self._s4_save_btn)
        lay.addLayout(btn_row)

        return page

    def _populate_results(self):
        """Fill in the results page with calculated values."""
        self._s4_channel.setText(self.channel)
        self._s4_offset.setText(str(self._offset))
        self._s4_loaded.setText(str(self._loaded_raw))
        raw_diff = abs(self._offset - self._loaded_raw)
        self._s4_diff.setText(str(raw_diff))
        self._s4_known.setText(f"{self._known_grams} g")
        self._s4_scale.setText(f"{self._scale:.4f}")

        # Resolution: 1 raw unit = how many grams
        if self._scale > 0:
            resolution = 1.0 / self._scale
            self._s4_resolution.setText(f"{resolution:.2f} g/unit")
        else:
            self._s4_resolution.setText("N/A")

        # Status check
        if self._scale <= 0:
            self._s4_status.setText("INVALID")
            self._s4_status.setStyleSheet(f"font-size: {_F_MED}px; color: {C.DANGER}; font-weight: bold;")
            self._s4_save_btn.setEnabled(False)
        elif raw_diff < 100:
            self._s4_status.setText("LOW SIGNAL")
            self._s4_status.setStyleSheet(f"font-size: {_F_MED}px; color: {C.WARNING}; font-weight: bold;")
            self._s4_save_btn.setEnabled(True)
        else:
            self._s4_status.setText("GOOD")
            self._s4_status.setStyleSheet(f"font-size: {_F_MED}px; color: {C.SUCCESS}; font-weight: bold;")
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

            self._s4_save_btn.setText("SAVED!")
            QTimer.singleShot(1000, self.accept)
        except Exception as e:
            logger.error(f"[CAL] Save failed: {e}")
            self._s4_save_btn.setText(f"ERROR: {e}")
            QTimer.singleShot(2000, lambda: self._s4_save_btn.setText("SAVE"))

    # ──────────────────────────────────────────────
    # NAVIGATION
    # ──────────────────────────────────────────────

    def _go_step(self, step: int):
        self._stack.setCurrentIndex(step)
        self._step_label.setText(f"Step {step + 1}/4")

        # Update progress bar color
        pct = (step + 1) * 25
        self._progress_bar.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 {C.PRIMARY}, stop:{pct/100} {C.PRIMARY}, "
            f"stop:{pct/100 + 0.01} {C.BORDER}, stop:1 {C.BORDER});"
            f"border-radius: 2px;"
        )

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
                if stable:
                    self._s1_stability.setText("STABLE - Ready to set zero")
                    self._s1_stability.setStyleSheet(f"font-size: {_F_SM}px; color: {C.SUCCESS};")
                else:
                    self._s1_stability.setText("Stabilizing...")
                    self._s1_stability.setStyleSheet(f"font-size: {_F_SM}px; color: {C.WARNING};")
            elif step == 2:
                self._s3_live_grams.setText(grams_text)
                self._s3_live_raw.setText(raw_text)
                if stable:
                    self._s3_stability.setText("STABLE - Ready to read")
                    self._s3_stability.setStyleSheet(f"font-size: {_F_SM}px; color: {C.SUCCESS};")
                else:
                    self._s3_stability.setText("Stabilizing...")
                    self._s3_stability.setStyleSheet(f"font-size: {_F_SM}px; color: {C.WARNING};")
        except Exception:
            pass

    def closeEvent(self, event):
        self._live_timer.stop()
        event.accept()
