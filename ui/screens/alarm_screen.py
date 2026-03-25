"""
Alarm Screen - Full-screen alarm display for critical errors (2026 Redesign)

Shows active alarms with:
- Red pulsing background for critical severity, amber for warnings
- Large error code + title + description
- Resolution steps
- ACKNOWLEDGE button (teal, 64dp)
- REQUEST PPG SUPPORT button (amber)

Data: app.alarm_manager.get_active_alarms(), app.alarm_manager.acknowledge(alarm_id)
Navigation: app._previous_screen to return after acknowledge
"""

import logging

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.lang import Builder
from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.animation import Animation
from kivy.properties import NumericProperty

from ui.app import DS

logger = logging.getLogger("smartlocker.alarm")


# ==============================================================
# KV LAYOUT
# ==============================================================

Builder.load_string('''
<AlarmScreen>:
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: root._bg_r, root._bg_g, root._bg_b, root._bg_a
            Rectangle:
                pos: self.pos
                size: self.size

        # ---- TOP STRIP ----
        BoxLayout:
            size_hint_y: None
            height: '44dp'
            padding: [dp(12), dp(4)]
            canvas.before:
                Color:
                    rgba: 0, 0, 0, 0.4
                Rectangle:
                    pos: self.pos
                    size: self.size

            Label:
                text: 'ALARM'
                font_size: '18sp'
                bold: True
                color: 1, 1, 1, 1
                size_hint_x: 0.5
                halign: 'center'
                text_size: self.size
                valign: 'middle'

            Label:
                id: alarm_count_label
                text: ''
                font_size: '13sp'
                bold: True
                color: 1, 1, 1, 0.7
                size_hint_x: 0.5
                halign: 'right'
                text_size: self.size
                valign: 'middle'

        # ---- ALARM CONTENT ----
        ScrollView:
            do_scroll_x: False
            bar_width: '4dp'
            bar_color: 1, 1, 1, 0.3

            BoxLayout:
                id: alarm_content
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: [dp(16), dp(12)]
                spacing: dp(12)

        # ---- BOTTOM BUTTONS ----
        BoxLayout:
            size_hint_y: None
            height: dp(80)
            padding: [dp(12), dp(8)]
            spacing: dp(8)
            canvas.before:
                Color:
                    rgba: 0, 0, 0, 0.3
                Rectangle:
                    pos: self.pos
                    size: self.size

            Button:
                id: ack_btn
                text: 'ACKNOWLEDGE'
                font_size: '17sp'
                bold: True
                size_hint_x: 0.55
                background_normal: ''
                background_color: 0.00, 0.82, 0.73, 1
                color: 0.06, 0.07, 0.10, 1
                on_release: root.acknowledge_current()

            Button:
                id: support_btn
                text: 'REQUEST PPG SUPPORT'
                font_size: '14sp'
                bold: True
                size_hint_x: 0.45
                background_normal: ''
                background_color: 0.98, 0.65, 0.25, 1
                color: 0.06, 0.07, 0.10, 1
                on_release: root.request_support()
''')


# ==============================================================
# ALARM CARD WIDGET
# ==============================================================

