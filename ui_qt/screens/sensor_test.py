"""
SmartLocker Sensor Testing Screen -- optimized for 800x480 4.3" touch

QTabWidget with 4 tabs: Weight, RFID, LED, Buzzer.
Professional card-based layout with icon system integration.
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
from ui_qt.icons import Icon, icon_badge, icon_label, status_dot, type_badge, section_header, screen_header
from hal.interfaces import LEDColor, LEDPattern, BuzzerPattern

logger = logging.getLogger("smartlocker.sensor_test")


# ================================================================
# WEIGHT CHART
# ================================================================

class WeightChartWidget(QWidget):
    """Rolling line chart of weight readings with axis labels."""
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
        left_margin = 48
        m_top = 8
        m_right = 8
        m_bottom = 20
        painter.fillRect(self.rect(), QColor(C.BG_INPUT))

        if len(self._data) < 2:
            painter.setPen(QColor(C.TEXT_MUTED))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Waiting for data...")
            painter.end()
            return

        data = list(self._data)
        mn, mx = min(data), max(data)
        rng = mx - mn
        if rng < 1.0:
            rng = 1.0
            mn -= 0.5
            mx += 0.5

        pw = w - left_margin - m_right
        ph = h - m_top - m_bottom

        # Grid lines (3 horizontal)
        painter.setPen(QPen(QColor(C.BORDER), 1, Qt.PenStyle.DotLine))
        for i in range(3):
            y = m_top + (ph * i / 2)
            painter.drawLine(QPointF(left_margin, y), QPointF(left_margin + pw, y))

        # Y-axis labels
        painter.setPen(QColor(C.TEXT_MUTED))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(QRectF(0, m_top - 6, left_margin - 4, 14),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                         f"{mx / 1000:.2f}")
        mid_val = (mx + mn) / 2
        painter.drawText(QRectF(0, m_top + ph / 2 - 7, left_margin - 4, 14),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                         f"{mid_val / 1000:.2f}")
        painter.drawText(QRectF(0, m_top + ph - 6, left_margin - 4, 14),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                         f"{mn / 1000:.2f}")

        # X-axis label
        painter.drawText(QRectF(left_margin, h - m_bottom + 4, pw, m_bottom - 2),
                         Qt.AlignmentFlag.AlignCenter, "kg")

        # Data line + fill
        n = len(data)
        pts = [QPointF(left_margin + pw * i / (n - 1),
                        m_top + ph - (v - mn) / rng * ph)
               for i, v in enumerate(data)]

        fill = QPainterPath()
        fill.moveTo(QPointF(pts[0].x(), m_top + ph))
        for p in pts:
            fill.lineTo(p)
        fill.lineTo(QPointF(pts[-1].x(), m_top + ph))
        fill.closeSubpath()
        fc = QColor(C.PRIMARY)
        fc.setAlpha(30)
        painter.fillPath(fill, fc)

        painter.setPen(QPen(QColor(C.PRIMARY), 2))
        for i in range(len(pts) - 1):
            painter.drawLine(pts[i], pts[i + 1])

        # Current point dot
        painter.setBrush(QColor(C.PRIMARY))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(pts[-1], 4, 4)
        painter.end()


# ================================================================
# HELPERS
# ================================================================

def _card(layout=None, accent_color=None) -> QFrame:
    """Create a styled card with optional left border accent."""
    f = QFrame()
    f.setObjectName("card")
    if accent_color:
        f.setStyleSheet(
            f"QFrame#card {{ border-left: 4px solid {accent_color}; }}"
        )
    if layout:
        f.setLayout(layout)
    return f


def _btn(text: str, obj_name: str = "") -> QPushButton:
    """Create a button with an objectName style."""
    b = QPushButton(text)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if obj_name:
        b.setObjectName(obj_name)
    return b


def _toggle_btn(text: str, active: bool = False) -> QPushButton:
    """Create a styled toggle button for channel/pattern selectors."""
    b = QPushButton(text)
    b.setCheckable(True)
    b.setChecked(active)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton {{"
        f"  font-size: {F.SMALL}px; padding: 6px 14px;"
        f"  border: 1px solid {C.BORDER}; border-radius: 6px;"
        f"  color: {C.TEXT_SEC}; background: {C.BG_CARD};"
        f"  font-weight: bold;"
        f"}}"
        f"QPushButton:checked {{"
        f"  background: {C.PRIMARY_BG}; color: {C.PRIMARY};"
        f"  border-color: {C.PRIMARY};"
        f"}}"
        f"QPushButton:hover:!checked {{"
        f"  background: {C.BG_HOVER}; border-color: {C.BORDER_HOVER};"
        f"}}"
    )
    return b


# ================================================================
# MAIN SCREEN
# ================================================================

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
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Screen header
        header_frame, header_layout = screen_header(
            self.app, "SENSOR TEST", Icon.SENSORS, C.ACCENT
        )
        # Mode badge in header
        mode = self.app.mode.upper()
        is_real = self.app.mode != "test"
        mode_badge = type_badge(mode, "success" if is_real else "muted")
        header_layout.addWidget(mode_badge)
        root.addWidget(header_frame)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            f"QTabBar::tab {{ padding: 8px 16px; font-size: {F.SMALL}px; min-width: 80px; }}"
        )
        root.addWidget(self._tabs, stretch=1)

        self._tabs.addTab(self._build_weight_tab(), f"{Icon.WEIGHT} Weight")
        self._tabs.addTab(self._build_rfid_tab(), f"{Icon.TAG} RFID")
        self._tabs.addTab(self._build_led_tab(), f"{Icon.DOT} LED")
        self._tabs.addTab(self._build_buzzer_tab(), f"{Icon.ALARM} Buzzer")

    # ----------------------------------------------------------------
    # WEIGHT TAB
    # ----------------------------------------------------------------

    def _build_weight_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(S.PAD, S.GAP, S.PAD, S.GAP)
        layout.setSpacing(S.GAP)

        # Driver info row
        drv_row = QHBoxLayout()
        drv_row.setSpacing(S.GAP)
        drv_type = self.app.driver_status.get("weight", "fake")
        drv_badge = type_badge(drv_type.upper(), "success" if drv_type in ("real", "socket") else "muted")
        drv_row.addWidget(drv_badge)
        self._weight_health_dot = status_dot(False, size=12)
        drv_row.addWidget(self._weight_health_dot)
        self._weight_health_lbl = QLabel("Checking...")
        self._weight_health_lbl.setStyleSheet(
            f"font-size: {F.SMALL}px; font-weight: bold; color: {C.TEXT_MUTED};"
        )
        drv_row.addWidget(self._weight_health_lbl)
        drv_row.addStretch()
        layout.addLayout(drv_row)

        # Channel selector
        chan_row = QHBoxLayout()
        chan_row.setSpacing(S.GAP)
        chan_lbl = QLabel("CHANNEL")
        chan_lbl.setStyleSheet(
            f"font-size: {F.TINY}px; color: {C.TEXT_MUTED};"
            f"font-weight: bold; letter-spacing: 1px;"
        )
        chan_row.addWidget(chan_lbl)
        self._channel_btns = {}
        channels = []
        try:
            channels = self.app.weight.get_channels()
        except Exception:
            channels = ["shelf1", "mixing_scale"]
        for ch in channels:
            b = _toggle_btn(ch)
            b.clicked.connect(lambda checked, c=ch: self._select_channel(c))
            chan_row.addWidget(b)
            self._channel_btns[ch] = b
        chan_row.addStretch()
        layout.addLayout(chan_row)
        if channels:
            self._active_channel = channels[0]
            self._channel_btns[channels[0]].setChecked(True)

        # Main area: reading card (left) + chart (right)
        main_row = QHBoxLayout()
        main_row.setSpacing(S.GAP)

        # Weight reading card
        read_lay = QVBoxLayout()
        read_lay.setSpacing(2)
        read_lay.setContentsMargins(S.PAD, S.GAP, S.PAD, S.GAP)

        self._weight_main = QLabel("--- kg")
        self._weight_main.setStyleSheet(
            f"font-size: {F.H1}px; font-weight: bold; color: {C.PRIMARY};"
        )
        self._weight_main.setAlignment(Qt.AlignmentFlag.AlignCenter)
        read_lay.addWidget(self._weight_main)

        # Stability badge
        stab_row = QHBoxLayout()
        stab_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stability_badge = type_badge("WAITING", "warning")
        stab_row.addWidget(self._stability_badge)
        read_lay.addLayout(stab_row)

        # Secondary info (grams + raw)
        self._weight_grams = QLabel("--- g")
        self._weight_grams.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.TEXT_SEC};"
        )
        self._weight_grams.setAlignment(Qt.AlignmentFlag.AlignCenter)
        read_lay.addWidget(self._weight_grams)

        self._weight_raw = QLabel("RAW: ---")
        self._weight_raw.setStyleSheet(
            f"font-size: {F.TINY}px; color: {C.TEXT_MUTED};"
        )
        self._weight_raw.setAlignment(Qt.AlignmentFlag.AlignCenter)
        read_lay.addWidget(self._weight_raw)

        read_card = _card(read_lay, accent_color=C.PRIMARY)
        read_card.setFixedWidth(220)
        main_row.addWidget(read_card)

        # Chart
        self._weight_chart = WeightChartWidget()
        main_row.addWidget(self._weight_chart, stretch=1)

        layout.addLayout(main_row, stretch=1)

        # Action buttons row (full width)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(S.GAP)

        self._tare_btn = _btn(f"{Icon.REFRESH}  TARE", "primary")
        self._tare_btn.setFixedHeight(44)
        self._tare_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {C.PRIMARY}; color: {C.BG_DARK};"
            f"  border: none; border-radius: 8px;"
            f"  font-size: {F.BODY}px; font-weight: bold;"
            f"  min-height: 44px;"
            f"}}"
            f"QPushButton:hover {{ background-color: {C.PRIMARY_DIM}; }}"
        )
        self._tare_btn.clicked.connect(self._do_tare)
        btn_row.addWidget(self._tare_btn, stretch=1)

        self._calibrate_btn = _btn(f"{Icon.SETTINGS}  CALIBRATE", "secondary")
        self._calibrate_btn.setFixedHeight(44)
        self._calibrate_btn.clicked.connect(self._do_calibrate)
        btn_row.addWidget(self._calibrate_btn, stretch=1)

        self._clear_btn = _btn("CLEAR", "ghost")
        self._clear_btn.setFixedHeight(44)
        self._clear_btn.clicked.connect(self._weight_chart.clear_data)
        btn_row.addWidget(self._clear_btn, stretch=1)

        layout.addLayout(btn_row)

        return tab

    def _select_channel(self, channel):
        self._active_channel = channel
        for ch, b in self._channel_btns.items():
            b.setChecked(ch == channel)
        self._weight_chart.clear_data()

    def _update_health_indicators(self):
        """Refresh health dots for all sensor tabs (called every 300ms)."""
        # Weight health
        try:
            w_ok = self.app.weight.is_healthy()
        except Exception:
            w_ok = False
        self._weight_health_dot.setStyleSheet(
            f"background-color: {C.SUCCESS if w_ok else C.DANGER};"
            f"border-radius: 6px; border: none;"
        )
        self._weight_health_lbl.setText("Healthy" if w_ok else "Offline")
        self._weight_health_lbl.setStyleSheet(
            f"font-size: {F.SMALL}px; font-weight: bold;"
            f"color: {C.SUCCESS if w_ok else C.DANGER};"
        )

        # RFID health
        try:
            r_ok = self.app.rfid.is_healthy()
        except Exception:
            r_ok = False
        self._rfid_health_dot.setStyleSheet(
            f"background-color: {C.SUCCESS if r_ok else C.DANGER};"
            f"border-radius: 6px; border: none;"
        )
        # Update reader count label if multi-reader
        try:
            if hasattr(self.app.rfid, 'get_healthy_count'):
                h, t = self.app.rfid.get_healthy_count()
                self._rfid_health_lbl.setText(f"PN532 Multi ({h}/{t} readers)")
        except Exception:
            pass

    def _update_weight(self):
        self._update_health_indicators()
        if not self._active_channel:
            return
        try:
            r = self.app.weight.read_weight(self._active_channel)
            self._weight_main.setText(f"{r.grams / 1000:.2f} kg")
            self._weight_grams.setText(f"{r.grams:.0f} g")
            self._weight_raw.setText(f"RAW: {r.raw_value}")

            # Update stability badge
            old_badge = self._stability_badge
            parent_layout = old_badge.parent().layout() if old_badge.parent() else None

            if r.stable:
                self._stability_badge.setText("STABLE")
                self._stability_badge.setStyleSheet(
                    f"background-color: {C.SUCCESS_BG}; color: {C.SUCCESS};"
                    f"border: 1px solid {C.SUCCESS}; border-radius: 4px;"
                    f"padding: 2px 8px; font-size: {F.TINY}px; font-weight: bold;"
                )
            else:
                self._stability_badge.setText("UNSTABLE")
                self._stability_badge.setStyleSheet(
                    f"background-color: {C.WARNING_BG}; color: {C.WARNING};"
                    f"border: 1px solid {C.WARNING}; border-radius: 4px;"
                    f"padding: 2px 8px; font-size: {F.TINY}px; font-weight: bold;"
                )

            self._weight_chart.add_point(r.grams)
        except Exception as e:
            self._weight_main.setText("ERR")
            self._weight_raw.setText(str(e)[:30])

    def _do_tare(self):
        if not self._active_channel:
            return
        try:
            self.app.weight.tare(self._active_channel)
            self._tare_btn.setText(f"{Icon.OK}  OK!")
            self._weight_chart.clear_data()
            QTimer.singleShot(1000, lambda: self._tare_btn.setText(f"{Icon.REFRESH}  TARE"))
        except Exception:
            self._tare_btn.setText(f"{Icon.ERROR}  FAIL")
            QTimer.singleShot(1000, lambda: self._tare_btn.setText(f"{Icon.REFRESH}  TARE"))

    def _do_calibrate(self):
        if not self._active_channel:
            return
        from ui_qt.widgets.calibration_wizard import CalibrationWizard
        wizard = CalibrationWizard(self.app, self._active_channel, parent=self)
        result = wizard.exec()
        if result == wizard.DialogCode.Accepted:
            self._calibrate_btn.setText(f"{Icon.OK}  SAVED!")
            QTimer.singleShot(1500, lambda: self._calibrate_btn.setText(f"{Icon.SETTINGS}  CALIBRATE"))
        else:
            self._calibrate_btn.setText(f"{Icon.SETTINGS}  CALIBRATE")

    # ----------------------------------------------------------------
    # RFID TAB
    # ----------------------------------------------------------------

    def _build_rfid_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(S.PAD, S.GAP, S.PAD, S.GAP)
        layout.setSpacing(S.GAP)

        # Driver info row
        drv_row = QHBoxLayout()
        drv_row.setSpacing(S.GAP)
        drv_type = self.app.driver_status.get("rfid", "fake")
        drv_badge = type_badge(drv_type.upper(), "success" if drv_type in ("real", "socket") else "muted")
        drv_row.addWidget(drv_badge)
        self._rfid_health_dot = status_dot(False, size=12)
        drv_row.addWidget(self._rfid_health_dot)
        # Show reader count if multi-reader driver
        rfid_label = "PN532 USB NFC"
        try:
            ids = self.app.rfid.get_reader_ids()
            if len(ids) > 1:
                rfid_label = f"PN532 Multi ({len(ids)} readers)"
            elif len(ids) == 1:
                rfid_label = f"PN532 USB NFC ({ids[0]})"
        except Exception:
            pass
        self._rfid_health_lbl = QLabel(rfid_label)
        self._rfid_health_lbl.setStyleSheet(
            f"font-size: {F.SMALL}px; font-weight: bold; color: {C.TEXT};"
        )
        drv_row.addWidget(self._rfid_health_lbl)
        drv_row.addStretch()
        layout.addLayout(drv_row)

        # Scan button (primary, full width, 56px)
        self._rfid_scan_btn = _btn(f"{Icon.TAG}  SCAN NOW", "primary")
        self._rfid_scan_btn.setFixedHeight(S.BTN_H)
        self._rfid_scan_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {C.PRIMARY}; color: {C.BG_DARK};"
            f"  border: none; border-radius: {S.RADIUS}px;"
            f"  font-size: {F.H3}px; font-weight: bold;"
            f"  min-height: {S.BTN_H}px;"
            f"}}"
            f"QPushButton:hover {{ background-color: {C.PRIMARY_DIM}; }}"
        )
        self._rfid_scan_btn.clicked.connect(self._do_rfid_scan)
        layout.addWidget(self._rfid_scan_btn)

        # Result card with icon_label per field
        result_lay = QGridLayout()
        result_lay.setContentsMargins(S.PAD_CARD, S.PAD_CARD, S.PAD_CARD, S.PAD_CARD)
        result_lay.setHorizontalSpacing(S.PAD)
        result_lay.setVerticalSpacing(S.GAP)

        def _field_label(glyph, text, color=C.TEXT_MUTED):
            row = QHBoxLayout()
            row.setSpacing(4)
            icn = icon_label(glyph, color=color, size=14)
            row.addWidget(icn)
            lbl = QLabel(text)
            lbl.setStyleSheet(f"font-size: {F.TINY}px; color: {C.TEXT_MUTED};")
            row.addWidget(lbl)
            row.addStretch()
            w = QWidget()
            w.setLayout(row)
            return w

        def _val(text, style=""):
            l = QLabel(text)
            l.setStyleSheet(style or f"font-size: {F.SMALL}px; color: {C.TEXT}; font-weight: bold;")
            l.setWordWrap(True)
            return l

        result_lay.addWidget(_field_label(Icon.TAG, "UID"), 0, 0)
        self._rfid_uid = _val("---", f"font-size: {F.SMALL}px; color: {C.PRIMARY}; font-weight: bold; font-family: monospace;")
        result_lay.addWidget(self._rfid_uid, 0, 1)

        result_lay.addWidget(_field_label(Icon.CHART, "Signal"), 0, 2)
        self._rfid_signal = _val("---")
        result_lay.addWidget(self._rfid_signal, 0, 3)

        result_lay.addWidget(_field_label(Icon.LOCK, "PPG Code"), 1, 0)
        self._rfid_ppg = _val("---")
        result_lay.addWidget(self._rfid_ppg, 1, 1)

        result_lay.addWidget(_field_label(Icon.INVENTORY, "Batch"), 1, 2)
        self._rfid_batch = _val("---")
        result_lay.addWidget(self._rfid_batch, 1, 3)

        result_lay.addWidget(_field_label(Icon.MIXING, "Product"), 2, 0)
        self._rfid_product = _val("---")
        result_lay.addWidget(self._rfid_product, 2, 1)

        result_lay.addWidget(_field_label(Icon.DOT, "Color"), 2, 2)
        self._rfid_color = _val("---")
        result_lay.addWidget(self._rfid_color, 2, 3)

        result_card = _card(result_lay, accent_color=C.SECONDARY)
        layout.addWidget(result_card)

        # History section header
        layout.addWidget(section_header(Icon.CHART, "SCAN HISTORY"))

        # History scrollable
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
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

        try:
            tags = self.app.rfid.poll_tags()
            if tags:
                # Show first tag in the detail card
                t = tags[0]
                self._rfid_uid.setText(t.tag_id)
                self._rfid_signal.setText(f"{t.signal_strength}%")
                self._rfid_ppg.setText(t.ppg_code or "---")
                self._rfid_batch.setText(t.batch_number or "---")
                self._rfid_product.setText(t.product_name or "---")
                self._rfid_color.setText(t.color or "---")
                # Add ALL tags to history (multi-reader support)
                ts = time.strftime("%H:%M:%S")
                for tag in tags:
                    reader = tag.reader_id or "?"
                    self._rfid_history.appendleft(
                        f"{ts} | {reader} | {tag.tag_id} | {tag.ppg_code or '?'}"
                    )
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

        tag_count = f" ({len(tags)} tags)" if 'tags' in dir() and tags and len(tags) > 1 else ""
        self._rfid_scan_btn.setText(f"{Icon.TAG}  SCAN NOW{tag_count}")
        self._rfid_scan_btn.setEnabled(True)

    def _rebuild_rfid_history(self):
        while self._rfid_history_layout.count() > 1:
            item = self._rfid_history_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for idx, entry in enumerate(self._rfid_history):
            bg = C.BG_CARD_ALT if idx % 2 == 0 else C.BG_CARD
            lbl = QLabel(entry)
            lbl.setStyleSheet(
                f"font-size: {F.TINY}px; color: {C.TEXT_SEC}; font-family: monospace;"
                f"background: {bg}; padding: 4px 8px; border-radius: 4px;"
            )
            self._rfid_history_layout.insertWidget(
                self._rfid_history_layout.count() - 1, lbl
            )

    # ----------------------------------------------------------------
    # LED TAB
    # ----------------------------------------------------------------

    def _build_led_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(S.PAD, S.GAP, S.PAD, S.GAP)
        layout.setSpacing(S.GAP)

        # Driver info row
        drv_row = QHBoxLayout()
        drv_row.setSpacing(S.GAP)
        drv_type = self.app.driver_status.get("led", "fake")
        drv_badge = type_badge(drv_type.upper(), "success" if drv_type == "real" else "muted")
        drv_row.addWidget(drv_badge)
        healthy = False
        try:
            healthy = self.app.led.is_healthy()
        except Exception:
            pass
        health_dot = status_dot(healthy, size=12)
        drv_row.addWidget(health_dot)
        health_lbl = QLabel("LED Indicators")
        health_lbl.setStyleSheet(
            f"font-size: {F.SMALL}px; font-weight: bold; color: {C.TEXT};"
        )
        drv_row.addWidget(health_lbl)
        drv_row.addStretch()
        layout.addLayout(drv_row)

        # Slot grid section
        layout.addWidget(section_header(Icon.SHELF, "SLOT CONTROL"))

        slot_grid = QGridLayout()
        slot_grid.setSpacing(S.GAP)
        self._led_slot_btns = {}
        slot_count = getattr(self.app, "slot_count", 4)
        cols = 4
        for i in range(slot_count):
            sid = f"shelf1_slot{i + 1}"
            # Slot button with icon_badge-style layout
            b = QPushButton(f"S{i + 1}")
            b.setMinimumHeight(48)
            b.setStyleSheet(self._led_btn_style(LEDColor.OFF))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda checked, s=sid: self._cycle_slot_color(s))
            slot_grid.addWidget(b, i // cols, i % cols)
            self._led_slot_btns[sid] = b
            self._led_slot_colors[sid] = 0

        layout.addLayout(slot_grid)

        # Pattern selector as toggle button group
        layout.addWidget(section_header(Icon.PLAY, "PATTERN"))

        pat_row = QHBoxLayout()
        pat_row.setSpacing(S.GAP)
        self._pattern_btns = {}
        patterns = [
            ("SOLID", LEDPattern.SOLID),
            ("BLINK", LEDPattern.BLINK_SLOW),
            ("FAST", LEDPattern.BLINK_FAST),
            ("PULSE", LEDPattern.PULSE),
        ]
        for label, pat in patterns:
            b = _toggle_btn(label, active=(pat == LEDPattern.SOLID))
            b.clicked.connect(lambda checked, p=pat: self._set_led_pattern(p))
            pat_row.addWidget(b)
            self._pattern_btns[pat] = b
        layout.addLayout(pat_row)

        # ALL ON / ALL OFF buttons
        ctrl = QHBoxLayout()
        ctrl.setSpacing(S.GAP)
        on_btn = _btn(f"{Icon.OK}  ALL ON", "success")
        on_btn.setFixedHeight(44)
        on_btn.clicked.connect(self._led_all_on)
        ctrl.addWidget(on_btn)
        off_btn = _btn(f"{Icon.CLOSE}  ALL OFF", "danger")
        off_btn.setFixedHeight(44)
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
            f"border-radius: 8px; font-size: {F.BODY}px; font-weight: bold; }}"
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
            sid = f"shelf1_slot{i + 1}"
            self._led_slot_colors[sid] = self._color_cycle.index(LEDColor.GREEN)
            b = self._led_slot_btns.get(sid)
            if b:
                b.setText(f"S{i + 1}\nGREEN")
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

    # ----------------------------------------------------------------
    # BUZZER TAB
    # ----------------------------------------------------------------

    def _build_buzzer_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(S.PAD, S.GAP, S.PAD, S.GAP)
        layout.setSpacing(S.GAP)

        # Driver info row
        drv_row = QHBoxLayout()
        drv_row.setSpacing(S.GAP)
        drv_type = self.app.driver_status.get("buzzer", "fake")
        drv_badge = type_badge(drv_type.upper(), "success" if drv_type == "real" else "muted")
        drv_row.addWidget(drv_badge)
        healthy = False
        try:
            healthy = self.app.buzzer.is_healthy()
        except Exception:
            pass
        health_dot = status_dot(healthy, size=12)
        drv_row.addWidget(health_dot)
        health_lbl = QLabel("Buzzer")
        health_lbl.setStyleSheet(
            f"font-size: {F.SMALL}px; font-weight: bold; color: {C.TEXT};"
        )
        drv_row.addWidget(health_lbl)
        drv_row.addStretch()
        layout.addLayout(drv_row)

        # Pattern grid 3x2 with icon_badge per pattern
        layout.addWidget(section_header(Icon.ALARM, "SOUND PATTERNS"))

        grid = QGridLayout()
        grid.setSpacing(S.GAP)

        _pattern_icons = {
            "CONFIRM": (Icon.OK, C.SUCCESS, C.SUCCESS_BG),
            "WARNING": (Icon.WARN, C.WARNING, C.WARNING_BG),
            "ERROR":   (Icon.ERROR, C.DANGER, C.DANGER_BG),
            "TARGET":  (Icon.CHART, C.PRIMARY, C.PRIMARY_BG),
            "TICK":    (Icon.DOT, C.ACCENT, C.ACCENT_BG),
        }

        patterns = [
            (BuzzerPattern.CONFIRM, "CONFIRM", "Short beep"),
            (BuzzerPattern.WARNING, "WARNING", "Double beep"),
            (BuzzerPattern.ERROR, "ERROR", "Long buzz"),
            (BuzzerPattern.TARGET_REACHED, "TARGET", "Rising tone"),
            (BuzzerPattern.TICK, "TICK", "Click"),
        ]
        for i, (pat, name, desc) in enumerate(patterns):
            glyph, fg, bg = _pattern_icons[name]
            # Container with icon badge + name + description
            cell = QVBoxLayout()
            cell.setSpacing(4)
            cell.setAlignment(Qt.AlignmentFlag.AlignCenter)

            badge = icon_badge(glyph, bg_color=bg, fg_color=fg, size=36)
            cell.addWidget(badge, alignment=Qt.AlignmentFlag.AlignCenter)

            name_lbl = QLabel(name)
            name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_lbl.setStyleSheet(
                f"font-size: {F.SMALL}px; font-weight: bold; color: {C.TEXT};"
            )
            cell.addWidget(name_lbl)

            desc_lbl = QLabel(desc)
            desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc_lbl.setStyleSheet(
                f"font-size: {F.TINY}px; color: {C.TEXT_MUTED};"
            )
            cell.addWidget(desc_lbl)

            cell_frame = QFrame()
            cell_frame.setObjectName("card")
            cell_frame.setLayout(cell)
            cell_frame.setCursor(Qt.CursorShape.PointingHandCursor)
            cell_frame.setStyleSheet(
                f"QFrame#card {{"
                f"  border-left: 3px solid {fg};"
                f"}}"
                f"QFrame#card:hover {{"
                f"  border-color: {fg};"
                f"  background-color: {C.BG_HOVER};"
                f"}}"
            )
            # Wrap in clickable button
            btn = QPushButton()
            btn.setMinimumHeight(70)
            btn.setStyleSheet(
                f"QPushButton {{"
                f"  background: {C.BG_CARD}; border: 1px solid {C.BORDER};"
                f"  border-left: 3px solid {fg}; border-radius: 8px;"
                f"  padding: {S.GAP}px;"
                f"}}"
                f"QPushButton:hover {{ background: {C.BG_HOVER}; border-color: {fg}; }}"
                f"QPushButton:pressed {{ background: {C.BG_CARD_ALT}; }}"
            )
            btn_layout = QVBoxLayout(btn)
            btn_layout.setSpacing(2)
            btn_layout.setContentsMargins(4, 4, 4, 4)

            b_icon = icon_badge(glyph, bg_color=bg, fg_color=fg, size=32)
            btn_layout.addWidget(b_icon, alignment=Qt.AlignmentFlag.AlignCenter)

            b_name = QLabel(name)
            b_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
            b_name.setStyleSheet(f"font-size: {F.SMALL}px; font-weight: bold; color: {fg};")
            btn_layout.addWidget(b_name)

            b_desc = QLabel(desc)
            b_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
            b_desc.setStyleSheet(f"font-size: {F.TINY}px; color: {C.TEXT_MUTED};")
            btn_layout.addWidget(b_desc)

            btn.clicked.connect(lambda checked, p=pat: self._play_buzzer(p))
            grid.addWidget(btn, i // 3, i % 3)

            # Remove unused cell_frame (we used btn instead)
            cell_frame.deleteLater()

        layout.addLayout(grid)

        # STOP button (danger, full width, large)
        stop = _btn(f"{Icon.STOP}  STOP", "danger")
        stop.setFixedHeight(S.BTN_H)
        stop.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {C.DANGER_BG}; color: {C.DANGER};"
            f"  border: 2px solid {C.DANGER}; border-radius: {S.RADIUS}px;"
            f"  font-size: {F.H3}px; font-weight: bold;"
            f"  min-height: {S.BTN_H}px;"
            f"}}"
            f"QPushButton:hover {{ background-color: {C.DANGER}; color: {C.BG_DARK}; }}"
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

    # ----------------------------------------------------------------
    # LIFECYCLE
    # ----------------------------------------------------------------

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
