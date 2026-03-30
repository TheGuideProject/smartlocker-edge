"""
SmartLocker System Health Screen

Displays CPU temperature, RAM usage, Disk usage, and CPU usage
with color-coded progress bars. Refreshes every 2 seconds.
"""

import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QProgressBar, QSizePolicy, QGridLayout,
)
from PyQt6.QtCore import Qt, QTimer

from ui_qt.theme import C, F, S

logger = logging.getLogger("smartlocker.ui.system_health")


class SystemHealthScreen(QWidget):
    """System health monitoring dashboard."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._metric_widgets = {}
        self._build_ui()

    # ══════════════════════════════════════════════════════════
    # UI BUILD
    # ══════════════════════════════════════════════════════════

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ──────────────────────────────────────
        header = QFrame()
        header.setStyleSheet(
            f"background-color: {C.BG_STATUS};"
            f"border-bottom: 1px solid {C.BORDER};"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(S.PAD, 8, S.PAD, 8)
        h_layout.setSpacing(S.GAP)

        btn_back = QPushButton("< BACK")
        btn_back.setObjectName("ghost")
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back.clicked.connect(lambda: self.app.go_back())
        h_layout.addWidget(btn_back)

        title = QLabel("SYSTEM HEALTH")
        title.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.TEXT};"
        )
        h_layout.addWidget(title)

        h_layout.addStretch(1)

        self._status_badge = QLabel("--")
        self._status_badge.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.TEXT_MUTED};"
        )
        h_layout.addWidget(self._status_badge)

        root.addWidget(header)

        # ── Body ────────────────────────────────────────
        body = QVBoxLayout()
        body.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
        body.setSpacing(S.GAP + 4)

        # Message label (shown when no data)
        self._no_data_label = QLabel("Monitoring not started")
        self._no_data_label.setStyleSheet(
            f"font-size: {F.H3}px; color: {C.TEXT_MUTED};"
        )
        self._no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_data_label.setVisible(False)
        body.addWidget(self._no_data_label)

        # Metric cards — 2x2 grid to fit 480px height
        metrics_config = [
            ("cpu_temp", "CPU TEMP", "C", 85, 70),
            ("cpu_pct", "CPU", "%", 90, 70),
            ("ram_pct", "RAM", "%", 85, 65),
            ("disk_pct", "DISK", "%", 90, 75),
        ]

        metrics_grid = QGridLayout()
        metrics_grid.setSpacing(S.GAP)
        for i, (key, label, unit, thresh_red, thresh_yellow) in enumerate(metrics_config):
            card = self._build_metric_card(key, label, unit, thresh_red, thresh_yellow)
            metrics_grid.addWidget(card, i // 2, i % 2)
        body.addLayout(metrics_grid)

        body.addStretch(1)
        root.addLayout(body, stretch=1)

    def _build_metric_card(self, key: str, label: str, unit: str,
                           thresh_red: int, thresh_yellow: int) -> QFrame:
        """Build a single metric card with label, value, and progress bar."""
        card = QFrame()
        card.setObjectName("card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # Top row: label + value
        top = QHBoxLayout()
        top.setSpacing(S.GAP)

        lbl_name = QLabel(label)
        lbl_name.setStyleSheet(
            f"font-size: {F.BODY}px; font-weight: bold; color: {C.TEXT_SEC};"
        )
        top.addWidget(lbl_name)

        top.addStretch(1)

        lbl_value = QLabel(f"--{unit}")
        lbl_value.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.TEXT};"
        )
        top.addWidget(lbl_value)

        layout.addLayout(top)

        # Progress bar
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setTextVisible(False)
        bar.setFixedHeight(14)
        bar.setStyleSheet(
            f"QProgressBar {{ background-color: {C.BG_INPUT};"
            f"border: none; border-radius: 6px; }}"
            f"QProgressBar::chunk {{ background-color: {C.PRIMARY};"
            f"border-radius: 6px; }}"
        )
        layout.addWidget(bar)

        # Store references for updates
        self._metric_widgets[key] = {
            "card": card,
            "value_label": lbl_value,
            "bar": bar,
            "unit": unit,
            "thresh_red": thresh_red,
            "thresh_yellow": thresh_yellow,
        }

        return card

    # ══════════════════════════════════════════════════════════
    # DATA REFRESH
    # ══════════════════════════════════════════════════════════

    def _refresh(self):
        monitor = getattr(self.app, "system_monitor", None)
        if not monitor:
            self._show_no_data("Monitoring not available")
            return

        try:
            metrics = monitor.get_metrics()
        except Exception as e:
            logger.debug(f"Failed to get metrics: {e}")
            self._show_no_data("Monitoring error")
            return

        if metrics is None:
            self._show_no_data("Monitoring not started")
            return

        # Hide no-data label, show metrics
        self._no_data_label.setVisible(False)
        for key, refs in self._metric_widgets.items():
            refs["card"].setVisible(True)

        self._status_badge.setText("LIVE")
        self._status_badge.setStyleSheet(
            f"background-color: {C.SUCCESS_BG}; color: {C.SUCCESS};"
            f"border: 1px solid {C.SUCCESS}; border-radius: 4px;"
            f"padding: 2px 8px; font-size: {F.TINY}px; font-weight: bold;"
        )

        # Update each metric
        for key, refs in self._metric_widgets.items():
            raw = metrics.get(key, 0)
            try:
                val = float(raw)
            except (TypeError, ValueError):
                val = 0.0

            unit = refs["unit"]
            thresh_red = refs["thresh_red"]
            thresh_yellow = refs["thresh_yellow"]

            # For temperature, clamp to 0-100 for progress bar
            if key == "cpu_temp":
                bar_val = min(100, max(0, int(val)))
                display = f"{val:.0f}{unit}"
            else:
                bar_val = min(100, max(0, int(val)))
                display = f"{val:.0f}{unit}"

            refs["value_label"].setText(display)
            refs["bar"].setValue(bar_val)

            # Color coding
            if val >= thresh_red:
                color = C.DANGER
                val_color = C.DANGER
            elif val >= thresh_yellow:
                color = C.WARNING
                val_color = C.WARNING
            else:
                color = C.PRIMARY
                val_color = C.TEXT

            refs["bar"].setStyleSheet(
                f"QProgressBar {{ background-color: {C.BG_INPUT};"
                f"border: none; border-radius: 6px; }}"
                f"QProgressBar::chunk {{ background-color: {color};"
                f"border-radius: 6px; }}"
            )
            refs["value_label"].setStyleSheet(
                f"font-size: {F.H3}px; font-weight: bold; color: {val_color};"
            )

    def _show_no_data(self, message: str):
        self._no_data_label.setText(message)
        self._no_data_label.setVisible(True)
        self._status_badge.setText("OFFLINE")
        self._status_badge.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.TEXT_MUTED};"
        )
        for key, refs in self._metric_widgets.items():
            refs["card"].setVisible(False)

    # ══════════════════════════════════════════════════════════
    # LIFECYCLE
    # ══════════════════════════════════════════════════════════

    def on_enter(self):
        self._refresh()
        self._timer.start(2000)

    def on_leave(self):
        self._timer.stop()
