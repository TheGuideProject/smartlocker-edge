"""
SmartLocker Sensor Testing Screen

QTabWidget with 4 tabs: Weight, RFID, LED, Buzzer.
Each tab provides live testing of the corresponding hardware driver.
"""

import time
import logging
from collections import deque

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTabWidget, QGridLayout, QScrollArea, QSizePolicy,
    QSpacerItem,
)
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QPainterPath

from ui_qt.theme import C, F, S
from hal.interfaces import LEDColor, LEDPattern, BuzzerPattern

logger = logging.getLogger("smartlocker.sensor_test")


# ══════════════════════════════════════════════════════════
# WEIGHT CHART — Custom QPainter line chart
# ══════════════════════════════════════════════════════════

class WeightChartWidget(QWidget):
    """Rolling line chart of the last 50 weight readings using QPainter."""

    MAX_POINTS = 50

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = deque(maxlen=self.MAX_POINTS)
        self.setMinimumHeight(120)
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

        w = self.width()
        h = self.height()
        margin = 8

        # Background
        painter.fillRect(self.rect(), QColor(C.BG_INPUT))

        if len(self._data) < 2:
            painter.setPen(QColor(C.TEXT_MUTED))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Waiting for data...")
            painter.end()
            return

        data = list(self._data)
        min_val = min(data)
        max_val = max(data)
        val_range = max_val - min_val
        if val_range < 1.0:
            val_range = 1.0
            min_val = min_val - 0.5
            max_val = max_val + 0.5

        plot_x = margin
        plot_y = margin
        plot_w = w - margin * 2
        plot_h = h - margin * 2

        # Grid lines
        grid_pen = QPen(QColor(C.BORDER), 1, Qt.PenStyle.DotLine)
        painter.setPen(grid_pen)
        for i in range(5):
            y = plot_y + (plot_h * i / 4)
            painter.drawLine(QPointF(plot_x, y), QPointF(plot_x + plot_w, y))

        # Axis labels
        painter.setPen(QColor(C.TEXT_MUTED))
        label_font = QFont("Segoe UI", 7)
        painter.setFont(label_font)
        painter.drawText(QRectF(0, plot_y - 2, margin + 30, 14),
                         Qt.AlignmentFlag.AlignLeft, f"{max_val:.0f}g")
        painter.drawText(QRectF(0, plot_y + plot_h - 12, margin + 30, 14),
                         Qt.AlignmentFlag.AlignLeft, f"{min_val:.0f}g")

        # Data line
        n = len(data)
        points = []
        for i, val in enumerate(data):
            x = plot_x + (plot_w * i / (n - 1))
            y = plot_y + plot_h - ((val - min_val) / val_range * plot_h)
            points.append(QPointF(x, y))

        # Fill area under the line
        if points:
            fill_path = QPainterPath()
            fill_path.moveTo(QPointF(points[0].x(), plot_y + plot_h))
            for pt in points:
                fill_path.lineTo(pt)
            fill_path.lineTo(QPointF(points[-1].x(), plot_y + plot_h))
            fill_path.closeSubpath()
            fill_color = QColor(C.PRIMARY)
            fill_color.setAlpha(30)
            painter.fillPath(fill_path, fill_color)

        # Draw the line
        line_pen = QPen(QColor(C.PRIMARY), 2)
        painter.setPen(line_pen)
        for i in range(len(points) - 1):
            painter.drawLine(points[i], points[i + 1])

        # Current value dot
        if points:
            last = points[-1]
            painter.setBrush(QColor(C.PRIMARY))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(last, 4, 4)

        painter.end()


# ══════════════════════════════════════════════════════════
# HELPER — create a card frame
# ══════════════════════════════════════════════════════════

def _card(layout=None) -> QFrame:
    """Create a QFrame styled as a card."""
    frame = QFrame()
    frame.setObjectName("card")
    if layout:
        frame.setLayout(layout)
    return frame


