"""
System Health Screen - Real-time system metrics with line graphs (2026 Redesign)

Displays CPU temperature, RAM usage, disk usage, CPU percentage with rolling
line charts drawn using Kivy Canvas API (zero external dependencies).
Also shows throttle state indicator and color-coded status badges.

Refresh: 1 second interval.
Data: app.system_monitor.get_metrics() -> dict with:
    cpu_temp, ram_pct, disk_pct, cpu_pct, throttle_state
"""

import time
import collections

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.graphics import Color, Line, Rectangle, RoundedRectangle, Ellipse
from kivy.lang import Builder
from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import NumericProperty

from ui.app import DS


# ==============================================================
# MINI LINE GRAPH WIDGET (canvas-based, no external deps)
# ==============================================================

class MiniLineGraph(Widget):
    """
    A compact rolling line graph drawn on Kivy Canvas.

    Parameters:
        max_points: number of data points to retain (rolling window)
        y_min / y_max: value range for the Y axis
        line_color: RGBA tuple for the data line
        threshold_lines: list of (value, rgba_tuple) for horizontal threshold lines
        label_text: optional label displayed in top-left
        unit_text: unit suffix for the current value label
    """

    current_value = NumericProperty(0)

    def __init__(self, max_points=60, y_min=0, y_max=100,
                 line_color=DS.PRIMARY, threshold_lines=None,
                 label_text='', unit_text='', **kwargs):
        super().__init__(**kwargs)
        self._max_points = max_points
        self._y_min = y_min
        self._y_max = y_max
        self._line_color = line_color
        self._threshold_lines = threshold_lines or []
        self._label_text = label_text
        self._unit_text = unit_text
        self._data = collections.deque(maxlen=max_points)

        # Pre-fill with zeros
        for _ in range(max_points):
            self._data.append(0)

        self.bind(pos=self._redraw, size=self._redraw)

    def add_point(self, value):
        """Append a new data point and redraw."""
        self._data.append(value)
        self.current_value = value
        self._redraw()

    def _redraw(self, *_args):
        """Full canvas redraw."""
        self.canvas.clear()
        if self.width < dp(20) or self.height < dp(20):
            return

        x0, y0 = self.pos
        w, h = self.size
        pad_left = dp(4)
        pad_bottom = dp(4)
        pad_top = dp(28)  # space for label
        pad_right = dp(4)

        graph_x = x0 + pad_left
        graph_y = y0 + pad_bottom
        graph_w = w - pad_left - pad_right
        graph_h = h - pad_bottom - pad_top

        y_range = max(self._y_max - self._y_min, 1)

        with self.canvas:
            # Card background
            Color(*DS.BG_CARD)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(DS.RADIUS)])

            # Graph area subtle background
            Color(0.08, 0.09, 0.13, 1)
            RoundedRectangle(
                pos=(graph_x, graph_y),
                size=(graph_w, graph_h),
                radius=[dp(6)],
            )

            # Threshold lines
            for thresh_val, thresh_color in self._threshold_lines:
                if self._y_min <= thresh_val <= self._y_max:
                    ty = graph_y + (thresh_val - self._y_min) / y_range * graph_h
                    Color(*thresh_color)
                    Line(points=[graph_x, ty, graph_x + graph_w, ty], width=1, dash_length=4, dash_offset=4)

            # Grid lines (horizontal, every 25%)
            Color(*DS.DIVIDER[:3], 0.3)
            for frac in (0.25, 0.5, 0.75):
                gy = graph_y + frac * graph_h
                Line(points=[graph_x, gy, graph_x + graph_w, gy], width=1)

            # Data line
            if len(self._data) >= 2:
                points = []
                n = len(self._data)
                step_x = graph_w / max(n - 1, 1)
                for i, val in enumerate(self._data):
                    px = graph_x + i * step_x
                    clamped = max(self._y_min, min(self._y_max, val))
                    py = graph_y + (clamped - self._y_min) / y_range * graph_h
                    points.extend([px, py])
                Color(*self._line_color)
                Line(points=points, width=dp(1.5))

                # Fill area under the line (semi-transparent)
                fill_points = [graph_x, graph_y]
                fill_points.extend(points)
                fill_points.extend([graph_x + (n - 1) * step_x, graph_y])

            # Current value text
            val = self._data[-1] if self._data else 0
            # Determine color based on thresholds
            val_color = DS.SUCCESS
            for thresh_val, thresh_color in sorted(self._threshold_lines, key=lambda t: t[0]):
                if val >= thresh_val:
                    val_color = thresh_color

            Color(*val_color)
            # Value indicator dot at the rightmost point
            if self._data:
                last_val = self._data[-1]
                clamped = max(self._y_min, min(self._y_max, last_val))
                dot_y = graph_y + (clamped - self._y_min) / y_range * graph_h
                dot_x = graph_x + graph_w
                Ellipse(pos=(dot_x - dp(3), dot_y - dp(3)), size=(dp(6), dp(6)))

        # Remove old label children and add fresh ones
        self.clear_widgets()

        # Title label (top-left of widget)
        title = Label(
            text=self._label_text,
            font_size=DS.FONT_SMALL,
            bold=True,
            color=DS.TEXT_SECONDARY,
            pos=(x0 + dp(8), y0 + h - pad_top + dp(2)),
            size=(graph_w * 0.5, dp(22)),
            halign='left',
            text_size=(graph_w * 0.5, dp(22)),
            valign='middle',
        )
        self.add_widget(title)

        # Current value label (top-right of widget)
        val_text = f'{val:.1f}{self._unit_text}'
        val_label = Label(
            text=val_text,
            font_size=DS.FONT_H3,
            bold=True,
            color=val_color if self._threshold_lines else self._line_color,
            pos=(x0 + graph_w * 0.5 + dp(8), y0 + h - pad_top + dp(2)),
            size=(graph_w * 0.5, dp(22)),
            halign='right',
            text_size=(graph_w * 0.5, dp(22)),
            valign='middle',
        )
        self.add_widget(val_label)


