"""
Alarm Screen - Full-screen critical error display + warning banner.

Critical alarms take over the entire 800x480 display with a red pulsing
background. The alarm CANNOT be dismissed without acknowledging it.
Warning alarms are shown as a dismissable banner at the top of any screen.

Design (800x480):
+--------------------------------------------------+
|            CRITICAL ERROR                         |  Red bg, pulsing
|                                                   |
|            ERROR CODE: E001                       |  Large white text
|     RFID Reader Disconnected                      |  Title
|                                                   |
|  RFID reader on shelf1 not responding.            |  Details (muted)
|  Check USB connection, restart device.            |  Resolution
|                                                   |
|  +--------------------------------------------+  |
|  |    ACKNOWLEDGE & CONTINUE                  |  |  Teal button
|  +--------------------------------------------+  |
|  +--------------------------------------------+  |
|  |    REQUEST PPG SUPPORT                     |  |  Amber button
|  +--------------------------------------------+  |
|                                                   |
|  Time: 14:35:22  |  Active alarms: 3             |  Footer
+--------------------------------------------------+
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.lang import Builder
from kivy.app import App
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.properties import (
    StringProperty, ListProperty, NumericProperty, BooleanProperty,
)
from kivy.graphics import Color, Rectangle, RoundedRectangle
import time


# ============================================================
# KV LAYOUT - Alarm Screen
# ============================================================

Builder.load_string('''
#:import Animation kivy.animation.Animation

<AlarmScreen>:
    BoxLayout:
        id: alarm_root
        orientation: 'vertical'
        padding: [0, 0]
        spacing: 0
        canvas.before:
            Color:
                rgba: root._bg_color
            Rectangle:
                pos: self.pos
                size: self.size

        # ---- TOP SECTION: Warning icon + title ----
        BoxLayout:
            orientation: 'vertical'
            size_hint_y: None
            height: '80dp'
            padding: [20, 12, 20, 0]

            Label:
                text: root._header_text
                font_size: '28sp'
                bold: True
                color: 1, 1, 1, 1
                halign: 'center'
                valign: 'middle'
                text_size: self.size
                markup: True

            # Alarm counter for multiple alarms
            Label:
                text: root._counter_text
                font_size: '13sp'
                bold: True
                color: 1, 1, 1, 0.7
                size_hint_y: None
                height: '20dp'
                halign: 'center'
                text_size: self.size
                valign: 'middle'

        # ---- ERROR CODE ----
        BoxLayout:
            orientation: 'vertical'
            size_hint_y: None
            height: '60dp'
            padding: [30, 0]

            Label:
                text: root._code_text
                font_size: '36sp'
                bold: True
                color: 1, 1, 1, 1
                halign: 'center'
                valign: 'middle'
                text_size: self.size

            Label:
                text: root._title_text
                font_size: '18sp'
                bold: True
                color: 1, 1, 1, 0.9
                size_hint_y: None
                height: '24dp'
                halign: 'center'
                text_size: self.size
                valign: 'middle'

        Widget:
            size_hint_y: None
            height: '8dp'

        # ---- DETAILS ----
        BoxLayout:
            orientation: 'vertical'
            size_hint_y: None
            height: '56dp'
            padding: [40, 0]

            Label:
                text: root._details_text
                font_size: '14sp'
                color: 1, 1, 1, 0.65
                halign: 'center'
                text_size: self.size
                valign: 'top'
                markup: True

            Label:
                text: root._resolution_text
                font_size: '13sp'
                color: 0.98, 0.76, 0.22, 0.9
                halign: 'center'
                text_size: self.size
                valign: 'top'
                markup: True

        Widget:
            size_hint_y: 1

        # ---- ACTION BUTTONS ----
        BoxLayout:
            orientation: 'vertical'
            size_hint_y: None
            height: '140dp'
            padding: [30, 0, 30, 0]
            spacing: 10

            # Acknowledge button
            Button:
                id: ack_btn
                text: 'ACKNOWLEDGE & CONTINUE'
                font_size: '18sp'
                bold: True
                background_normal: ''
                background_color: 0, 0, 0, 0
                color: 0.02, 0.05, 0.08, 1
                size_hint_y: None
                height: '60dp'
                on_release: root._acknowledge()
                canvas.before:
                    Color:
                        rgba: 0.00, 0.82, 0.73, 1
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [12]

            # Support button
            Button:
                id: support_btn
                text: 'REQUEST PPG SUPPORT'
                font_size: '16sp'
                bold: True
                background_normal: ''
                background_color: 0, 0, 0, 0
                color: 0.06, 0.07, 0.10, 1
                size_hint_y: None
                height: '54dp'
                on_release: root._request_support()
                canvas.before:
                    Color:
                        rgba: 0.98, 0.65, 0.25, 1
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [12]

        # ---- FOOTER ----
        BoxLayout:
            size_hint_y: None
            height: '30dp'
            padding: [20, 4]

            Label:
                id: footer_label
                text: root._footer_text
                font_size: '11sp'
                color: 1, 1, 1, 0.45
                halign: 'center'
                text_size: self.size
                valign: 'middle'
                markup: True


# ============================================================
# WARNING BANNER (non-critical) - overlay on any screen
# ============================================================
<AlarmBanner>:
    orientation: 'horizontal'
    size_hint: (1, None)
    height: '44dp'
    padding: [12, 4]
    spacing: 8
    canvas.before:
        Color:
            rgba: root._banner_color
        Rectangle:
            pos: self.pos
            size: self.size

    Label:
        text: root._banner_text
        font_size: '14sp'
        bold: True
        color: 0.06, 0.07, 0.10, 1
        size_hint_x: 0.75
        halign: 'left'
        text_size: self.size
        valign: 'middle'
        markup: True

    Button:
        text: 'DISMISS'
        font_size: '13sp'
        bold: True
        size_hint_x: 0.25
        background_normal: ''
        background_color: 0, 0, 0, 0.2
        color: 0.06, 0.07, 0.10, 1
        on_release: root.dismiss()
''')


# ============================================================
# ALARM SCREEN CLASS
# ============================================================

class AlarmScreen(Screen):
    """Full-screen critical alarm display."""

    # Properties bound to KV
    _bg_color = ListProperty([0.60, 0.12, 0.15, 1])
    _header_text = StringProperty('CRITICAL ERROR')
    _counter_text = StringProperty('')
    _code_text = StringProperty('')
    _title_text = StringProperty('')
    _details_text = StringProperty('')
    _resolution_text = StringProperty('')
    _footer_text = StringProperty('')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current_alarm_index = 0
        self._critical_alarms = []
        self._pulse_anim = None
        self._clock_event = None

    def on_enter(self):
        """Called when the alarm screen is displayed."""
        self._refresh_alarms()
        self._start_pulse()
        # Update clock every second
        self._clock_event = Clock.schedule_interval(self._tick, 1.0)

    def on_leave(self):
        """Called when leaving the alarm screen."""
        self._stop_pulse()
        if self._clock_event:
            self._clock_event.cancel()
            self._clock_event = None

    def _refresh_alarms(self):
        """Reload the list of critical alarms from the alarm manager."""
        app = App.get_running_app()
        if not hasattr(app, 'alarm_manager'):
            return

        self._critical_alarms = app.alarm_manager.get_critical_alarms()

        if not self._critical_alarms:
            # No critical alarms remaining - go back
            app.dismiss_alarm()
            return

        # Clamp index
        if self._current_alarm_index >= len(self._critical_alarms):
            self._current_alarm_index = 0

        self._show_alarm(self._current_alarm_index)

    def _show_alarm(self, index):
        """Display a specific alarm by index."""
        if not self._critical_alarms:
            return

        alarm = self._critical_alarms[index]
        total = len(self._critical_alarms)

        self._header_text = 'CRITICAL ERROR'
        if total > 1:
            self._counter_text = f'Alarm {index + 1} of {total} -- Tap arrows to cycle'
        else:
            self._counter_text = ''

        self._code_text = f'{alarm.get("error_code", "E???")}'
        self._title_text = alarm.get('error_title', 'Unknown Error')
        self._details_text = alarm.get('details', '')
        self._resolution_text = alarm.get('resolution', '')

        # If resolution is not in the alarm dict, get from error_codes
        if not self._resolution_text:
            try:
                from core.error_codes import get_error_by_code
                ec = get_error_by_code(alarm.get('error_code', ''))
                if ec:
                    self._resolution_text = ec.resolution
            except Exception:
                pass

    def _tick(self, dt):
        """Update footer every second."""
        app = App.get_running_app()
        now = time.strftime('%H:%M:%S')
        alarm_count = app.alarm_manager.active_count() if hasattr(app, 'alarm_manager') else 0
        self._footer_text = f'Time: {now}   |   Active alarms: {alarm_count}'

    # ---- Pulsing background animation ----

    def _start_pulse(self):
        """Start the red background pulsing animation."""
        self._stop_pulse()  # Clear any existing
        # Pulse between dark red and brighter red
        anim = (
            Animation(_bg_color=[0.78, 0.15, 0.18, 1], duration=0.8, t='in_out_sine')
            + Animation(_bg_color=[0.50, 0.08, 0.10, 1], duration=0.8, t='in_out_sine')
        )
        anim.repeat = True
        anim.start(self)
        self._pulse_anim = anim

    def _stop_pulse(self):
        """Stop the pulsing animation."""
        if self._pulse_anim:
            self._pulse_anim.stop(self)
            self._pulse_anim = None

    # ---- Actions ----

    def _acknowledge(self):
        """User acknowledges the current critical alarm."""
        app = App.get_running_app()
        if not hasattr(app, 'alarm_manager') or not self._critical_alarms:
            app.dismiss_alarm()
            return

        alarm = self._critical_alarms[self._current_alarm_index]
        alarm_id = alarm.get('alarm_id')
        if alarm_id:
            app.alarm_manager.acknowledge_alarm(alarm_id)

        # Remove from local list
        self._critical_alarms.pop(self._current_alarm_index)

        if self._critical_alarms:
            # More critical alarms remain - show the next one
            if self._current_alarm_index >= len(self._critical_alarms):
                self._current_alarm_index = 0
            self._show_alarm(self._current_alarm_index)
        else:
            # All critical alarms acknowledged - return to previous screen
            self._stop_pulse()
            app.dismiss_alarm()

    def _request_support(self):
        """Send a support request for the current alarm."""
        app = App.get_running_app()
        if not hasattr(app, 'alarm_manager') or not self._critical_alarms:
            return

        alarm = self._critical_alarms[self._current_alarm_index]
        alarm_id = alarm.get('alarm_id')
        if alarm_id:
            app.alarm_manager.request_support(alarm_id)

            # Also send to cloud if available
            if hasattr(app, 'cloud') and app.cloud.is_paired:
                try:
                    app.cloud.send_support_request(alarm)
                except Exception:
                    pass

        # Update button text to show confirmation
        self.ids.support_btn.text = 'SUPPORT REQUESTED'
        self.ids.support_btn.disabled = True

        # Reset button after 3 seconds
        Clock.schedule_once(self._reset_support_btn, 3.0)

    def _reset_support_btn(self, dt):
        """Reset the support button after confirmation."""
        if self.ids.support_btn:
            self.ids.support_btn.text = 'REQUEST PPG SUPPORT'
            self.ids.support_btn.disabled = False

    def cycle_alarm(self, direction=1):
        """Cycle through multiple critical alarms."""
        if len(self._critical_alarms) <= 1:
            return
        self._current_alarm_index = (
            (self._current_alarm_index + direction) % len(self._critical_alarms)
        )
        self._show_alarm(self._current_alarm_index)

    def on_touch_down(self, touch):
        """Handle swipe to cycle through alarms."""
        # Only intercept horizontal swipes in the middle area (not on buttons)
        if touch.y > self.height * 0.35:
            self._touch_start_x = touch.x
            return super().on_touch_down(touch)
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        """Detect swipe completion for cycling alarms."""
        if hasattr(self, '_touch_start_x') and touch.y > self.height * 0.35:
            dx = touch.x - self._touch_start_x
            if abs(dx) > 80:  # Minimum swipe distance
                if dx > 0:
                    self.cycle_alarm(-1)  # Swipe right = previous
                else:
                    self.cycle_alarm(1)   # Swipe left = next
                return True
        return super().on_touch_up(touch)


# ============================================================
# ALARM BANNER - Non-blocking warning overlay
# ============================================================

class AlarmBanner(BoxLayout):
    """
    Warning banner shown at the top of any screen for non-critical alarms.

    Usage:
        banner = AlarmBanner()
        banner.show_warning("Stock low: SIGMACOVER 280 below 25%")
        some_layout.add_widget(banner, index=len(some_layout.children))
    """

    _banner_text = StringProperty('')
    _banner_color = ListProperty([0.98, 0.76, 0.22, 1])  # Warning yellow

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._dismiss_event = None
        self._alarm_data = None

    def show_warning(self, text, alarm_data=None, auto_dismiss_s=15):
        """Show a warning banner with optional auto-dismiss."""
        self._banner_text = text
        self._banner_color = [0.98, 0.76, 0.22, 1]  # Amber/yellow
        self._alarm_data = alarm_data

        if auto_dismiss_s > 0:
            if self._dismiss_event:
                self._dismiss_event.cancel()
            self._dismiss_event = Clock.schedule_once(
                lambda dt: self.dismiss(), auto_dismiss_s
            )

    def show_error(self, text, alarm_data=None):
        """Show a red error banner (not auto-dismissed)."""
        self._banner_text = text
        self._banner_color = [0.93, 0.27, 0.32, 1]  # Danger red
        self._alarm_data = alarm_data

    def dismiss(self):
        """Remove this banner from its parent."""
        if self._dismiss_event:
            self._dismiss_event.cancel()
            self._dismiss_event = None

        if self.parent:
            self.parent.remove_widget(self)

    def on_touch_down(self, touch):
        """Tapping the banner area opens alarm details."""
        if self.collide_point(*touch.pos):
            # If it's a critical alarm banner, navigate to alarm screen
            app = App.get_running_app()
            if hasattr(app, 'alarm_manager') and app.alarm_manager.has_critical():
                app.go_screen('alarm')
                return True
        return super().on_touch_down(touch)
