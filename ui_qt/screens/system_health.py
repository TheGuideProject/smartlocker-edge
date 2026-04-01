"""
SmartLocker System Health Screen

Comprehensive system health dashboard showing:
- Hardware metrics (CPU temp, CPU %, RAM, disk) with color-coded bars
- Cloud sync status (paired, last sync, queue depth, heartbeat)
- Sensor health (RFID, weight, LED, buzzer driver status)
- System info (uptime, version, network, power)

Refreshes every 2 seconds. Uses icon system for consistent styling.
"""

import time
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QProgressBar, QGridLayout, QScrollArea, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer

from ui_qt.theme import C, F, S, enable_touch_scroll
from ui_qt.icons import (
    Icon, icon_badge, icon_label, status_dot, type_badge,
    section_header, screen_header,
)

logger = logging.getLogger("smartlocker.ui.system_health")


# ================================================================
# System Health Screen
# ================================================================

class SystemHealthScreen(QWidget):
    """Comprehensive system health monitoring dashboard."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._metric_widgets = {}
        self._build_ui()

    # ================================================================
    # UI BUILD
    # ================================================================

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Screen header with overall status badge
        header_frame, header_layout = screen_header(
            self.app, "SYSTEM HEALTH", Icon.HEALTH, C.SUCCESS
        )
        self._status_badge = type_badge("OFFLINE", "muted")
        header_layout.addWidget(self._status_badge)
        root.addWidget(header_frame)

        # Scrollable body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        body_widget = QWidget()
        body = QVBoxLayout(body_widget)
        body.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
        body.setSpacing(S.GAP + 2)

        # No-data label (hidden by default)
        self._no_data_label = QLabel("Monitoring not started")
        self._no_data_label.setStyleSheet(
            f"font-size: {F.H3}px; color: {C.TEXT_MUTED};"
        )
        self._no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_data_label.setVisible(False)
        body.addWidget(self._no_data_label)

        # -- HARDWARE METRICS --
        body.addWidget(section_header(Icon.SENSORS, "HARDWARE METRICS", C.PRIMARY))

        self._metrics_container = QWidget()
        metrics_config = [
            ("cpu_temp", "CPU TEMP", "C",  85, 70, 100, Icon.SENSORS, C.ACCENT,  C.ACCENT_BG),
            ("cpu_pct",  "CPU",      "%",  90, 70, 100, Icon.SENSORS, C.PRIMARY, C.PRIMARY_BG),
            ("ram_pct",  "RAM",      "%",  85, 65, 100, Icon.INFO,    C.SECONDARY, C.SECONDARY_BG),
            ("disk_pct", "DISK",     "%",  90, 75, 100, Icon.INVENTORY, C.WARNING, C.WARNING_BG),
        ]
        metrics_grid = QGridLayout(self._metrics_container)
        metrics_grid.setSpacing(S.GAP)
        metrics_grid.setContentsMargins(0, 0, 0, 0)
        for i, (key, label, unit, t_red, t_yellow, max_v, glyph, fg, bg) in enumerate(metrics_config):
            card = self._build_metric_card(key, label, unit, t_red, t_yellow, max_v, glyph, fg, bg)
            metrics_grid.addWidget(card, i // 2, i % 2)
        body.addWidget(self._metrics_container)

        # -- CLOUD SYNC --
        self._cloud_card = self._build_cloud_card()
        body.addWidget(self._cloud_card)

        # -- SENSOR HEALTH --
        self._sensor_card = self._build_sensor_card()
        body.addWidget(self._sensor_card)

        # -- SYSTEM INFO --
        self._system_card = self._build_system_info_card()
        body.addWidget(self._system_card)

        body.addStretch(1)

        scroll.setWidget(body_widget)
        enable_touch_scroll(scroll)
        root.addWidget(scroll, stretch=1)

    # ----------------------------------------------------------------
    # Metric Card (2x2 grid cells)
    # ----------------------------------------------------------------

    def _build_metric_card(self, key: str, label: str, unit: str,
                           thresh_red: int, thresh_yellow: int,
                           max_val: float, glyph: str,
                           icon_fg: str, icon_bg: str) -> QFrame:
        card = QFrame()
        card.setObjectName("card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(S.PAD_CARD, S.PAD_CARD, S.PAD_CARD, S.PAD_CARD)
        layout.setSpacing(4)

        # Top row: icon badge + label
        top = QHBoxLayout()
        top.setSpacing(S.GAP)

        badge = icon_badge(glyph, bg_color=icon_bg, fg_color=icon_fg, size=28)
        top.addWidget(badge)

        lbl_name = QLabel(label)
        lbl_name.setStyleSheet(
            f"font-size: {F.SMALL}px; font-weight: bold; color: {C.TEXT_MUTED};"
            f"letter-spacing: 1px;"
        )
        top.addWidget(lbl_name)
        top.addStretch()

        # Value (right-aligned in top row)
        lbl_value = QLabel(f"--{unit}")
        lbl_value.setStyleSheet(
            f"font-size: {F.H2}px; font-weight: bold; color: {C.TEXT};"
        )
        lbl_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_value.setMinimumWidth(70)
        top.addWidget(lbl_value)

        layout.addLayout(top)

        # Progress bar (12px height, dynamic color)
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setTextVisible(False)
        bar.setFixedHeight(12)
        bar.setStyleSheet(
            f"QProgressBar {{ background-color: {C.BG_INPUT};"
            f"border: none; border-radius: 6px;"
            f"min-height: 12px; max-height: 12px; }}"
            f"QProgressBar::chunk {{ background-color: {C.PRIMARY};"
            f"border-radius: 6px; }}"
        )
        layout.addWidget(bar)

        self._metric_widgets[key] = {
            "card": card,
            "value_label": lbl_value,
            "bar": bar,
            "unit": unit,
            "thresh_red": thresh_red,
            "thresh_yellow": thresh_yellow,
        }

        return card

    # ----------------------------------------------------------------
    # Cloud & Sync Card
    # ----------------------------------------------------------------

    def _build_cloud_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(
            f"QFrame#card {{ border-left: 4px solid {C.SECONDARY}; }}"
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(S.PAD, S.PAD_CARD, S.PAD, S.PAD_CARD)
        layout.setSpacing(S.GAP)

        # Section header
        layout.addWidget(section_header(Icon.CLOUD, "CLOUD SYNC", C.SECONDARY))

        # Status row
        row1 = QHBoxLayout()
        row1.setSpacing(S.GAP)

        self._cloud_dot = status_dot(False, size=14)
        row1.addWidget(self._cloud_dot)

        self._cloud_status_lbl = QLabel("--")
        self._cloud_status_lbl.setStyleSheet(
            f"font-size: {F.BODY}px; font-weight: bold; color: {C.TEXT};"
        )
        row1.addWidget(self._cloud_status_lbl)
        row1.addStretch()

        self._cloud_ws_badge = type_badge("WS: OFF", "muted")
        row1.addWidget(self._cloud_ws_badge)

        layout.addLayout(row1)

        # Info grid: clean key:value pairs
        grid = QGridLayout()
        grid.setHorizontalSpacing(S.PAD)
        grid.setVerticalSpacing(S.GAP)

        grid.addWidget(self._key_label("Last Sync"), 0, 0)
        self._lbl_last_sync = self._value_label("--")
        grid.addWidget(self._lbl_last_sync, 0, 1)

        grid.addWidget(self._key_label("Queue"), 0, 2)
        self._lbl_queue = self._value_label("--")
        grid.addWidget(self._lbl_queue, 0, 3)

        grid.addWidget(self._key_label("Heartbeat"), 1, 0)
        self._lbl_heartbeat = self._value_label("--")
        grid.addWidget(self._lbl_heartbeat, 1, 1)

        grid.addWidget(self._key_label("Vessel"), 1, 2)
        self._lbl_vessel = self._value_label("--")
        grid.addWidget(self._lbl_vessel, 1, 3)

        layout.addLayout(grid)

        return card

    # ----------------------------------------------------------------
    # Sensor Health Card
    # ----------------------------------------------------------------

    def _build_sensor_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(
            f"QFrame#card {{ border-left: 4px solid {C.ACCENT}; }}"
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(S.PAD, S.PAD_CARD, S.PAD, S.PAD_CARD)
        layout.setSpacing(S.GAP)

        # Section header
        layout.addWidget(section_header(Icon.SENSORS, "SENSOR DRIVERS", C.ACCENT))

        # Sensor rows with icon_badge + name + status_dot + text
        self._sensor_rows = {}
        sensors = [
            ("rfid",   "RFID Reader",  Icon.TAG,    C.PRIMARY,   C.PRIMARY_BG),
            ("weight", "Weight Scale", Icon.WEIGHT,  C.ACCENT,    C.ACCENT_BG),
            ("led",    "LED Strip",    Icon.DOT,     C.SUCCESS,   C.SUCCESS_BG),
            ("buzzer", "Buzzer",       Icon.ALARM,   C.SECONDARY, C.SECONDARY_BG),
        ]
        for key, name, glyph, fg, bg in sensors:
            row = QHBoxLayout()
            row.setSpacing(S.GAP)

            badge = icon_badge(glyph, bg_color=bg, fg_color=fg, size=28)
            row.addWidget(badge)

            name_lbl = QLabel(name)
            name_lbl.setStyleSheet(
                f"font-size: {F.SMALL}px; color: {C.TEXT}; font-weight: bold;"
            )
            name_lbl.setFixedWidth(120)
            row.addWidget(name_lbl)

            driver_lbl = QLabel("--")
            driver_lbl.setStyleSheet(
                f"font-size: {F.TINY}px; color: {C.TEXT_MUTED};"
            )
            row.addWidget(driver_lbl)

            row.addStretch()

            dot = status_dot(False, size=12)
            row.addWidget(dot)

            status_lbl = QLabel("--")
            status_lbl.setStyleSheet(
                f"font-size: {F.TINY}px; color: {C.TEXT_MUTED};"
            )
            row.addWidget(status_lbl)

            layout.addLayout(row)
            self._sensor_rows[key] = {
                "dot": dot,
                "driver": driver_lbl,
                "status": status_lbl,
            }

        return card

    # ----------------------------------------------------------------
    # System Info Card
    # ----------------------------------------------------------------

    def _build_system_info_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(
            f"QFrame#card {{ border-left: 4px solid {C.TEXT_MUTED}; }}"
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(S.PAD, S.PAD_CARD, S.PAD, S.PAD_CARD)
        layout.setSpacing(S.GAP)

        # Section header
        layout.addWidget(section_header(Icon.SETTINGS, "SYSTEM INFO", C.TEXT_SEC))

        # Clean key:value grid
        grid = QGridLayout()
        grid.setHorizontalSpacing(S.PAD)
        grid.setVerticalSpacing(S.GAP)

        grid.addWidget(self._key_label("Version"), 0, 0)
        self._lbl_version = self._value_label("--")
        grid.addWidget(self._lbl_version, 0, 1)

        grid.addWidget(self._key_label("Uptime"), 0, 2)
        self._lbl_uptime = self._value_label("--")
        grid.addWidget(self._lbl_uptime, 0, 3)

        grid.addWidget(self._key_label("Network"), 1, 0)
        self._lbl_network = self._value_label("--")
        grid.addWidget(self._lbl_network, 1, 1)

        grid.addWidget(self._key_label("Clock"), 1, 2)
        self._lbl_clock = self._value_label("--")
        grid.addWidget(self._lbl_clock, 1, 3)

        grid.addWidget(self._key_label("SD Card"), 2, 0)
        self._lbl_sd = self._value_label("--")
        grid.addWidget(self._lbl_sd, 2, 1)

        grid.addWidget(self._key_label("Power"), 2, 2)
        self._lbl_power = self._value_label("--")
        grid.addWidget(self._lbl_power, 2, 3)

        grid.addWidget(self._key_label("Mode"), 3, 0)
        self._lbl_mode = self._value_label("--")
        self._lbl_mode.setStyleSheet(
            f"color: {C.PRIMARY}; font-size: {F.SMALL}px; font-weight: bold;"
        )
        grid.addWidget(self._lbl_mode, 3, 1)

        grid.addWidget(self._key_label("DB Size"), 3, 2)
        self._lbl_db_size = self._value_label("--")
        grid.addWidget(self._lbl_db_size, 3, 3)

        layout.addLayout(grid)

        return card

    # ================================================================
    # DATA REFRESH
    # ================================================================

    def _refresh(self):
        """Refresh all sections with latest data."""
        self._refresh_metrics()
        self._refresh_cloud()
        self._refresh_sensors()
        self._refresh_system_info()

    def _refresh_metrics(self):
        """Update hardware metric cards with color-coded values."""
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
            self._show_no_data("Starting monitor...")
            return

        # Hide no-data, show all sections
        self._no_data_label.setVisible(False)
        self._metrics_container.setVisible(True)
        self._cloud_card.setVisible(True)
        self._sensor_card.setVisible(True)
        self._system_card.setVisible(True)

        # Update header badge to LIVE
        self._status_badge.setText("LIVE")
        self._status_badge.setStyleSheet(
            f"background-color: {C.SUCCESS_BG}; color: {C.SUCCESS};"
            f"border: 1px solid {C.SUCCESS}; border-radius: 4px;"
            f"padding: 2px 8px; font-size: {F.TINY}px; font-weight: bold;"
        )

        # Update each metric card
        for key, refs in self._metric_widgets.items():
            raw = metrics.get(key, 0)
            try:
                val = float(raw) if raw is not None else 0.0
            except (TypeError, ValueError):
                val = 0.0

            unit = refs["unit"]
            thresh_red = refs["thresh_red"]
            thresh_yellow = refs["thresh_yellow"]

            bar_val = min(100, max(0, int(val)))
            if key == "cpu_temp":
                display = f"{val:.1f}{unit}"
            else:
                display = f"{val:.0f}{unit}"

            refs["value_label"].setText(display)
            refs["bar"].setValue(bar_val)

            # Color coding: green < 70, yellow < 85, red >= 85
            if val >= thresh_red:
                color = C.DANGER
                val_color = C.DANGER
            elif val >= thresh_yellow:
                color = C.WARNING
                val_color = C.WARNING
            else:
                color = C.SUCCESS
                val_color = C.TEXT

            refs["bar"].setStyleSheet(
                f"QProgressBar {{ background-color: {C.BG_INPUT};"
                f"border: none; border-radius: 6px;"
                f"min-height: 12px; max-height: 12px; }}"
                f"QProgressBar::chunk {{ background-color: {color};"
                f"border-radius: 6px; }}"
            )
            refs["value_label"].setStyleSheet(
                f"font-size: {F.H2}px; font-weight: bold; color: {val_color};"
            )

    def _refresh_cloud(self):
        """Update cloud sync status section."""
        sync_engine = getattr(self.app, "sync_engine", None)
        cloud = getattr(self.app, "cloud", None)

        if not cloud:
            return

        is_paired = getattr(cloud, "is_paired", False)

        if is_paired:
            self._cloud_dot.setStyleSheet(
                f"background-color: {C.SUCCESS}; border-radius: 7px;"
            )
            self._cloud_status_lbl.setText("CONNECTED")
            self._cloud_status_lbl.setStyleSheet(
                f"font-size: {F.BODY}px; font-weight: bold; color: {C.SUCCESS};"
            )
        else:
            self._cloud_dot.setStyleSheet(
                f"background-color: {C.DANGER}; border-radius: 7px;"
            )
            self._cloud_status_lbl.setText("NOT PAIRED")
            self._cloud_status_lbl.setStyleSheet(
                f"font-size: {F.BODY}px; font-weight: bold; color: {C.DANGER};"
            )

        # Sync engine details
        if sync_engine:
            try:
                status = sync_engine.get_status()

                # Last sync
                last_sync = status.get("last_sync", 0)
                self._lbl_last_sync.setText(
                    self._time_ago(last_sync) if last_sync else "Never"
                )

                # Queue depth
                unsynced = status.get("events_unsynced", 0)
                total = status.get("events_total", 0)
                queue_color = C.WARNING if unsynced > 10 else C.TEXT
                self._lbl_queue.setText(f"{unsynced} pending / {total} total")
                self._lbl_queue.setStyleSheet(
                    f"color: {queue_color}; font-size: {F.SMALL}px;"
                )

                # Vessel
                vessel = status.get("vessel_name", "")
                self._lbl_vessel.setText(vessel if vessel else "Not assigned")

                # Uptime from sync
                uptime_h = status.get("uptime_hours", 0)
                self._lbl_uptime.setText(self._format_uptime(uptime_h))

                # WebSocket badge
                ws = status.get("ws_connected", False)
                if ws:
                    self._cloud_ws_badge.setText("WS: LIVE")
                    self._cloud_ws_badge.setStyleSheet(
                        f"background-color: {C.SUCCESS_BG}; color: {C.SUCCESS};"
                        f"border: 1px solid {C.SUCCESS}; border-radius: 4px;"
                        f"padding: 2px 8px; font-size: {F.TINY}px; font-weight: bold;"
                    )
                else:
                    self._cloud_ws_badge.setText("WS: OFF")
                    self._cloud_ws_badge.setStyleSheet(
                        f"background-color: {C.BG_CARD_ALT}; color: {C.TEXT_MUTED};"
                        f"border: 1px solid {C.TEXT_MUTED}; border-radius: 4px;"
                        f"padding: 2px 8px; font-size: {F.TINY}px;"
                    )

                # Heartbeat
                hb_time = getattr(sync_engine, "_last_heartbeat_time", 0)
                self._lbl_heartbeat.setText(
                    self._time_ago(hb_time) if hb_time else "Waiting..."
                )

            except Exception as e:
                logger.debug(f"Cloud status error: {e}")

    def _refresh_sensors(self):
        """Update sensor health section."""
        driver_status = getattr(self.app, "driver_status", {})

        for key, refs in self._sensor_rows.items():
            drv = driver_status.get(key, "fake")
            is_real = drv == "real"

            # Driver type badge text
            refs["driver"].setText(drv.upper())
            refs["driver"].setStyleSheet(
                f"font-size: {F.TINY}px;"
                f"color: {C.SUCCESS if is_real else C.TEXT_MUTED};"
                f"font-weight: bold;"
            )

            # Health check
            health_ok = True
            status_text = "OK"

            if key == "rfid":
                try:
                    rfid = getattr(self.app, "rfid", None)
                    if rfid and hasattr(rfid, "is_healthy"):
                        health_ok = rfid.is_healthy()
                        status_text = "OK" if health_ok else "ERROR"
                    elif not is_real:
                        status_text = "SIM"
                except Exception:
                    health_ok = False
                    status_text = "ERROR"

            elif key == "weight":
                try:
                    weight = getattr(self.app, "weight", None)
                    if weight and hasattr(weight, "is_healthy"):
                        health_ok = weight.is_healthy()
                        status_text = "OK" if health_ok else "ERROR"
                    elif not is_real:
                        status_text = "SIM"
                except Exception:
                    health_ok = False
                    status_text = "ERROR"

            elif key in ("led", "buzzer"):
                status_text = "ACTIVE" if is_real else "SIM"
                health_ok = True

            # Update dot color
            if not is_real:
                dot_color = C.TEXT_MUTED
            elif health_ok:
                dot_color = C.SUCCESS
            else:
                dot_color = C.DANGER

            refs["dot"].setStyleSheet(
                f"background-color: {dot_color}; border-radius: 6px;"
            )

            # Status label
            if health_ok:
                refs["status"].setText(status_text)
                refs["status"].setStyleSheet(
                    f"font-size: {F.TINY}px;"
                    f"color: {C.SUCCESS if is_real else C.TEXT_MUTED};"
                    f"font-weight: bold;"
                )
            else:
                refs["status"].setText(status_text)
                refs["status"].setStyleSheet(
                    f"font-size: {F.TINY}px; color: {C.DANGER}; font-weight: bold;"
                )

    def _refresh_system_info(self):
        """Update system info section."""
        # Version
        try:
            from sync.update_manager import read_version
            self._lbl_version.setText(f"v{read_version()}")
        except Exception:
            self._lbl_version.setText("v?.?.?")

        # Mode
        mode = getattr(self.app, "mode", "unknown")
        self._lbl_mode.setText(mode.upper())

        # Monitor data for network, clock, sd, power
        monitor = getattr(self.app, "system_monitor", None)
        if monitor:
            try:
                data = monitor.get_last_check()
                if data:
                    # Network
                    net = data.get("network", {})
                    if net.get("connected"):
                        ip = net.get("ip", "?")
                        iface = net.get("interface", "")
                        net_text = f"{ip}"
                        if iface:
                            net_text += f" ({iface})"
                        self._lbl_network.setText(net_text)
                        self._lbl_network.setStyleSheet(
                            f"color: {C.SUCCESS}; font-size: {F.SMALL}px;"
                        )
                    else:
                        self._lbl_network.setText("Disconnected")
                        self._lbl_network.setStyleSheet(
                            f"color: {C.DANGER}; font-size: {F.SMALL}px;"
                        )

                    # Clock sync
                    clock_ok = data.get("clock_sync", None)
                    if clock_ok is True:
                        self._lbl_clock.setText("NTP Synced")
                        self._lbl_clock.setStyleSheet(
                            f"color: {C.SUCCESS}; font-size: {F.SMALL}px;"
                        )
                    elif clock_ok is False:
                        self._lbl_clock.setText("Not synced")
                        self._lbl_clock.setStyleSheet(
                            f"color: {C.WARNING}; font-size: {F.SMALL}px;"
                        )

                    # SD health
                    sd = data.get("sd_health", "ok")
                    if sd == "ok":
                        self._lbl_sd.setText("OK")
                        self._lbl_sd.setStyleSheet(
                            f"color: {C.SUCCESS}; font-size: {F.SMALL}px;"
                        )
                    else:
                        self._lbl_sd.setText("ERROR")
                        self._lbl_sd.setStyleSheet(
                            f"color: {C.DANGER}; font-size: {F.SMALL}px; font-weight: bold;"
                        )

                    # Power
                    under_v = data.get("under_voltage", False)
                    throttled = data.get("cpu_throttled", False)
                    if under_v:
                        self._lbl_power.setText("UNDER VOLTAGE")
                        self._lbl_power.setStyleSheet(
                            f"color: {C.DANGER}; font-size: {F.SMALL}px; font-weight: bold;"
                        )
                    elif throttled:
                        self._lbl_power.setText("THROTTLED")
                        self._lbl_power.setStyleSheet(
                            f"color: {C.WARNING}; font-size: {F.SMALL}px;"
                        )
                    else:
                        self._lbl_power.setText("Stable")
                        self._lbl_power.setStyleSheet(
                            f"color: {C.SUCCESS}; font-size: {F.SMALL}px;"
                        )
            except Exception:
                pass

        # DB size
        try:
            db_path = getattr(self.app.db, 'db_path', None)
            if db_path:
                import os
                if os.path.exists(db_path):
                    size_mb = os.path.getsize(db_path) / (1024 * 1024)
                    self._lbl_db_size.setText(f"{size_mb:.1f} MB")
        except Exception:
            pass

    # ================================================================
    # NO-DATA STATE
    # ================================================================

    def _show_no_data(self, message: str):
        self._no_data_label.setText(message)
        self._no_data_label.setVisible(True)
        self._status_badge.setText("OFFLINE")
        self._status_badge.setStyleSheet(
            f"background-color: {C.BG_CARD_ALT}; color: {C.TEXT_MUTED};"
            f"border: 1px solid {C.TEXT_MUTED}; border-radius: 4px;"
            f"padding: 2px 8px; font-size: {F.TINY}px;"
        )
        self._metrics_container.setVisible(False)

    # ================================================================
    # LIFECYCLE
    # ================================================================

    def on_enter(self):
        # Force an immediate health check if no data yet
        monitor = getattr(self.app, "system_monitor", None)
        if monitor and not monitor.get_metrics():
            try:
                monitor.force_check()
            except Exception:
                pass
        self._refresh()
        self._timer.start(2000)

    def on_leave(self):
        self._timer.stop()

    # ================================================================
    # HELPERS
    # ================================================================

    @staticmethod
    def _key_label(text: str) -> QLabel:
        """Create a muted key label for key:value grids."""
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-size: {F.TINY}px;"
            f"font-weight: bold; letter-spacing: 0.5px;"
        )
        lbl.setFixedWidth(75)
        return lbl

    @staticmethod
    def _value_label(text: str) -> QLabel:
        """Create a value label for key:value grids."""
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {C.TEXT}; font-size: {F.SMALL}px;")
        return lbl

    @staticmethod
    def _time_ago(timestamp: float) -> str:
        if not timestamp or timestamp <= 0:
            return "Never"
        diff = time.time() - timestamp
        if diff < 0:
            return "Just now"
        if diff < 60:
            return f"{int(diff)}s ago"
        if diff < 3600:
            return f"{int(diff / 60)}m ago"
        if diff < 86400:
            return f"{int(diff / 3600)}h ago"
        return f"{int(diff / 86400)}d ago"

    @staticmethod
    def _format_uptime(hours: float) -> str:
        if hours < 1:
            return f"{int(hours * 60)}m"
        if hours < 24:
            return f"{hours:.1f}h"
        days = int(hours / 24)
        remaining = hours - days * 24
        return f"{days}d {remaining:.0f}h"