# ==============================================================
# STATUS BADGE WIDGET
# ==============================================================

class _StatusBadge(BoxLayout):
    """Compact status indicator: colored dot + label + value."""

    def __init__(self, label_text='', **kwargs):
        super().__init__(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(32),
            spacing=dp(6),
            padding=[dp(8), dp(2)],
            **kwargs,
        )
        with self.canvas.before:
            Color(*DS.BG_CARD)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(8)])
        self.bind(pos=lambda w, v: setattr(w._bg, 'pos', v),
                  size=lambda w, v: setattr(w._bg, 'size', v))

        self._dot = Widget(size_hint=(None, None), size=(dp(10), dp(10)))
        with self._dot.canvas:
            Color(*DS.SUCCESS)
            self._dot_ellipse = Ellipse(pos=self._dot.pos, size=self._dot.size)
        self._dot.bind(
            pos=lambda w, v: setattr(self._dot_ellipse, 'pos', (v[0], v[1] + dp(10))),
            size=lambda w, v: setattr(self._dot_ellipse, 'size', v),
        )

        self._label = Label(
            text=label_text,
            font_size=DS.FONT_SMALL,
            color=DS.TEXT_SECONDARY,
            size_hint_x=0.5,
            halign='left',
            text_size=(None, None),
        )
        self._value = Label(
            text='--',
            font_size=DS.FONT_SMALL,
            bold=True,
            color=DS.TEXT_PRIMARY,
            size_hint_x=0.4,
            halign='right',
            text_size=(None, None),
        )

        self.add_widget(self._dot)
        self.add_widget(self._label)
        self.add_widget(self._value)

    def update(self, value_text, color=DS.SUCCESS):
        """Update displayed value and dot color."""
        self._value.text = str(value_text)
        self._value.color = color
        self._dot.canvas.clear()
        with self._dot.canvas:
            Color(*color)
            self._dot_ellipse = Ellipse(
                pos=(self._dot.x, self._dot.y + dp(10)),
                size=self._dot.size,
            )


# ==============================================================
# KV LAYOUT
# ==============================================================

Builder.load_string('''
<SystemHealthScreen>:
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: 0.06, 0.07, 0.10, 1
            Rectangle:
                pos: self.pos
                size: self.size

        # ---- STATUS BAR ----
        StatusBar:
            BackButton:
                on_release: root.go_back()

            Label:
                text: 'SYSTEM HEALTH'
                font_size: '18sp'
                bold: True
                color: 0.96, 0.97, 0.98, 1
                size_hint_x: 0.5
                halign: 'center'
                text_size: self.size
                valign: 'middle'

            Widget:
                size_hint_x: 0.2

        # ---- GRAPH AREA ----
        BoxLayout:
            orientation: 'vertical'
            padding: [dp(10), dp(6)]
            spacing: dp(6)

            # Top row: CPU Temp + RAM
            BoxLayout:
                orientation: 'horizontal'
                spacing: dp(6)
                size_hint_y: 0.45

                MiniLineGraph:
                    id: cpu_temp_graph
                    max_points: 60
                    y_min: 20
                    y_max: 90
                    line_color: 0.93, 0.27, 0.32, 1
                    label_text: 'CPU TEMP'
                    unit_text: ' C'

                MiniLineGraph:
                    id: ram_graph
                    max_points: 60
                    y_min: 0
                    y_max: 100
                    line_color: 0.33, 0.58, 0.85, 1
                    label_text: 'RAM'
                    unit_text: '%'

            # Bottom row: Disk + CPU %
            BoxLayout:
                orientation: 'horizontal'
                spacing: dp(6)
                size_hint_y: 0.45

                MiniLineGraph:
                    id: disk_graph
                    max_points: 60
                    y_min: 0
                    y_max: 100
                    line_color: 0.98, 0.65, 0.25, 1
                    label_text: 'DISK'
                    unit_text: '%'

                MiniLineGraph:
                    id: cpu_pct_graph
                    max_points: 60
                    y_min: 0
                    y_max: 100
                    line_color: 0.00, 0.82, 0.73, 1
                    label_text: 'CPU LOAD'
                    unit_text: '%'

            # Status badges row
            BoxLayout:
                id: badges_row
                orientation: 'horizontal'
                size_hint_y: 0.1
                spacing: dp(6)
''')