class _AlarmCard(BoxLayout):
    """Single alarm display card with error code, title, description, and steps."""

    def __init__(self, alarm, **kwargs):
        super().__init__(
            orientation='vertical',
            size_hint_y=None,
            spacing=dp(6),
            padding=dp(14),
            **kwargs,
        )
        self._alarm = alarm
        self.bind(minimum_height=self.setter('height'))

        # Card background with slight transparency
        with self.canvas.before:
            Color(0, 0, 0, 0.35)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(DS.RADIUS)])
        self.bind(pos=lambda w, v: setattr(w._bg, 'pos', v),
                  size=lambda w, v: setattr(w._bg, 'size', v))

        # Extract alarm fields with safe defaults
        code = getattr(alarm, 'code', getattr(alarm, 'error_code', 'E000'))
        title = getattr(alarm, 'title', getattr(alarm, 'message', 'Unknown Alarm'))
        description = getattr(alarm, 'description', getattr(alarm, 'detail', ''))
        severity = getattr(alarm, 'severity', 'critical')
        steps = getattr(alarm, 'resolution_steps', getattr(alarm, 'steps', []))
        if isinstance(steps, str):
            steps = [steps]

        # Severity badge
        sev_color = DS.DANGER if severity == 'critical' else DS.WARNING
        sev_text = severity.upper() if severity else 'CRITICAL'

        sev_row = BoxLayout(size_hint_y=None, height=dp(26), spacing=dp(8))
        sev_badge_lbl = Label(
            text=f'  {sev_text}  ',
            font_size=DS.FONT_TINY,
            bold=True,
            color=(1, 1, 1, 1),
            size_hint_x=None,
            width=dp(80),
            halign='center',
            text_size=(dp(80), dp(22)),
            valign='middle',
        )
        with sev_badge_lbl.canvas.before:
            Color(*sev_color)
            sev_badge_lbl._sev_bg = RoundedRectangle(
                pos=sev_badge_lbl.pos, size=sev_badge_lbl.size, radius=[dp(4)])
        sev_badge_lbl.bind(
            pos=lambda w, v: setattr(w._sev_bg, 'pos', v),
            size=lambda w, v: setattr(w._sev_bg, 'size', v),
        )
        sev_row.add_widget(sev_badge_lbl)
        sev_row.add_widget(Widget())
        self.add_widget(sev_row)

        # Error code (large)
        self.add_widget(Label(
            text=str(code),
            font_size=DS.FONT_HERO,
            bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(50),
            halign='center',
            text_size=(None, None),
        ))

        # Title
        self.add_widget(Label(
            text=str(title),
            font_size=DS.FONT_H2,
            bold=True,
            color=(1, 1, 1, 0.95),
            size_hint_y=None,
            height=dp(32),
            halign='center',
            text_size=(None, None),
        ))

        # Description
        if description:
            desc_lbl = Label(
                text=str(description),
                font_size=DS.FONT_BODY,
                color=(1, 1, 1, 0.75),
                size_hint_y=None,
                halign='center',
                text_size=(dp(350), None),
                valign='top',
            )
            desc_lbl.bind(texture_size=lambda w, s: setattr(w, 'height', s[1] + dp(8)))
            self.add_widget(desc_lbl)

        # Resolution steps
        if steps:
            self.add_widget(Widget(size_hint_y=None, height=dp(6)))
            self.add_widget(Label(
                text='RESOLUTION STEPS:',
                font_size=DS.FONT_SMALL,
                bold=True,
                color=(1, 1, 1, 0.6),
                size_hint_y=None,
                height=dp(22),
                halign='left',
                text_size=(None, None),
            ))
            for i, step in enumerate(steps, 1):
                step_lbl = Label(
                    text=f'{i}. {step}',
                    font_size=DS.FONT_SMALL,
                    color=(1, 1, 1, 0.8),
                    size_hint_y=None,
                    halign='left',
                    text_size=(dp(340), None),
                    valign='top',
                )
                step_lbl.bind(texture_size=lambda w, s: setattr(w, 'height', s[1] + dp(4)))
                self.add_widget(step_lbl)


# ==============================================================
# ALARM SCREEN
# ==============================================================