def _status_header(driver_name: str, driver_type: str, is_healthy: bool) -> QHBoxLayout:
    """Build a driver status header row: [BADGE] DriverName  [HEALTH DOT]."""
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)

    badge = QLabel(driver_type.upper())
    badge.setObjectName("badge_real" if driver_type == "real" else "badge_fake")
    badge.setFixedHeight(22)
    row.addWidget(badge)

    name_lbl = QLabel(f"  {driver_name}")
    name_lbl.setStyleSheet(f"font-size: {F.H3}px; font-weight: bold; color: {C.TEXT};")
    row.addWidget(name_lbl)

    row.addStretch()

    dot_color = C.SUCCESS if is_healthy else C.DANGER
    dot = QLabel("\u25CF")
    dot.setStyleSheet(f"font-size: 14px; color: {dot_color};")
    row.addWidget(dot)

    status_text = "Healthy" if is_healthy else "Unhealthy"
    status_lbl = QLabel(status_text)
    status_lbl.setStyleSheet(f"font-size: {F.SMALL}px; color: {dot_color};")
    row.addWidget(status_lbl)

    return row


def _action_btn(text: str, obj_name: str = "") -> QPushButton:
    btn = QPushButton(text)
    if obj_name:
        btn.setObjectName(obj_name)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


# ══════════════════════════════════════════════════════════
# MAIN SCREEN
# ══════════════════════════════════════════════════════════

