"""
Home Screen - Main Navigation Hub (2026 Redesign)

Layout (800x480):
+--------------------------------------------------+
| SMARTLOCKER           TEST MODE           14:35   |  44dp status bar
+--------------------------------------------------+
|                                                    |
|  +--------------------------------------------+  |
|  |            PAINT NOW!                       |  |  Hero button 180dp
|  |        Select area & start mixing           |  |  with gradient BG
|  +--------------------------------------------+  |
|                                                    |
|  +----------+  +----------+  +----------+        |
|  | CHECK    |  | INVENTORY|  | SETTINGS |        |  Nav tiles 110dp
|  | CHART    |  |          |  |          |        |
|  +----------+  +----------+  +----------+        |
|                                                    |
|  Slots: 3/4  |  Cloud: ONLINE  |  Mix: IDLE      |  24dp info strip
+--------------------------------------------------+

Design principles:
- Hero "PAINT NOW!" button dominates upper area with teal glow
- Navigation tiles are large, rounded cards with icons (emoji)
- Bottom info strip provides at-a-glance system status
- High contrast, minimal text, game-like feel
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.lang import Builder
from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle, Rectangle, Line
import time


Builder.load_string('''
<HomeScreen>:
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
            Label:
                text: 'SMARTLOCKER'
                font_size: '18sp'
                bold: True
                color: 0.96, 0.97, 0.98, 1
                size_hint_x: 0.35
                halign: 'left'
                text_size: self.size
                valign: 'middle'

            Label:
                id: mode_label
                text: 'TEST MODE'
                font_size: '13sp'
                bold: True
                color: 0.00, 0.82, 0.73, 1
                size_hint_x: 0.35
                halign: 'center'
                text_size: self.size
                valign: 'middle'

            Label:
                id: clock_label
                text: '00:00'
                font_size: '15sp'
                bold: True
                color: 0.60, 0.64, 0.72, 1
                size_hint_x: 0.30
                halign: 'right'
                text_size: self.size
                valign: 'middle'

        # ---- MAIN CONTENT ----
        BoxLayout:
            orientation: 'vertical'
            padding: [12, 8, 12, 6]
            spacing: 8

            # ===== HERO PAINT NOW BUTTON =====
            Button:
                id: hero_btn
                text: 'PAINT NOW!'
                font_size: '34sp'
                bold: True
                background_normal: ''
                background_color: 0, 0, 0, 0
                color: 0.02, 0.05, 0.08, 1
                size_hint_y: None
                height: '160dp'
                on_release: app.go_screen('paint_now')
                canvas.before:
                    # Teal gradient fill
                    Color:
                        rgba: 0.00, 0.72, 0.63, 1
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [16]
                    # Lighter top edge for gradient feel
                    Color:
                        rgba: 0.00, 0.92, 0.82, 0.35
                    RoundedRectangle:
                        pos: self.x + 2, self.y + self.height * 0.55
                        size: self.width - 4, self.height * 0.44
                        radius: [16, 16, 0, 0]
                    # Subtle glow border
                    Color:
                        rgba: 0.00, 0.92, 0.80, 0.3
                    Line:
                        rounded_rectangle: self.x, self.y, self.width, self.height, 16
                        width: 1.2

            # Subtitle under hero
            Label:
                text: 'Select area from chart, calculate paint, start mixing'
                font_size: '12sp'
                color: 0.38, 0.42, 0.50, 1
                size_hint_y: None
                height: '18dp'
                halign: 'center'
                text_size: self.size

            Widget:
                size_hint_y: None
                height: '4dp'

            # ===== NAVIGATION TILES ROW =====
            BoxLayout:
                spacing: 10
                size_hint_y: None
                height: '120dp'

                # -- CHECK CHART tile --
                Button:
                    text: 'CHECK\\nCHART'
                    font_size: '16sp'
                    bold: True
                    background_normal: ''
                    background_color: 0, 0, 0, 0
                    color: 0.96, 0.97, 0.98, 1
                    on_release: app.go_screen('chart_viewer')
                    markup: True
                    halign: 'center'
                    valign: 'center'
                    text_size: self.size
                    canvas.before:
                        Color:
                            rgba: 0.10, 0.12, 0.16, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [12]
                        # Top accent bar
                        Color:
                            rgba: 0.33, 0.58, 0.85, 1
                        RoundedRectangle:
                            pos: self.x + 4, self.y + self.height - 4
                            size: self.width - 8, 3
                            radius: [2]

                # -- INVENTORY tile --
                Button:
                    text: 'INVENTORY'
                    font_size: '16sp'
                    bold: True
                    background_normal: ''
                    background_color: 0, 0, 0, 0
                    color: 0.96, 0.97, 0.98, 1
                    on_release: app.go_screen('inventory')
                    markup: True
                    halign: 'center'
                    valign: 'center'
                    text_size: self.size
                    canvas.before:
                        Color:
                            rgba: 0.10, 0.12, 0.16, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [12]
                        # Top accent bar
                        Color:
                            rgba: 0.20, 0.82, 0.48, 1
                        RoundedRectangle:
                            pos: self.x + 4, self.y + self.height - 4
                            size: self.width - 8, 3
                            radius: [2]

                # -- SETTINGS tile --
                Button:
                    text: 'SETTINGS'
                    font_size: '16sp'
                    bold: True
                    background_normal: ''
                    background_color: 0, 0, 0, 0
                    color: 0.96, 0.97, 0.98, 1
                    on_release: app.go_screen('settings')
                    markup: True
                    halign: 'center'
                    valign: 'center'
                    text_size: self.size
                    canvas.before:
                        Color:
                            rgba: 0.10, 0.12, 0.16, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [12]
                        # Top accent bar
                        Color:
                            rgba: 0.60, 0.64, 0.72, 1
                        RoundedRectangle:
                            pos: self.x + 4, self.y + self.height - 4
                            size: self.width - 8, 3
                            radius: [2]

            # ===== SPACER =====
            Widget:
                size_hint_y: 1

            # ===== ACTIVE MIX INDICATOR (dynamic) =====
            BoxLayout:
                id: mix_indicator
                orientation: 'horizontal'
                size_hint_y: None
                height: '0dp'
                padding: [0, 0]
                spacing: 0

            # ===== BOTTOM STATUS STRIP =====
            BoxLayout:
                size_hint_y: None
                height: '24dp'
                padding: [8, 0]
                canvas.before:
                    Color:
                        rgba: 0.08, 0.09, 0.12, 1
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [6]

                Label:
                    id: slot_summary
                    text: ''
                    font_size: '11sp'
                    color: 0.38, 0.42, 0.50, 1
                    halign: 'center'
                    text_size: self.size
                    valign: 'middle'
                    markup: True
''')


class HomeScreen(Screen):
    device_info = ''

    def on_enter(self):
        """Called when screen is displayed."""
        app = App.get_running_app()
        cloud_status = "CLOUD" if app.cloud.is_paired else "OFFLINE"
        mode_text = app.mode.upper()

        # Update mode label
        self.ids.mode_label.text = f"{mode_text} MODE"
        if cloud_status == "CLOUD":
            self.ids.mode_label.color = (0.33, 0.58, 0.85, 1)  # Blue
            self.ids.mode_label.text = f"{mode_text} | CLOUD"
        else:
            self.ids.mode_label.color = (0.00, 0.82, 0.73, 1)  # Teal

        # Update clock every second
        self._clock_event = Clock.schedule_interval(self._update_clock, 1.0)
        self._update_clock(0)
        self._update_slot_summary()

    def on_leave(self):
        """Called when leaving screen."""
        if hasattr(self, '_clock_event'):
            self._clock_event.cancel()

    def _update_clock(self, dt):
        """Update the clock label."""
        self.ids.clock_label.text = time.strftime('%H:%M')

        # Also refresh slot summary
        self._update_slot_summary()

    def _update_slot_summary(self):
        """Show a brief slot status summary and active mix indicator."""
        app = App.get_running_app()
        slots = app.inventory.get_all_slots()
        occupied = sum(1 for s in slots if s.status.value == 'occupied')
        total = len(slots)
        events = len(app.event_log)

        # Cloud status indicator
        if app.cloud.is_paired:
            cloud = "[color=54a5d4]CLOUD[/color]"
        else:
            cloud = "[color=616980]OFFLINE[/color]"

        summary = f"Slots: {occupied}/{total}   |   Events: {events}   |   {cloud}"

        # Check if mixing is active
        if app.mixing.is_active:
            state = app.mixing.current_state.value.replace('_', ' ').upper()
            summary += f"   |   [color=00d1ba]MIX: {state}[/color]"

        self.ids.slot_summary.text = summary

        # Update active mix indicator bar
        self._update_mix_indicator(app)

    def _update_mix_indicator(self, app):
        """Show or hide the active mix indicator bar."""
        indicator = self.ids.mix_indicator
        is_active = app.mixing.is_active

        if is_active:
            session = app.mixing.session
            state_text = app.mixing.current_state.value.replace('_', ' ').upper()

            # Get recipe name
            recipe_name = ''
            if session and session.recipe_id:
                recipes = getattr(app.mixing, '_recipes', {})
                recipe = recipes.get(session.recipe_id)
                if recipe:
                    recipe_name = recipe.name

            display_name = recipe_name or 'Active Session'

            # Rebuild indicator content only if needed
            if indicator.height < 40:
                indicator.clear_widgets()
                indicator.height = 48
                indicator.padding = [8, 4]
                indicator.spacing = 8

                # Background canvas
                indicator.canvas.before.clear()
                with indicator.canvas.before:
                    Color(0.80, 0.60, 0.00, 0.20)
                    self._mix_indicator_bg = RoundedRectangle(
                        pos=indicator.pos,
                        size=indicator.size,
                        radius=[8],
                    )
                indicator.bind(
                    pos=lambda inst, val: setattr(self._mix_indicator_bg, 'pos', val),
                    size=lambda inst, val: setattr(self._mix_indicator_bg, 'size', val),
                )

                # Status label
                self._mix_indicator_label = Label(
                    text='',
                    font_size='13sp',
                    bold=True,
                    color=(0.95, 0.80, 0.20, 1),
                    size_hint_x=0.7,
                    halign='left',
                    valign='middle',
                    markup=True,
                )
                self._mix_indicator_label.bind(
                    size=self._mix_indicator_label.setter('text_size'),
                )
                indicator.add_widget(self._mix_indicator_label)

                # Resume button
                resume_btn = Button(
                    text='RESUME',
                    font_size='14sp',
                    bold=True,
                    background_normal='',
                    background_color=(0.80, 0.60, 0.00, 1),
                    color=(0.02, 0.05, 0.08, 1),
                    size_hint_x=0.3,
                )
                resume_btn.bind(on_release=lambda x: app.go_screen('mixing'))
                indicator.add_widget(resume_btn)

            # Update the label text every refresh
            if hasattr(self, '_mix_indicator_label'):
                self._mix_indicator_label.text = (
                    f'MIX ACTIVE: [b]{display_name}[/b]  -  {state_text}'
                )
        else:
            # Hide indicator when no active mix
            if indicator.height > 0:
                indicator.clear_widgets()
                indicator.canvas.before.clear()
                indicator.height = 0
                indicator.padding = [0, 0]
                indicator.spacing = 0
