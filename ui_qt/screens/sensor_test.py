"""
SmartLocker Sensor Testing Screen — optimized for 800x480 4.3" touch

QTabWidget with 4 tabs: Weight, RFID, LED, Buzzer.
Each tab uses compact horizontal layouts to maximize use of limited height.
"""

import time
import logging
from collections import deque

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTabWidget, QGridLayout, QScrollArea, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QPainterPath

from ui_qt.theme import C, F, S, enable_touch_scroll
from hal.interfaces import LEDColor, LEDPattern, BuzzerPattern

logger = logging.getLogger("smartlocker.sensor_test")

# Compact font sizes for 480px height
_F_BIG = 28       # Main reading
_F_MED = 14       # Labels
_F_SM = 12        # Secondary info
_PAD = 6          # Reduced padding


# ══════════════════════════════════════════════════════════
# WEIGHT CHART
# ══════════════════════════════════════════════════════════

class WeightChartWidget(QWidget):
    """Rolling line chart of weight readings."""
    MAX_POINTS = 50

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = deque(maxlen=self.MAX_POINTS)
        self.setMinimumHeight(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"background-color: {C.BG_INPUT}; border-radius: 6px;")

    def add_point(self, grams: float):
        self._data.append(grams)
        self.update()

    def clear_data(self):
        self._data.clear()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        m = 6
        painter.fillRect(self.rect(), QColor(C.BG_INPUT))

        if len(self._data) < 2:
            painter.setPen(QColor(C.TEXT_MUTED))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Waiting...")
            painter.end()
            return

        data = list(self._data)
        mn, mx = min(data), max(data)
        rng = mx - mn
        if rng < 1.0:
            rng = 1.0
            mn -= 0.5
            mx += 0.5

        pw, ph = w - m * 2, h - m * 2

        # Grid
        painter.setPen(QPen(QColor(C.BORDER), 1, Qt.PenStyle.DotLine))
        for i in range(3):
            y = m + (ph * i / 2)
            painter.drawLine(QPointF(m, y), QPointF(m + pw, y))

        # Labels
        painter.setPen(QColor(C.TEXT_MUTED))
        painter.setFont(QFont("Segoe UI", 7))
        painter.drawText(QRectF(0, m - 2, 44, 12), Qt.AlignmentFlag.AlignLeft, f"{mx / 1000:.1f}kg")
        painter.drawText(QRectF(0, m + ph - 10, 44, 12), Qt.AlignmentFlag.AlignLeft, f"{mn / 1000:.1f}kg")

        # Line + fill
        n = len(data)
        pts = [QPointF(m + pw * i / (n - 1), m + ph - (v - mn) / rng * ph) for i, v in enumerate(data)]

        fill = QPainterPath()
        fill.moveTo(QPointF(pts[0].x(), m + ph))
        for p in pts:
            fill.lineTo(p)
        fill.lineTo(QPointF(pts[-1].x(), m + ph))
        fill.closeSubpath()
        fc = QColor(C.PRIMARY)
        fc.setAlpha(30)
        painter.fillPath(fill, fc)

        painter.setPen(QPen(QColor(C.PRIMARY), 2))
        for i in range(len(pts) - 1):
            painter.drawLine(pts[i], pts[i + 1])

        painter.setBrush(QColor(C.PRIMARY))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(pts[-1], 3, 3)
        painter.end()


# ══════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════

def _card(layout=None) -> QFrame:
    f = QFrame()
    f.setObjectName("card")
    if layout:
        f.setLayout(layout)
    return f


def _badge(text: str, is_real: bool) -> QLabel:
    lbl = QLabel(text)
    if is_real:
        lbl.setStyleSheet(
            f"background-color: {C.SUCCESS_BG}; color: {C.SUCCESS};"
            f"border: 1px solid {C.SUCCESS}; border-radius: 3px;"
            f"padding: 1px 6px; font-size: {_F_SM}px; font-weight: bold;"
        )
    else:
        lbl.setStyleSheet(
            f"background-color: {C.BG_CARD_ALT}; color: {C.TEXT_MUTED};"
            f"border: 1px solid {C.TEXT_MUTED}; border-radius: 3px;"
            f"padding: 1px 6px; font-size: {_F_SM}px;"
        )
    return lbl


