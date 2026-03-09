"""
System Health Screen - Real-time system metrics with line graphs.

Displays CPU temperature, RAM usage, disk usage with rolling line charts
drawn using Kivy Canvas API (zero external dependencies).
Also shows system status indicators for clock, power, SD card, throttle.

Accessible from Settings → HEALTH button.
"""

import time

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.graphics import Color, Line, Rectangle, RoundedRectangle, Ellipse
from kivy.lang import Builder
from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp


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

            Label:
                id: live_indicator
                text: ''
                font_size: '11sp'
                color: 0.20, 0.82, 0.48, 1
                size_hint_x: 0.3
                halign: 'right'
                text_size: self.size
                valign: 'middle'
                markup: True

        # ---- SCROLLABLE CONTENT ----
        ScrollView:
            do_scroll_x: False
            bar_color: 0.00, 0.82, 0.73, 0.5
            bar_width: 4

            BoxLayout:
                id: health_content
                orientation: 'vertical'
                padding: [12, 8, 12, 12]
                spacing: 10
                size_hint_y: None
                height: self.minimum_height

                # Content is built dynamically in Python
                # (graphs require Canvas drawing)

                Widget:
                    size_hint_y: None
                    height: '12dp'
''')


class MiniLineGraph(Widget):
    """A compact line graph widget drawn with Kivy Canvas.

    Displays a series of data points as a line chart with optional
    warning and critical threshold lines.
    """

    def __init__(self, warn_threshold=None, crit_threshold=None,
                 y_min=0, y_max=100, line_color=None, **kwargs):
        super().__init__(**kwargs)
        self.warn_threshold = warn_threshold
        self.crit_threshold = crit_threshold
        self.y_min = y_min
        self.y_max = y_max
        self.line_color = line_color or [0.00, 0.82, 0.73, 1]  # Teal
        self._data = []
        self.bind(pos=self._redraw, size=self._redraw)

    def set_data(self, values):
        """Update data points (list of floats, None entries are skipped)."""
        self._data = [v for v in values if v is not None]
        self._redraw()

    def _redraw(self, *args):
        """Redraw the graph on the canvas."""
        self.canvas.clear()

        x0 = self.x + dp(4)
        y0 = self.y + dp(4)
        w = self.width - dp(8)
        h = self.height - dp(8)

        if w <= 0 or h <= 0:
            return

        y_range = self.y_max - self.y_min
        if y_range <= 0:
            y_range = 1

        with self.canvas:
            # Background
            Color(0.07, 0.09, 0.13, 1)
            RoundedRectangle(pos=(self.x, self.y), size=self.size, radius=[6])

            # Grid lines (horizontal, subtle)
            Color(0.12, 0.14, 0.18, 1)
            for i in range(1, 4):
                gy = y0 + (h * i / 4)
                Line(points=[x0, gy, x0 + w, gy], width=1)

            # Warning threshold line (dashed, amber)
            if self.warn_threshold is not None:
                wy = y0 + ((self.warn_threshold - self.y_min) / y_range) * h
                if y0 <= wy <= y0 + h:
                    Color(0.98, 0.76, 0.22, 0.4)
                    Line(
                        points=[x0, wy, x0 + w, wy],
                        width=1,
                        dash_length=6,
                        dash_offset=4,
                    )

            # Critical threshold line (dashed, red)
            if self.crit_threshold is not None:
                cy = y0 + ((self.crit_threshold - self.y_min) / y_range) * h
                if y0 <= cy <= y0 + h:
                    Color(0.93, 0.27, 0.32, 0.5)
                    Line(
                        points=[x0, cy, x0 + w, cy],
                        width=1,
                        dash_length=6,
                        dash_offset=4,
                    )

            # Data line
            if len(self._data) >= 2:
                n = len(self._data)
                points = []
                for i, v in enumerate(self._data):
                    px = x0 + (i / (n - 1)) * w
                    # Clamp value to range
                    clamped = max(self.y_min, min(self.y_max, v))
                    py = y0 + ((clamped - self.y_min) / y_range) * h
                    points.extend([px, py])

                # Area fill (subtle gradient effect)
                Color(self.line_color[0], self.line_color[1],
                      self.line_color[2], 0.08)
                fill_points = list(points)
                # Close the polygon at the bottom
                fill_points.extend([x0 + w, y0, x0, y0])
                # Draw a thin filled area using lines
                for i in range(0, len(points) - 2, 2):
                    x_pt = points[i]
                    y_pt = points[i + 1]
                    Line(points=[x_pt, y0, x_pt, y_pt], width=1)

                # Main line
                Color(*self.line_color)
                Line(points=points, width=1.5)

                # Current value dot (last point)
                if points:
                    last_x = points[-2]
                    last_y = points[-1]
                    Color(*self.line_color)
                    Ellipse(
                        pos=(last_x - dp(3), last_y - dp(3)),
                        size=(dp(6), dp(6)),
                    )

            elif len(self._data) == 1:
                # Single point — draw a dot in the center
                v = max(self.y_min, min(self.y_max, self._data[0]))
                py = y0 + ((v - self.y_min) / y_range) * h
                Color(*self.line_color)
                Ellipse(
                    pos=(x0 + w / 2 - dp(3), py - dp(3)),
                    size=(dp(6), dp(6)),
                )


class MetricCard(BoxLayout):
    """A card showing a metric name, current value, status badge, and graph."""

    def __init__(self, title, unit="", warn=None, crit=None,
                 y_min=0, y_max=100, line_color=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.height = dp(180)
        self.padding = [dp(10), dp(8)]
        self.spacing = dp(4)

        # Card background (drawn via canvas)
        with self.canvas.before:
            Color(0.10, 0.12, 0.16, 1)
            self._bg_rect = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[10]
            )
        self.bind(pos=self._update_bg, size=self._update_bg)

        # ── Header row: title + value + badge ──
        header = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(6))

        self._title_label = Label(
            text=title,
            font_size='13sp',
            bold=True,
            color=[0.33, 0.58, 0.85, 1],
            halign='left',
            text_size=(None, None),
            size_hint_x=0.45,
        )
        self._title_label.bind(
            size=lambda w, s: setattr(w, 'text_size', s)
        )

        self._value_label = Label(
            text='--',
            font_size='20sp',
            bold=True,
            color=[0.96, 0.97, 0.98, 1],
            halign='right',
            text_size=(None, None),
            size_hint_x=0.35,
        )
        self._value_label.bind(
            size=lambda w, s: setattr(w, 'text_size', s)
        )

        self._badge_label = Label(
            text='[color=33d17a]OK[/color]',
            font_size='12sp',
            bold=True,
            markup=True,
            halign='center',
            text_size=(None, None),
            size_hint_x=0.20,
        )
        self._badge_label.bind(
            size=lambda w, s: setattr(w, 'text_size', s)
        )

        header.add_widget(self._title_label)
        header.add_widget(self._value_label)
        header.add_widget(self._badge_label)
        self.add_widget(header)

        # ── Line graph ──
        self._graph = MiniLineGraph(
            warn_threshold=warn,
            crit_threshold=crit,
            y_min=y_min,
            y_max=y_max,
            line_color=line_color or [0.00, 0.82, 0.73, 1],
            size_hint_y=None,
            height=dp(100),
        )
        self.add_widget(self._graph)

        # ── Legend row ──
        legend = BoxLayout(size_hint_y=None, height=dp(16), spacing=dp(8))
        if warn is not None:
            legend.add_widget(Label(
                text=f'Warning: {warn}{unit}',
                font_size='10sp',
                color=[0.98, 0.76, 0.22, 0.6],
                halign='left',
                text_size=(None, None),
            ))
        if crit is not None:
            legend.add_widget(Label(
                text=f'Critical: {crit}{unit}',
                font_size='10sp',
                color=[0.93, 0.27, 0.32, 0.6],
                halign='left',
                text_size=(None, None),
            ))
        if not legend.children:
            legend.add_widget(Widget())  # Spacer
        self.add_widget(legend)

        self._unit = unit
        self._warn = warn
        self._crit = crit

    def _update_bg(self, *args):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def update(self, current_value, history_values):
        """Update the card with current value and history data."""
        if current_value is not None:
            self._value_label.text = f'{current_value:.1f}{self._unit}'

            # Update badge
            if self._crit is not None and current_value >= self._crit:
                self._badge_label.text = '[color=ed4550]CRIT[/color]'
            elif self._warn is not None and current_value >= self._warn:
                self._badge_label.text = '[color=fac238]WARN[/color]'
            else:
                self._badge_label.text = '[color=33d17a]OK[/color]'
        else:
            self._value_label.text = 'N/A'
            self._badge_label.text = '[color=626878]--[/color]'

        self._graph.set_data(history_values)


class StatusCard(BoxLayout):
    """Card showing boolean system status indicators."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.height = dp(140)
        self.padding = [dp(10), dp(8)]
        self.spacing = dp(6)

        with self.canvas.before:
            Color(0.10, 0.12, 0.16, 1)
            self._bg_rect = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[10]
            )
        self.bind(pos=self._update_bg, size=self._update_bg)

        # Title
        self.add_widget(Label(
            text='System Status',
            font_size='13sp',
            bold=True,
            color=[0.33, 0.58, 0.85, 1],
            halign='left',
            text_size=(200, None),
            size_hint_y=None,
            height=dp(22),
        ))

        # Status rows
        self._rows = {}
        for key, label_text in [
            ('clock', 'NTP Clock'),
            ('power', 'Power Supply'),
            ('sd', 'SD Card'),
            ('throttle', 'CPU Throttle'),
        ]:
            row = BoxLayout(size_hint_y=None, height=dp(22), spacing=dp(6))

            dot = Label(
                text='',
                font_size='10sp',
                size_hint_x=0.08,
                markup=True,
            )

            name = Label(
                text=label_text,
                font_size='13sp',
                color=[0.65, 0.68, 0.76, 1],
                halign='left',
                text_size=(None, None),
                size_hint_x=0.42,
            )
            name.bind(size=lambda w, s: setattr(w, 'text_size', s))

            status = Label(
                text='--',
                font_size='13sp',
                bold=True,
                color=[0.38, 0.42, 0.50, 1],
                halign='right',
                text_size=(None, None),
                size_hint_x=0.50,
                markup=True,
            )
            status.bind(size=lambda w, s: setattr(w, 'text_size', s))

            row.add_widget(dot)
            row.add_widget(name)
            row.add_widget(status)
            self.add_widget(row)
            self._rows[key] = (dot, status)

    def _update_bg(self, *args):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def update(self, check_data):
        """Update all status indicators from check_all() result."""
        # Clock sync
        clock_ok = check_data.get('clock_sync', True)
        self._set_row('clock',
                       ok=clock_ok,
                       ok_text='Synced',
                       fail_text='NOT SYNCED')

        # Power
        under_v = check_data.get('under_voltage', False)
        self._set_row('power',
                       ok=not under_v,
                       ok_text='Stable',
                       fail_text='UNDER-VOLTAGE')

        # SD Card
        sd = check_data.get('sd_health', 'ok')
        self._set_row('sd',
                       ok=(sd == 'ok'),
                       ok_text='Healthy',
                       fail_text='ERROR')

        # Throttle
        throttled = check_data.get('cpu_throttled', False)
        self._set_row('throttle',
                       ok=not throttled,
                       ok_text='None',
                       fail_text='THROTTLED')

    def _set_row(self, key, ok, ok_text, fail_text):
        dot, status = self._rows[key]
        if ok:
            dot.text = '[color=33d17a]\u25cf[/color]'
            status.text = f'[color=33d17a]{ok_text}[/color]'
        else:
            dot.text = '[color=ed4550]\u25cf[/color]'
            status.text = f'[color=ed4550]{fail_text}[/color]'


class SystemHealthScreen(Screen):
    """System health dashboard with real-time graphs."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._update_event = None
        self._cards_built = False

        # Card references (built on first enter)
        self._cpu_card = None
        self._ram_card = None
        self._disk_card = None
        self._status_card = None

    def on_enter(self):
        """Start auto-refresh when entering the screen."""
        if not self._cards_built:
            self._build_cards()
            self._cards_built = True

        # Immediate update
        self._refresh_data()

        # Auto-refresh every 5 seconds
        self._update_event = Clock.schedule_interval(
            self._refresh_data, 5
        )

        # Show live indicator
        self.ids.live_indicator.text = '[color=33d17a]\u25cf LIVE[/color]'

    def on_leave(self):
        """Stop auto-refresh when leaving."""
        if self._update_event:
            self._update_event.cancel()
            self._update_event = None

    def _build_cards(self):
        """Create the metric cards and add them to the layout."""
        content = self.ids.health_content

        # CPU Temperature card
        self._cpu_card = MetricCard(
            title='CPU Temperature',
            unit='\u00b0C',
            warn=70,
            crit=80,
            y_min=30,
            y_max=90,
            line_color=[0.98, 0.65, 0.25, 1],  # Amber
        )
        content.add_widget(self._cpu_card, index=1)

        # RAM Usage card
        self._ram_card = MetricCard(
            title='RAM Usage',
            unit='%',
            warn=80,
            crit=90,
            y_min=0,
            y_max=100,
            line_color=[0.33, 0.58, 0.85, 1],  # Blue
        )
        content.add_widget(self._ram_card, index=1)

        # Disk Usage card
        self._disk_card = MetricCard(
            title='Disk Usage',
            unit='%',
            warn=85,
            crit=95,
            y_min=0,
            y_max=100,
            line_color=[0.00, 0.82, 0.73, 1],  # Teal
        )
        content.add_widget(self._disk_card, index=1)

        # System Status card
        self._status_card = StatusCard()
        content.add_widget(self._status_card, index=1)

    def _refresh_data(self, *args):
        """Pull latest data from SystemMonitor and update cards."""
        app = App.get_running_app()
        if not hasattr(app, 'system_monitor'):
            return

        monitor = app.system_monitor
        last = monitor.get_last_check()
        history = monitor.get_history()

        # Extract history arrays
        cpu_history = [h.get('cpu_temp') for h in history
                       if h.get('cpu_temp') is not None]
        ram_history = [h.get('ram_pct') for h in history
                       if h.get('ram_pct') is not None]
        disk_history = [h.get('disk_pct') for h in history
                        if h.get('disk_pct') is not None]

        # Update cards
        if self._cpu_card:
            self._cpu_card.update(last.get('cpu_temp'), cpu_history)

        if self._ram_card:
            self._ram_card.update(last.get('ram_pct'), ram_history)

        if self._disk_card:
            self._disk_card.update(last.get('disk_pct'), disk_history)

        if self._status_card:
            self._status_card.update(last)

    def go_back(self):
        """Navigate back to settings."""
        app = App.get_running_app()
        app.go_screen('settings')