class AlarmScreen(Screen):
    """Full-screen alarm display with pulsing background."""

    _bg_r = NumericProperty(0.25)
    _bg_g = NumericProperty(0.05)
    _bg_b = NumericProperty(0.05)
    _bg_a = NumericProperty(1.0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._pulse_anim = None
        self._active_alarms = []
        self._current_alarm_index = 0

    # ----------------------------------------------------------
    # Lifecycle
    # ----------------------------------------------------------

    def on_enter(self):
        """Load alarms and start pulse animation."""
        self._load_alarms()
        self._render_alarms()
        self._start_pulse()

    def on_leave(self):
        """Stop pulse animation."""
        self._stop_pulse()

    # ----------------------------------------------------------
    # Alarm loading
    # ----------------------------------------------------------

    def _load_alarms(self):
        """Fetch active alarms from alarm_manager."""
        app = App.get_running_app()
        self._active_alarms = []
        if app and hasattr(app, 'alarm_manager') and app.alarm_manager:
            try:
                alarms = app.alarm_manager.get_active_alarms()
                if alarms:
                    self._active_alarms = list(alarms)
            except Exception as e:
                logger.warning(f"Could not fetch alarms: {e}")

        self._current_alarm_index = 0

    def _render_alarms(self):
        """Display alarm cards in the content area."""
        content = self.ids.get('alarm_content')
        if not content:
            return
        content.clear_widgets()

        count_lbl = self.ids.get('alarm_count_label')

        if not self._active_alarms:
            # No active alarms - show all-clear
            self._set_bg_color('ok')
            content.add_widget(Widget(size_hint_y=None, height=dp(60)))
            content.add_widget(Label(
                text='ALL CLEAR',
                font_size=DS.FONT_HERO,
                bold=True,
                color=DS.SUCCESS,
                size_hint_y=None,
                height=dp(60),
                halign='center',
                text_size=(None, None),
            ))
            content.add_widget(Label(
                text='No active alarms',
                font_size=DS.FONT_BODY,
                color=DS.TEXT_SECONDARY,
                size_hint_y=None,
                height=dp(30),
                halign='center',
                text_size=(None, None),
            ))
            if count_lbl:
                count_lbl.text = ''
            return

        # Determine highest severity for background color
        has_critical = any(
            getattr(a, 'severity', 'critical') == 'critical'
            for a in self._active_alarms
        )
        self._set_bg_color('critical' if has_critical else 'warning')

        if count_lbl:
            count_lbl.text = f'{len(self._active_alarms)} ACTIVE'

        # Render each alarm
        for alarm in self._active_alarms:
            card = _AlarmCard(alarm)
            content.add_widget(card)
            content.add_widget(Widget(size_hint_y=None, height=dp(4)))

    # ----------------------------------------------------------
    # Background color / pulse
    # ----------------------------------------------------------

    def _set_bg_color(self, level):
        """Set base background color by severity level."""
        if level == 'critical':
            self._bg_r, self._bg_g, self._bg_b = 0.35, 0.05, 0.05
        elif level == 'warning':
            self._bg_r, self._bg_g, self._bg_b = 0.35, 0.22, 0.05
        else:
            self._bg_r, self._bg_g, self._bg_b = DS.BG_DARK[0], DS.BG_DARK[1], DS.BG_DARK[2]

    def _start_pulse(self):
        """Start a pulsing background animation."""
        self._stop_pulse()
        if not self._active_alarms:
            return

        has_critical = any(
            getattr(a, 'severity', 'critical') == 'critical'
            for a in self._active_alarms
        )

        if has_critical:
            bright_r, bright_g, bright_b = 0.55, 0.08, 0.08
            dim_r, dim_g, dim_b = 0.25, 0.03, 0.03
        else:
            bright_r, bright_g, bright_b = 0.50, 0.30, 0.08
            dim_r, dim_g, dim_b = 0.25, 0.15, 0.03

        anim_bright = Animation(_bg_r=bright_r, _bg_g=bright_g, _bg_b=bright_b, duration=0.8)
        anim_dim = Animation(_bg_r=dim_r, _bg_g=dim_g, _bg_b=dim_b, duration=0.8)
        self._pulse_anim = anim_bright + anim_dim
        self._pulse_anim.repeat = True
        self._pulse_anim.start(self)

    def _stop_pulse(self):
        """Stop the pulse animation."""
        if self._pulse_anim:
            self._pulse_anim.stop(self)
            self._pulse_anim = None

    # ----------------------------------------------------------
    # Actions
    # ----------------------------------------------------------

    def acknowledge_current(self):
        """Acknowledge all active alarms and return to previous screen."""
        app = App.get_running_app()
        if app and hasattr(app, 'alarm_manager') and app.alarm_manager:
            for alarm in self._active_alarms:
                alarm_id = getattr(alarm, 'alarm_id', getattr(alarm, 'id', None))
                if alarm_id:
                    try:
                        app.alarm_manager.acknowledge(alarm_id)
                    except Exception as e:
                        logger.warning(f"Could not acknowledge alarm {alarm_id}: {e}")

        self._active_alarms.clear()
        self._stop_pulse()

        # Navigate back
        if app:
            prev = getattr(app, '_previous_screen', 'home')
            app.root.current = prev if prev else 'home'

    def request_support(self):
        """Send a support request to PPG cloud for the active alarms."""
        app = App.get_running_app()
        if not app:
            return

        alarm_codes = []
        for alarm in self._active_alarms:
            code = getattr(alarm, 'code', getattr(alarm, 'error_code', 'E000'))
            alarm_codes.append(str(code))

        # Attempt to send via cloud client
        if hasattr(app, 'cloud_client') and app.cloud_client:
            try:
                app.cloud_client.send_support_request(
                    device_id=getattr(app, 'device_id', 'unknown'),
                    alarm_codes=alarm_codes,
                    message=f'Support requested for alarms: {", ".join(alarm_codes)}',
                )
                logger.info(f"Support request sent for alarms: {alarm_codes}")
            except Exception as e:
                logger.warning(f"Could not send support request: {e}")

        # Visual feedback - briefly change button text
        btn = self.ids.get('support_btn')
        if btn:
            original = btn.text
            btn.text = 'REQUEST SENT'
            btn.background_color = DS.SUCCESS
            Clock.schedule_once(lambda dt: self._reset_support_btn(btn, original), 2.0)

    @staticmethod
    def _reset_support_btn(btn, original_text):
        """Reset support button after feedback."""
        btn.text = original_text
        btn.background_color = DS.ACCENT