class SensorTestScreen(QWidget):
    """Sensor testing screen with 4 hardware tabs."""

    def __init__(self, app):
        super().__init__()
        self.app = app

        # State
        self._weight_timer = QTimer()
        self._weight_timer.setInterval(300)
        self._weight_timer.timeout.connect(self._update_weight)

        self._active_channel = None
        self._led_slot_colors = {}       # slot_id -> LEDColor index
        self._led_current_pattern = LEDPattern.SOLID
        self._rfid_history = deque(maxlen=10)

        # Color cycling order
        self._color_cycle = [
            LEDColor.OFF, LEDColor.GREEN, LEDColor.RED,
            LEDColor.YELLOW, LEDColor.BLUE, LEDColor.WHITE,
        ]

        self._build_ui()

    # ──────────────────────────────────────────────────
    # UI CONSTRUCTION
    # ──────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
        root.setSpacing(S.GAP)

        # Top bar
        top = QHBoxLayout()
        self._back_btn = _action_btn("\u2190  Back", "ghost")
        self._back_btn.clicked.connect(self.app.go_back)
        top.addWidget(self._back_btn)

        title = QLabel("Sensor Testing")
        title.setObjectName("title")
        top.addWidget(title)
        top.addStretch()

        self._mode_lbl = QLabel(self.app.mode.upper())
        self._mode_lbl.setObjectName(
            "badge_real" if self.app.mode in ("live", "hybrid") else "badge_fake"
        )
        top.addWidget(self._mode_lbl)
        root.addLayout(top)

        # Tab widget
        self._tabs = QTabWidget()
        root.addWidget(self._tabs, stretch=1)

        self._tabs.addTab(self._build_weight_tab(), "\u2696  Weight")
        self._tabs.addTab(self._build_rfid_tab(), "\U0001F4F6  RFID")
        self._tabs.addTab(self._build_led_tab(), "\U0001F4A1  LED")
        self._tabs.addTab(self._build_buzzer_tab(), "\U0001F50A  Buzzer")

    # ──────────────────────────────────────────────────
    # WEIGHT TAB
    # ──────────────────────────────────────────────────

    def _build_weight_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
        layout.setSpacing(S.GAP)

        # Status header
        healthy = False
        try:
            healthy = self.app.weight.is_healthy()
        except Exception:
            pass
        hdr = _status_header(
            "Weight Sensor (HX711)",
            self.app.driver_status.get("weight", "fake"),
            healthy,
        )
        self._weight_health_row = hdr
        layout.addLayout(hdr)

        # Channel selector
        chan_row = QHBoxLayout()
        chan_label = QLabel("Channel:")
        chan_label.setStyleSheet(f"font-size: {F.BODY}px; color: {C.TEXT_SEC};")
        chan_row.addWidget(chan_label)

        self._channel_btns = {}
        channels = []
        try:
            channels = self.app.weight.get_channels()
        except Exception:
            channels = ["shelf1", "mixing_scale"]

        for ch in channels:
            btn = _action_btn(ch)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, c=ch: self._select_channel(c))
            chan_row.addWidget(btn)
            self._channel_btns[ch] = btn

        chan_row.addStretch()
        layout.addLayout(chan_row)

        # Select first channel by default
        if channels:
            self._active_channel = channels[0]
            self._channel_btns[channels[0]].setChecked(True)

        # Main reading card
        reading_layout = QVBoxLayout()
        reading_layout.setSpacing(4)

        # Grams display
        self._weight_grams = QLabel("---")
        self._weight_grams.setObjectName("hero")
        self._weight_grams.setAlignment(Qt.AlignmentFlag.AlignCenter)
        reading_layout.addWidget(self._weight_grams)

        # Kg display
        self._weight_kg = QLabel("--- kg")
        self._weight_kg.setStyleSheet(
            f"font-size: {F.H2}px; color: {C.TEXT_SEC};"
        )
        self._weight_kg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        reading_layout.addWidget(self._weight_kg)

        # Stability indicator
        stab_row = QHBoxLayout()
        stab_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stability_dot = QLabel("\u25CF")
        self._stability_dot.setStyleSheet(f"font-size: 14px; color: {C.WARNING};")
        stab_row.addWidget(self._stability_dot)
        self._stability_text = QLabel("WAITING")
        self._stability_text.setStyleSheet(
            f"font-size: {F.SMALL}px; font-weight: bold; color: {C.WARNING};"
        )
        stab_row.addWidget(self._stability_text)
        reading_layout.addLayout(stab_row)

        # Raw ADC
        self._weight_raw = QLabel("RAW ADC: ---")
        self._weight_raw.setStyleSheet(
            f"font-size: {F.TINY}px; color: {C.TEXT_MUTED};"
        )
        self._weight_raw.setAlignment(Qt.AlignmentFlag.AlignCenter)
        reading_layout.addWidget(self._weight_raw)

        reading_card = _card(reading_layout)
        layout.addWidget(reading_card)

        # Chart
        self._weight_chart = WeightChartWidget()
        layout.addWidget(self._weight_chart, stretch=1)

        # Action buttons
        btn_row = QHBoxLayout()

        self._tare_btn = _action_btn("TARE  (Zero)", "primary")
        self._tare_btn.clicked.connect(self._do_tare)
        btn_row.addWidget(self._tare_btn)

        self._calibrate_btn = _action_btn("CALIBRATE", "secondary")
        self._calibrate_btn.clicked.connect(self._do_calibrate)
        btn_row.addWidget(self._calibrate_btn)

        self._clear_chart_btn = _action_btn("Clear Chart", "ghost")
        self._clear_chart_btn.clicked.connect(self._weight_chart.clear_data)
        btn_row.addWidget(self._clear_chart_btn)

        layout.addLayout(btn_row)

        return tab

    def _select_channel(self, channel: str):
        self._active_channel = channel
        for ch, btn in self._channel_btns.items():
            btn.setChecked(ch == channel)
        self._weight_chart.clear_data()

    def _update_weight(self):
        if not self._active_channel:
            return
        try:
            reading = self.app.weight.read_weight(self._active_channel)
            grams = reading.grams
            kg = grams / 1000.0
            stable = reading.stable
            raw = reading.raw_value

            self._weight_grams.setText(f"{grams:.1f} g")
            self._weight_kg.setText(f"{kg:.3f} kg")
            self._weight_raw.setText(f"RAW ADC: {raw}")

            if stable:
                self._stability_dot.setStyleSheet(f"font-size: 14px; color: {C.SUCCESS};")
                self._stability_text.setText("STABLE")
                self._stability_text.setStyleSheet(
                    f"font-size: {F.SMALL}px; font-weight: bold; color: {C.SUCCESS};"
                )
            else:
                self._stability_dot.setStyleSheet(f"font-size: 14px; color: {C.WARNING};")
                self._stability_text.setText("SETTLING...")
                self._stability_text.setStyleSheet(
                    f"font-size: {F.SMALL}px; font-weight: bold; color: {C.WARNING};"
                )

            self._weight_chart.add_point(grams)

        except Exception as e:
            self._weight_grams.setText("ERR")
            self._weight_kg.setText("---")
            self._weight_raw.setText(f"Error: {e}")
            self._stability_dot.setStyleSheet(f"font-size: 14px; color: {C.DANGER};")
            self._stability_text.setText("ERROR")
            self._stability_text.setStyleSheet(
                f"font-size: {F.SMALL}px; font-weight: bold; color: {C.DANGER};"
            )

    def _do_tare(self):
        if not self._active_channel:
            return
        try:
            ok = self.app.weight.tare(self._active_channel)
            if ok:
                self._tare_btn.setText("TARED!")
                self._weight_chart.clear_data()
                QTimer.singleShot(1500, lambda: self._tare_btn.setText("TARE  (Zero)"))
            else:
                self._tare_btn.setText("TARE FAILED")
                QTimer.singleShot(1500, lambda: self._tare_btn.setText("TARE  (Zero)"))
        except Exception as e:
            logger.error(f"Tare error: {e}")
            self._tare_btn.setText("TARE ERROR")
            QTimer.singleShot(1500, lambda: self._tare_btn.setText("TARE  (Zero)"))

    def _do_calibrate(self):
        # Placeholder — show message in the button
        self._calibrate_btn.setText("Coming Soon...")
        QTimer.singleShot(2000, lambda: self._calibrate_btn.setText("CALIBRATE"))

    # ──────────────────────────────────────────────────
    # RFID TAB
    # ──────────────────────────────────────────────────

    def _build_rfid_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
        layout.setSpacing(S.GAP)

        # Status header
        healthy = False
        try:
            healthy = self.app.rfid.is_healthy()
        except Exception:
            pass
        hdr = _status_header(
            "RFID / NFC Reader",
            self.app.driver_status.get("rfid", "fake"),
            healthy,
        )
        layout.addLayout(hdr)

        # Scan button
        self._rfid_scan_btn = _action_btn("\U0001F4E1  SCAN NOW", "primary")
        self._rfid_scan_btn.clicked.connect(self._do_rfid_scan)
        layout.addWidget(self._rfid_scan_btn)

        # Current tag card
        tag_layout = QVBoxLayout()
        tag_layout.setSpacing(4)

        tag_title = QLabel("Last Detected Tag")
        tag_title.setObjectName("section")
        tag_layout.addWidget(tag_title)

        self._rfid_uid = QLabel("No tag scanned")
        self._rfid_uid.setStyleSheet(
            f"font-size: {F.H1}px; font-weight: bold; color: {C.PRIMARY}; "
            f"font-family: 'Consolas', 'Courier New', monospace;"
        )
        self._rfid_uid.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._rfid_uid.setWordWrap(True)
        tag_layout.addWidget(self._rfid_uid)

        self._rfid_signal = QLabel("Signal: ---")
        self._rfid_signal.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.TEXT_SEC};"
        )
        self._rfid_signal.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tag_layout.addWidget(self._rfid_signal)

        # Product data
        prod_title = QLabel("Product Data")
        prod_title.setObjectName("section")
        tag_layout.addWidget(prod_title)

        self._rfid_ppg = QLabel("PPG Code: ---")
        self._rfid_ppg.setStyleSheet(f"font-size: {F.BODY}px; color: {C.TEXT};")
        tag_layout.addWidget(self._rfid_ppg)

        self._rfid_product = QLabel("Product: ---")
        self._rfid_product.setStyleSheet(f"font-size: {F.BODY}px; color: {C.TEXT};")
        tag_layout.addWidget(self._rfid_product)

        self._rfid_color = QLabel("Color: ---")
        self._rfid_color.setStyleSheet(f"font-size: {F.BODY}px; color: {C.TEXT};")
        tag_layout.addWidget(self._rfid_color)

        tag_card = _card(tag_layout)
        layout.addWidget(tag_card)

        # History
        hist_title = QLabel("Scan History (last 10)")
        hist_title.setObjectName("section")
        layout.addWidget(hist_title)

        # Scrollable history list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._rfid_history_container = QWidget()
        self._rfid_history_layout = QVBoxLayout(self._rfid_history_container)
        self._rfid_history_layout.setContentsMargins(0, 0, 0, 0)
        self._rfid_history_layout.setSpacing(4)
        self._rfid_history_layout.addStretch()
        scroll.setWidget(self._rfid_history_container)

        layout.addWidget(scroll, stretch=1)

        return tab

    def _do_rfid_scan(self):
        self._rfid_scan_btn.setText("Scanning...")
        self._rfid_scan_btn.setEnabled(False)

        try:
            tags = self.app.rfid.poll_tags()
            if tags:
                tag = tags[0]
                self._rfid_uid.setText(tag.tag_id)
                self._rfid_signal.setText(f"Signal: {tag.signal_strength}%")

                ppg = tag.ppg_code or (
                    tag.product_data.split("/")[0] if tag.product_data else "---"
                )
                product = tag.product_name or "---"
                color = tag.color or "---"

                self._rfid_ppg.setText(f"PPG Code: {ppg}")
                self._rfid_product.setText(f"Product: {product}")
                self._rfid_color.setText(f"Color: {color}")

                # Add to history
                ts = time.strftime("%H:%M:%S")
                self._rfid_history.appendleft(
                    f"{ts}  |  {tag.tag_id}  |  {ppg}"
                )
                self._rebuild_rfid_history()
            else:
                self._rfid_uid.setText("No tag found")
                self._rfid_signal.setText("Signal: ---")
                self._rfid_ppg.setText("PPG Code: ---")
                self._rfid_product.setText("Product: ---")
                self._rfid_color.setText("Color: ---")
        except Exception as e:
            logger.error(f"RFID scan error: {e}")
            self._rfid_uid.setText("SCAN ERROR")
            self._rfid_signal.setText(f"Error: {e}")

        self._rfid_scan_btn.setText("\U0001F4E1  SCAN NOW")
        self._rfid_scan_btn.setEnabled(True)

    def _rebuild_rfid_history(self):
        # Clear existing items (except the stretch)
        while self._rfid_history_layout.count() > 1:
            item = self._rfid_history_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        for entry in self._rfid_history:
            lbl = QLabel(entry)
            lbl.setStyleSheet(
                f"font-size: {F.TINY}px; color: {C.TEXT_SEC}; "
                f"font-family: 'Consolas', monospace; "
                f"background-color: {C.BG_CARD_ALT}; "
                f"padding: 4px 8px; border-radius: 4px;"
            )
            self._rfid_history_layout.insertWidget(
                self._rfid_history_layout.count() - 1, lbl
            )

    # ──────────────────────────────────────────────────
    # LED TAB
    # ──────────────────────────────────────────────────

    def _build_led_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
        layout.setSpacing(S.GAP)

        # Status header
        healthy = False
        try:
            healthy = self.app.led.is_healthy()
        except Exception:
            pass
        hdr = _status_header(
            "LED Slot Indicators",
            self.app.driver_status.get("led", "fake"),
            healthy,
        )
        layout.addLayout(hdr)

        # Slot buttons grid
        slot_title = QLabel("Slot Colors (click to cycle)")
        slot_title.setObjectName("section")
        layout.addWidget(slot_title)

        slot_grid = QGridLayout()
        slot_grid.setSpacing(S.GAP)
        self._led_slot_btns = {}

        slot_count = getattr(self.app, "slot_count", 4)
        for i in range(slot_count):
            slot_id = f"shelf1_slot{i + 1}"
            btn = QPushButton(f"S{i + 1}\nOFF")
            btn.setMinimumHeight(80)
            btn.setStyleSheet(self._led_btn_style(LEDColor.OFF))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, sid=slot_id: self._cycle_slot_color(sid))
            row = i // 2
            col = i % 2
            slot_grid.addWidget(btn, row, col)
            self._led_slot_btns[slot_id] = btn
            self._led_slot_colors[slot_id] = 0  # index into _color_cycle

        slot_card_layout = QVBoxLayout()
        slot_card_layout.addLayout(slot_grid)
        slot_card = _card(slot_card_layout)
        layout.addWidget(slot_card)

        # Pattern selector
        pat_title = QLabel("Pattern")
        pat_title.setObjectName("section")
        layout.addWidget(pat_title)

        pat_row = QHBoxLayout()
        self._pattern_btns = {}
        patterns = [
            ("SOLID", LEDPattern.SOLID),
            ("BLINK", LEDPattern.BLINK_SLOW),
            ("FAST", LEDPattern.BLINK_FAST),
            ("PULSE", LEDPattern.PULSE),
        ]
        for label, pat in patterns:
            btn = _action_btn(label)
            btn.setCheckable(True)
            btn.setChecked(pat == LEDPattern.SOLID)
            btn.clicked.connect(lambda checked, p=pat: self._set_led_pattern(p))
            pat_row.addWidget(btn)
            self._pattern_btns[pat] = btn
        layout.addLayout(pat_row)

        # ALL ON / ALL OFF
        ctrl_row = QHBoxLayout()
        all_on_btn = _action_btn("ALL ON", "success")
        all_on_btn.clicked.connect(self._led_all_on)
        ctrl_row.addWidget(all_on_btn)

        all_off_btn = _action_btn("ALL OFF", "danger")
        all_off_btn.clicked.connect(self._led_all_off)
        ctrl_row.addWidget(all_off_btn)
        layout.addLayout(ctrl_row)

        layout.addStretch()

        return tab

    def _led_btn_style(self, color: LEDColor) -> str:
        """Return stylesheet for a slot button based on LED color."""
        color_map = {
            LEDColor.OFF: (C.BG_CARD_ALT, C.TEXT_MUTED, C.BORDER),
            LEDColor.GREEN: (C.SUCCESS_BG, C.SUCCESS, C.SUCCESS),
            LEDColor.RED: (C.DANGER_BG, C.DANGER, C.DANGER),
            LEDColor.YELLOW: (C.WARNING_BG, C.WARNING, C.WARNING),
            LEDColor.BLUE: (C.SECONDARY_BG, C.SECONDARY, C.SECONDARY),
            LEDColor.WHITE: ("#1A1A2E", C.TEXT, C.TEXT),
        }
        bg, fg, border = color_map.get(color, (C.BG_CARD_ALT, C.TEXT_MUTED, C.BORDER))
        return (
            f"QPushButton {{ background-color: {bg}; color: {fg}; "
            f"border: 2px solid {border}; border-radius: 10px; "
            f"font-size: {F.H3}px; font-weight: bold; }}"
        )

    def _cycle_slot_color(self, slot_id: str):
        idx = self._led_slot_colors.get(slot_id, 0)
        idx = (idx + 1) % len(self._color_cycle)
        self._led_slot_colors[slot_id] = idx
        color = self._color_cycle[idx]

        btn = self._led_slot_btns[slot_id]
        short_id = slot_id.split("_")[-1].upper()
        btn.setText(f"{short_id}\n{color.name}")
        btn.setStyleSheet(self._led_btn_style(color))

        try:
            if color == LEDColor.OFF:
                self.app.led.clear_slot(slot_id)
            else:
                self.app.led.set_slot(slot_id, color, self._led_current_pattern)
        except Exception as e:
            logger.error(f"LED set_slot error: {e}")

    def _set_led_pattern(self, pattern: LEDPattern):
        self._led_current_pattern = pattern
        for pat, btn in self._pattern_btns.items():
            btn.setChecked(pat == pattern)

        # Re-apply current colors with new pattern
        for slot_id, idx in self._led_slot_colors.items():
            color = self._color_cycle[idx]
            if color != LEDColor.OFF:
                try:
                    self.app.led.set_slot(slot_id, color, pattern)
                except Exception as e:
                    logger.error(f"LED pattern update error: {e}")

    def _led_all_on(self):
        slot_count = getattr(self.app, "slot_count", 4)
        for i in range(slot_count):
            slot_id = f"shelf1_slot{i + 1}"
            color = LEDColor.GREEN
            self._led_slot_colors[slot_id] = self._color_cycle.index(color)
            btn = self._led_slot_btns.get(slot_id)
            if btn:
                short_id = slot_id.split("_")[-1].upper()
                btn.setText(f"{short_id}\n{color.name}")
                btn.setStyleSheet(self._led_btn_style(color))
            try:
                self.app.led.set_slot(slot_id, color, self._led_current_pattern)
            except Exception as e:
                logger.error(f"LED all_on error: {e}")

    def _led_all_off(self):
        try:
            self.app.led.clear_all()
        except Exception as e:
            logger.error(f"LED clear_all error: {e}")

        for slot_id, btn in self._led_slot_btns.items():
            self._led_slot_colors[slot_id] = 0
            short_id = slot_id.split("_")[-1].upper()
            btn.setText(f"{short_id}\nOFF")
            btn.setStyleSheet(self._led_btn_style(LEDColor.OFF))

    # ──────────────────────────────────────────────────
    # BUZZER TAB
    # ──────────────────────────────────────────────────

    def _build_buzzer_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
        layout.setSpacing(S.GAP)

        # Status header
        healthy = False
        try:
            healthy = self.app.buzzer.is_healthy()
        except Exception:
            pass
        hdr = _status_header(
            "Buzzer / Audio",
            self.app.driver_status.get("buzzer", "fake"),
            healthy,
        )
        layout.addLayout(hdr)

        # Pattern buttons
        patterns_info = [
            (BuzzerPattern.CONFIRM, "CONFIRM", "Single short beep — action confirmed"),
            (BuzzerPattern.WARNING, "WARNING", "Double beep — attention needed"),
            (BuzzerPattern.ERROR, "ERROR", "Long continuous buzz — something wrong"),
            (BuzzerPattern.TARGET_REACHED, "TARGET", "Rising tone — pour target reached"),
            (BuzzerPattern.TICK, "TICK", "Very short click — weight change ack"),
        ]

        for pattern, name, desc in patterns_info:
            btn_layout = QHBoxLayout()

            btn = _action_btn(f"\u266B  {name}", "accent")
            btn.setMinimumHeight(S.BTN_H)
            btn.clicked.connect(lambda checked, p=pattern: self._play_buzzer(p))
            btn_layout.addWidget(btn, stretch=1)

            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet(
                f"font-size: {F.SMALL}px; color: {C.TEXT_SEC}; padding-left: 8px;"
            )
            desc_lbl.setWordWrap(True)
            desc_lbl.setMinimumWidth(180)
            btn_layout.addWidget(desc_lbl, stretch=1)

            card_layout = QHBoxLayout()
            card_layout.setContentsMargins(S.PAD_CARD, S.PAD_CARD, S.PAD_CARD, S.PAD_CARD)
            card_layout.addLayout(btn_layout)
            card = _card(card_layout)
            layout.addWidget(card)

        # STOP button
        stop_btn = _action_btn("\u23F9  STOP", "danger")
        stop_btn.setMinimumHeight(S.BTN_H_LG)
        stop_btn.clicked.connect(self._stop_buzzer)
        layout.addWidget(stop_btn)

        layout.addStretch()

        return tab

    def _play_buzzer(self, pattern: BuzzerPattern):
        try:
            self.app.buzzer.play(pattern)
        except Exception as e:
            logger.error(f"Buzzer play error: {e}")

    def _stop_buzzer(self):
        try:
            self.app.buzzer.stop()
        except Exception as e:
            logger.error(f"Buzzer stop error: {e}")

    # ──────────────────────────────────────────────────
    # LIFECYCLE
    # ──────────────────────────────────────────────────

    def on_enter(self):
        """Called when this screen becomes active."""
        self._weight_timer.start()

    def on_leave(self):
        """Called when navigating away from this screen."""
        self._weight_timer.stop()

        # Clean up LEDs
        try:
            self.app.led.clear_all()
        except Exception:
            pass

        # Stop buzzer
        try:
            self.app.buzzer.stop()
        except Exception:
            pass