# ==============================================================
# SYSTEM HEALTH SCREEN
# ==============================================================

class SystemHealthScreen(Screen):
    """Real-time system metrics display with rolling graphs."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._update_event = None
        self._badges_built = False
        self._throttle_badge = None
        self._uptime_badge = None
        self._start_time = time.time()

    # ----------------------------------------------------------
    # Lifecycle
    # ----------------------------------------------------------

    def on_enter(self):
        """Start 1-second refresh loop."""
        # Set threshold lines on CPU temp graph
        cpu_graph = self.ids.get('cpu_temp_graph')
        if cpu_graph and not cpu_graph._threshold_lines:
            cpu_graph._threshold_lines = [
                (70, DS.WARNING),
                (80, DS.DANGER),
            ]
        # Set threshold lines on RAM graph
        ram_graph = self.ids.get('ram_graph')
        if ram_graph and not ram_graph._threshold_lines:
            ram_graph._threshold_lines = [
                (75, DS.WARNING),
                (90, DS.DANGER),
            ]
        # Disk thresholds
        disk_graph = self.ids.get('disk_graph')
        if disk_graph and not disk_graph._threshold_lines:
            disk_graph._threshold_lines = [
                (80, DS.WARNING),
                (95, DS.DANGER),
            ]

        if not self._badges_built:
            self._build_badges()

        self._update_event = Clock.schedule_interval(self._update_metrics, 1.0)
        # Immediate first read
        self._update_metrics(0)

    def on_leave(self):
        """Stop refresh loop."""
        if self._update_event:
            self._update_event.cancel()
            self._update_event = None

    def go_back(self):
        app = App.get_running_app()
        if app:
            app.root.current = 'settings'

    # ----------------------------------------------------------
    # Badges
    # ----------------------------------------------------------

    def _build_badges(self):
        """Create status badge widgets in the bottom row."""
        self._badges_built = True
        row = self.ids.get('badges_row')
        if not row:
            return

        self._throttle_badge = _StatusBadge(label_text='THROTTLE')
        self._uptime_badge = _StatusBadge(label_text='UPTIME')

        row.add_widget(self._throttle_badge)
        row.add_widget(self._uptime_badge)

    # ----------------------------------------------------------
    # Metrics update
    # ----------------------------------------------------------

    def _update_metrics(self, dt):
        """Poll system_monitor and feed data to graphs."""
        app = App.get_running_app()
        metrics = {}

        if app and hasattr(app, 'system_monitor') and app.system_monitor:
            try:
                metrics = app.system_monitor.get_metrics()
            except Exception:
                pass

        cpu_temp = metrics.get('cpu_temp', 0)
        ram_pct = metrics.get('ram_pct', 0)
        disk_pct = metrics.get('disk_pct', 0)
        cpu_pct = metrics.get('cpu_pct', 0)
        throttle = metrics.get('throttle_state', 'OK')

        # Feed graphs
        cpu_graph = self.ids.get('cpu_temp_graph')
        if cpu_graph:
            cpu_graph.add_point(cpu_temp)

        ram_graph = self.ids.get('ram_graph')
        if ram_graph:
            ram_graph.add_point(ram_pct)

        disk_graph = self.ids.get('disk_graph')
        if disk_graph:
            disk_graph.add_point(disk_pct)

        cpu_pct_graph = self.ids.get('cpu_pct_graph')
        if cpu_pct_graph:
            cpu_pct_graph.add_point(cpu_pct)

        # Update badges
        if self._throttle_badge:
            if throttle and throttle != 'OK':
                self._throttle_badge.update(str(throttle), DS.DANGER)
            else:
                self._throttle_badge.update('OK', DS.SUCCESS)

        if self._uptime_badge:
            elapsed = time.time() - self._start_time
            hours = int(elapsed // 3600)
            mins = int((elapsed % 3600) // 60)
            self._uptime_badge.update(f'{hours}h {mins}m', DS.TEXT_PRIMARY)