def _hdr_row(name: str, drv_type: str, healthy: bool) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)
    row.addWidget(_badge(drv_type.upper(), drv_type == "real"))
    lbl = QLabel(name)
    lbl.setStyleSheet(f"font-size: {_F_MED}px; font-weight: bold; color: {C.TEXT};")
    row.addWidget(lbl)
    row.addStretch()
    c = C.SUCCESS if healthy else C.DANGER
    dot = QLabel("Healthy" if healthy else "Offline")
    dot.setStyleSheet(f"font-size: {_F_SM}px; color: {c}; font-weight: bold;")
    row.addWidget(dot)
    return row


def _btn(text: str, style: str = "") -> QPushButton:
    b = QPushButton(text)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if style:
        b.setStyleSheet(style)
    return b


# ══════════════════════════════════════════════════════════
# MAIN SCREEN
# ══════════════════════════════════════════════════════════

class SensorTestScreen(QWidget):

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._weight_timer = QTimer()
        self._weight_timer.setInterval(300)
        self._weight_timer.timeout.connect(self._update_weight)
        self._active_channel = None
        self._led_slot_colors = {}
        self._led_current_pattern = LEDPattern.SOLID
        self._rfid_history = deque(maxlen=10)
        self._color_cycle = [
            LEDColor.OFF, LEDColor.GREEN, LEDColor.RED,
            LEDColor.YELLOW, LEDColor.BLUE, LEDColor.WHITE,
        ]
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(_PAD, _PAD, _PAD, _PAD)
        root.setSpacing(4)

        # Top bar — compact
        top = QHBoxLayout()
        top.setSpacing(8)
        back = _btn("< Back", f"QPushButton {{ background: transparent; color: {C.TEXT_SEC}; border: none; font-size: {_F_MED}px; }}")
        back.clicked.connect(self.app.go_back)
        top.addWidget(back)
        t = QLabel("SENSOR TEST")
        t.setStyleSheet(f"font-size: {F.H3}px; font-weight: bold; color: {C.TEXT};")
        top.addWidget(t)
        top.addStretch()
        m = QLabel(self.app.mode.upper())
        m.setStyleSheet(
            f"background-color: {C.SUCCESS_BG if self.app.mode != 'test' else C.BG_CARD_ALT};"
            f"color: {C.SUCCESS if self.app.mode != 'test' else C.TEXT_MUTED};"
            f"border: 1px solid {C.SUCCESS if self.app.mode != 'test' else C.TEXT_MUTED};"
            f"border-radius: 3px; padding: 1px 6px; font-size: {_F_SM}px; font-weight: bold;"
        )
        top.addWidget(m)
        root.addLayout(top)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            f"QTabBar::tab {{ padding: 6px 14px; font-size: {_F_MED}px; min-width: 60px; }}"
        )
        root.addWidget(self._tabs, stretch=1)
        self._tabs.addTab(self._build_weight_tab(), "Weight")
        self._tabs.addTab(self._build_rfid_tab(), "RFID")
        self._tabs.addTab(self._build_led_tab(), "LED")
        self._tabs.addTab(self._build_buzzer_tab(), "Buzzer")

    # ──────────────────────────────────────────────────
    # WEIGHT TAB — horizontal: reading left, chart right
    # ──────────────────────────────────────────────────

    def _build_weight_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(_PAD, _PAD, _PAD, _PAD)
        layout.setSpacing(4)

        # Header
        healthy = False
        try:
            healthy = self.app.weight.is_healthy()
        except Exception:
            pass
        layout.addLayout(_hdr_row("HX711 Weight", self.app.driver_status.get("weight", "fake"), healthy))

        # Channel selector
        chan_row = QHBoxLayout()
        chan_row.setSpacing(4)
        lbl = QLabel("CH:")
        lbl.setStyleSheet(f"font-size: {_F_SM}px; color: {C.TEXT_SEC};")
        chan_row.addWidget(lbl)
        self._channel_btns = {}
        channels = []
        try:
            channels = self.app.weight.get_channels()
        except Exception:
            channels = ["shelf1", "mixing_scale"]
        for ch in channels:
            b = _btn(ch, f"QPushButton {{ font-size: {_F_SM}px; padding: 2px 8px; border: 1px solid {C.BORDER}; border-radius: 4px; color: {C.TEXT}; background: {C.BG_CARD}; }}")
            b.setCheckable(True)
            b.clicked.connect(lambda checked, c=ch: self._select_channel(c))
            chan_row.addWidget(b)
            self._channel_btns[ch] = b
        chan_row.addStretch()
        layout.addLayout(chan_row)
        if channels:
            self._active_channel = channels[0]
            self._channel_btns[channels[0]].setChecked(True)

        # Main area: reading (left) + chart (right)
        main_row = QHBoxLayout()
        main_row.setSpacing(8)

        # Left: reading card
        read_lay = QVBoxLayout()
        read_lay.setSpacing(0)
        read_lay.setContentsMargins(8, 4, 8, 4)

        self._weight_grams = QLabel("---")
        self._weight_grams.setStyleSheet(f"font-size: {_F_BIG}px; font-weight: bold; color: {C.PRIMARY};")
        self._weight_grams.setAlignment(Qt.AlignmentFlag.AlignCenter)
        read_lay.addWidget(self._weight_grams)

        self._weight_kg = QLabel("--- kg")
        self._weight_kg.setStyleSheet(f"font-size: {_F_MED}px; color: {C.TEXT_SEC};")
        self._weight_kg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        read_lay.addWidget(self._weight_kg)

        stab_row = QHBoxLayout()
        stab_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stability_dot = QLabel("*")
        self._stability_dot.setStyleSheet(f"font-size: {_F_SM}px; color: {C.WARNING};")
        stab_row.addWidget(self._stability_dot)
        self._stability_text = QLabel("WAIT")
        self._stability_text.setStyleSheet(f"font-size: {_F_SM}px; font-weight: bold; color: {C.WARNING};")
        stab_row.addWidget(self._stability_text)
        read_lay.addLayout(stab_row)

        self._weight_raw = QLabel("RAW: ---")
        self._weight_raw.setStyleSheet(f"font-size: {_F_SM}px; color: {C.TEXT_MUTED};")
        self._weight_raw.setAlignment(Qt.AlignmentFlag.AlignCenter)
        read_lay.addWidget(self._weight_raw)

        read_card = _card(read_lay)
        read_card.setFixedWidth(220)
        main_row.addWidget(read_card)

        # Right: chart
        self._weight_chart = WeightChartWidget()
        main_row.addWidget(self._weight_chart, stretch=1)

        layout.addLayout(main_row, stretch=1)

        # Bottom buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        self._tare_btn = _btn("TARE", f"QPushButton {{ background: {C.PRIMARY}; color: {C.BG_DARK}; border: none; border-radius: 6px; font-size: {_F_MED}px; font-weight: bold; padding: 8px 16px; }} QPushButton:hover {{ background: {C.PRIMARY_DIM}; }}")
        self._tare_btn.clicked.connect(self._do_tare)
        btn_row.addWidget(self._tare_btn)

        self._calibrate_btn = _btn("CALIBRATE", f"QPushButton {{ background: {C.SECONDARY_BG}; color: {C.SECONDARY}; border: 1px solid {C.SECONDARY}; border-radius: 6px; font-size: {_F_MED}px; padding: 8px 16px; }} QPushButton:hover {{ background: {C.BG_HOVER}; }}")
        self._calibrate_btn.clicked.connect(self._do_calibrate)
        btn_row.addWidget(self._calibrate_btn)

        clr = _btn("Clear", f"QPushButton {{ background: transparent; color: {C.TEXT_SEC}; border: none; font-size: {_F_SM}px; }}")
        clr.clicked.connect(self._weight_chart.clear_data)
        btn_row.addWidget(clr)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        return tab

    def _select_channel(self, channel):
        self._active_channel = channel
        for ch, b in self._channel_btns.items():
            b.setChecked(ch == channel)
        self._weight_chart.clear_data()

    def _update_weight(self):
        if not self._active_channel:
            return
        try:
            r = self.app.weight.read_weight(self._active_channel)
            self._weight_grams.setText(f"{r.grams / 1000:.2f} kg")
            self._weight_kg.setText(f"{r.grams:.0f} g")
            self._weight_raw.setText(f"RAW: {r.raw_value}")
            c = C.SUCCESS if r.stable else C.WARNING
            txt = "STABLE" if r.stable else "..."
            self._stability_dot.setStyleSheet(f"font-size: {_F_SM}px; color: {c};")
            self._stability_text.setText(txt)
            self._stability_text.setStyleSheet(f"font-size: {_F_SM}px; font-weight: bold; color: {c};")
            self._weight_chart.add_point(r.grams)
        except Exception as e:
            self._weight_grams.setText("ERR")
            self._weight_raw.setText(str(e)[:30])

    def _do_tare(self):
        if not self._active_channel:
            return
        try:
            self.app.weight.tare(self._active_channel)
            self._tare_btn.setText("OK!")
            self._weight_chart.clear_data()
            QTimer.singleShot(1000, lambda: self._tare_btn.setText("TARE"))
        except Exception:
            self._tare_btn.setText("FAIL")
            QTimer.singleShot(1000, lambda: self._tare_btn.setText("TARE"))

    def _do_calibrate(self):
        if not self._active_channel:
            return
        from ui_qt.widgets.calibration_wizard import CalibrationWizard
        wizard = CalibrationWizard(self.app, self._active_channel, parent=self)
        result = wizard.exec()
        if result == wizard.DialogCode.Accepted:
            self._calibrate_btn.setText("SAVED!")
            QTimer.singleShot(1500, lambda: self._calibrate_btn.setText("CALIBRATE"))
        else:
            self._calibrate_btn.setText("CALIBRATE")

    # ──────────────────────────────────────────────────
    # RFID TAB — compact: scan + result side by side
    # ──────────────────────────────────────────────────

    def _build_rfid_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(_PAD, _PAD, _PAD, _PAD)
        layout.setSpacing(4)

        # Header
        healthy = False
        try:
            healthy = self.app.rfid.is_healthy()
        except Exception:
            pass
        layout.addLayout(_hdr_row("PN532 USB NFC", self.app.driver_status.get("rfid", "fake"), healthy))

        # Scan button — not huge
        self._rfid_scan_btn = _btn("SCAN NOW", f"QPushButton {{ background: {C.PRIMARY}; color: {C.BG_DARK}; border: none; border-radius: 6px; font-size: {_F_MED}px; font-weight: bold; padding: 10px; }} QPushButton:hover {{ background: {C.PRIMARY_DIM}; }}")
        self._rfid_scan_btn.setFixedHeight(40)
        self._rfid_scan_btn.clicked.connect(self._do_rfid_scan)
        layout.addWidget(self._rfid_scan_btn)

        # Result card — 2 column grid
        result_grid = QGridLayout()
        result_grid.setContentsMargins(8, 6, 8, 6)
        result_grid.setHorizontalSpacing(12)
        result_grid.setVerticalSpacing(4)

        def _lbl(text, style=""):
            l = QLabel(text)
            l.setStyleSheet(style or f"font-size: {_F_SM}px; color: {C.TEXT_MUTED};")
            return l

        def _val(text, style=""):
            l = QLabel(text)
            l.setStyleSheet(style or f"font-size: {_F_MED}px; color: {C.TEXT}; font-weight: bold;")
            l.setWordWrap(True)
            return l

        result_grid.addWidget(_lbl("UID:"), 0, 0)
        self._rfid_uid = _val("---", f"font-size: {_F_MED}px; color: {C.PRIMARY}; font-weight: bold; font-family: monospace;")
        result_grid.addWidget(self._rfid_uid, 0, 1)

        result_grid.addWidget(_lbl("Signal:"), 0, 2)
        self._rfid_signal = _val("---")
        result_grid.addWidget(self._rfid_signal, 0, 3)

        result_grid.addWidget(_lbl("PPG Code:"), 1, 0)
        self._rfid_ppg = _val("---")
        result_grid.addWidget(self._rfid_ppg, 1, 1)

        result_grid.addWidget(_lbl("Batch:"), 1, 2)
        self._rfid_batch = _val("---")
        result_grid.addWidget(self._rfid_batch, 1, 3)

        result_grid.addWidget(_lbl("Product:"), 2, 0)
        self._rfid_product = _val("---")
        result_grid.addWidget(self._rfid_product, 2, 1)

        result_grid.addWidget(_lbl("Color:"), 2, 2)
        self._rfid_color = _val("---")
        result_grid.addWidget(self._rfid_color, 2, 3)

        result_card = _card(result_grid)
        layout.addWidget(result_card)

        # History — scrollable
        hist_lbl = QLabel("History")
        hist_lbl.setStyleSheet(f"font-size: {_F_SM}px; color: {C.SECONDARY}; font-weight: bold; padding-top: 2px;")
        layout.addWidget(hist_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._rfid_history_container = QWidget()
        self._rfid_history_layout = QVBoxLayout(self._rfid_history_container)
        self._rfid_history_layout.setContentsMargins(0, 0, 0, 0)
        self._rfid_history_layout.setSpacing(2)
        self._rfid_history_layout.addStretch()
        scroll.setWidget(self._rfid_history_container)
        enable_touch_scroll(scroll)
        layout.addWidget(scroll, stretch=1)

        return tab

    def _do_rfid_scan(self):
        self._rfid_scan_btn.setText("Scanning...")
        self._rfid_scan_btn.setEnabled(False)
        # Process events so the button text updates
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

        try:
            tags = self.app.rfid.poll_tags()
            if tags:
                t = tags[0]
                self._rfid_uid.setText(t.tag_id)
                self._rfid_signal.setText(f"{t.signal_strength}%")
                self._rfid_ppg.setText(t.ppg_code or "---")
                self._rfid_batch.setText(t.batch_number or "---")
                self._rfid_product.setText(t.product_name or "---")
                self._rfid_color.setText(t.color or "---")
                ts = time.strftime("%H:%M:%S")
                self._rfid_history.appendleft(f"{ts} | {t.tag_id} | {t.ppg_code or '?'}")
                self._rebuild_rfid_history()
            else:
                self._rfid_uid.setText("No tag found")
                self._rfid_signal.setText("---")
                self._rfid_ppg.setText("---")
                self._rfid_batch.setText("---")
                self._rfid_product.setText("---")
                self._rfid_color.setText("---")
        except Exception as e:
            self._rfid_uid.setText("ERROR")
            self._rfid_signal.setText(str(e)[:30])

        self._rfid_scan_btn.setText("SCAN NOW")
        self._rfid_scan_btn.setEnabled(True)

    def _rebuild_rfid_history(self):
        while self._rfid_history_layout.count() > 1:
            item = self._rfid_history_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for entry in self._rfid_history:
            lbl = QLabel(entry)
            lbl.setStyleSheet(
                f"font-size: {_F_SM}px; color: {C.TEXT_SEC}; font-family: monospace;"
                f"background: {C.BG_CARD_ALT}; padding: 2px 6px; border-radius: 3px;"
            )
            self._rfid_history_layout.insertWidget(self._rfid_history_layout.count() - 1, lbl)

    # ──────────────────────────────────────────────────
    # LED TAB — 4-column grid, compact
    # ──────────────────────────────────────────────────

    def _build_led_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(_PAD, _PAD, _PAD, _PAD)
        layout.setSpacing(4)

        healthy = False
        try:
            healthy = self.app.led.is_healthy()
        except Exception:
            pass
        layout.addLayout(_hdr_row("LED Indicators", self.app.driver_status.get("led", "fake"), healthy))

        # Slot grid — 4 columns
        slot_grid = QGridLayout()
        slot_grid.setSpacing(4)
        self._led_slot_btns = {}
        slot_count = getattr(self.app, "slot_count", 4)
        cols = 4
        for i in range(slot_count):
            sid = f"shelf1_slot{i + 1}"
            b = QPushButton(f"S{i+1}")
            b.setMinimumHeight(40)
            b.setStyleSheet(self._led_btn_style(LEDColor.OFF))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda checked, s=sid: self._cycle_slot_color(s))
            slot_grid.addWidget(b, i // cols, i % cols)
            self._led_slot_btns[sid] = b
            self._led_slot_colors[sid] = 0

        layout.addLayout(slot_grid)

        # Pattern row
        pat_row = QHBoxLayout()
        pat_row.setSpacing(4)
        self._pattern_btns = {}
        for label, pat in [("SOLID", LEDPattern.SOLID), ("BLINK", LEDPattern.BLINK_SLOW), ("FAST", LEDPattern.BLINK_FAST), ("PULSE", LEDPattern.PULSE)]:
            b = _btn(label, f"QPushButton {{ font-size: {_F_SM}px; padding: 4px 8px; border: 1px solid {C.BORDER}; border-radius: 4px; color: {C.TEXT}; background: {C.BG_CARD}; }}")
            b.setCheckable(True)
            b.setChecked(pat == LEDPattern.SOLID)
            b.clicked.connect(lambda checked, p=pat: self._set_led_pattern(p))
            pat_row.addWidget(b)
            self._pattern_btns[pat] = b
        layout.addLayout(pat_row)

        # ALL ON / OFF
        ctrl = QHBoxLayout()
        ctrl.setSpacing(4)
        on_btn = _btn("ALL ON", f"QPushButton {{ background: {C.SUCCESS_BG}; color: {C.SUCCESS}; border: 1px solid {C.SUCCESS}; border-radius: 6px; font-size: {_F_MED}px; font-weight: bold; padding: 8px; }} QPushButton:hover {{ background: {C.BG_HOVER}; }}")
        on_btn.clicked.connect(self._led_all_on)
        ctrl.addWidget(on_btn)
        off_btn = _btn("ALL OFF", f"QPushButton {{ background: {C.DANGER_BG}; color: {C.DANGER}; border: 1px solid {C.DANGER}; border-radius: 6px; font-size: {_F_MED}px; font-weight: bold; padding: 8px; }} QPushButton:hover {{ background: {C.BG_HOVER}; }}")
        off_btn.clicked.connect(self._led_all_off)
        ctrl.addWidget(off_btn)
        layout.addLayout(ctrl)
        layout.addStretch()

        return tab

    def _led_btn_style(self, color: LEDColor) -> str:
        cmap = {
            LEDColor.OFF: (C.BG_CARD_ALT, C.TEXT_MUTED, C.BORDER),
            LEDColor.GREEN: (C.SUCCESS_BG, C.SUCCESS, C.SUCCESS),
            LEDColor.RED: (C.DANGER_BG, C.DANGER, C.DANGER),
            LEDColor.YELLOW: (C.WARNING_BG, C.WARNING, C.WARNING),
            LEDColor.BLUE: (C.SECONDARY_BG, C.SECONDARY, C.SECONDARY),
            LEDColor.WHITE: ("#1A1A2E", C.TEXT, C.TEXT),
        }
        bg, fg, bd = cmap.get(color, (C.BG_CARD_ALT, C.TEXT_MUTED, C.BORDER))
        return (
            f"QPushButton {{ background: {bg}; color: {fg}; border: 2px solid {bd};"
            f"border-radius: 8px; font-size: {_F_MED}px; font-weight: bold; }}"
        )

    def _cycle_slot_color(self, slot_id):
        idx = (self._led_slot_colors.get(slot_id, 0) + 1) % len(self._color_cycle)
        self._led_slot_colors[slot_id] = idx
        color = self._color_cycle[idx]
        b = self._led_slot_btns[slot_id]
        num = slot_id.split("_")[-1].replace("slot", "S")
        b.setText(f"{num}\n{color.name}" if color != LEDColor.OFF else num)
        b.setStyleSheet(self._led_btn_style(color))
        try:
            if color == LEDColor.OFF:
                self.app.led.clear_slot(slot_id)
            else:
                self.app.led.set_slot(slot_id, color, self._led_current_pattern)
        except Exception:
            pass

    def _set_led_pattern(self, pattern):
        self._led_current_pattern = pattern
        for p, b in self._pattern_btns.items():
            b.setChecked(p == pattern)
        for sid, idx in self._led_slot_colors.items():
            c = self._color_cycle[idx]
            if c != LEDColor.OFF:
                try:
                    self.app.led.set_slot(sid, c, pattern)
                except Exception:
                    pass

    def _led_all_on(self):
        for i in range(getattr(self.app, "slot_count", 4)):
            sid = f"shelf1_slot{i+1}"
            self._led_slot_colors[sid] = self._color_cycle.index(LEDColor.GREEN)
            b = self._led_slot_btns.get(sid)
            if b:
                b.setText(f"S{i+1}\nGREEN")
                b.setStyleSheet(self._led_btn_style(LEDColor.GREEN))
            try:
                self.app.led.set_slot(sid, LEDColor.GREEN, self._led_current_pattern)
            except Exception:
                pass

    def _led_all_off(self):
        try:
            self.app.led.clear_all()
        except Exception:
            pass
        for sid, b in self._led_slot_btns.items():
            self._led_slot_colors[sid] = 0
            num = sid.split("_")[-1].replace("slot", "S")
            b.setText(num)
            b.setStyleSheet(self._led_btn_style(LEDColor.OFF))

    # ──────────────────────────────────────────────────
    # BUZZER TAB — grid of buttons, no cards
    # ──────────────────────────────────────────────────

    def _build_buzzer_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(_PAD, _PAD, _PAD, _PAD)
        layout.setSpacing(6)

        healthy = False
        try:
            healthy = self.app.buzzer.is_healthy()
        except Exception:
            pass
        layout.addLayout(_hdr_row("Buzzer", self.app.driver_status.get("buzzer", "fake"), healthy))

        # Button grid — 3 columns
        grid = QGridLayout()
        grid.setSpacing(6)
        patterns = [
            (BuzzerPattern.CONFIRM, "CONFIRM", "Short beep"),
            (BuzzerPattern.WARNING, "WARNING", "Double beep"),
            (BuzzerPattern.ERROR, "ERROR", "Long buzz"),
            (BuzzerPattern.TARGET_REACHED, "TARGET", "Rising tone"),
            (BuzzerPattern.TICK, "TICK", "Click"),
        ]
        for i, (pat, name, desc) in enumerate(patterns):
            b = _btn(f"{name}\n{desc}",
                f"QPushButton {{ background: {C.ACCENT_BG}; color: {C.ACCENT};"
                f"border: 1px solid {C.ACCENT}; border-radius: 8px;"
                f"font-size: {_F_MED}px; font-weight: bold; padding: 10px 6px; }}"
                f"QPushButton:hover {{ background: {C.BG_HOVER}; }}"
            )
            b.setMinimumHeight(60)
            b.clicked.connect(lambda checked, p=pat: self._play_buzzer(p))
            grid.addWidget(b, i // 3, i % 3)

        layout.addLayout(grid)

        # STOP
        stop = _btn("STOP",
            f"QPushButton {{ background: {C.DANGER_BG}; color: {C.DANGER};"
            f"border: 1px solid {C.DANGER}; border-radius: 8px;"
            f"font-size: {_F_MED}px; font-weight: bold; padding: 12px; }}"
            f"QPushButton:hover {{ background: {C.BG_HOVER}; }}"
        )
        stop.clicked.connect(self._stop_buzzer)
        layout.addWidget(stop)
        layout.addStretch()

        return tab

    def _play_buzzer(self, pattern):
        try:
            self.app.buzzer.play(pattern)
        except Exception as e:
            logger.error(f"Buzzer error: {e}")

    def _stop_buzzer(self):
        try:
            self.app.buzzer.stop()
        except Exception:
            pass

    # ──────────────────────────────────────────────────
    # LIFECYCLE
    # ──────────────────────────────────────────────────

    def on_enter(self):
        self._weight_timer.start()

    def on_leave(self):
        self._weight_timer.stop()
        try:
            self.app.led.clear_all()
        except Exception:
            pass
        try:
            self.app.buzzer.stop()
        except Exception:
            pass
