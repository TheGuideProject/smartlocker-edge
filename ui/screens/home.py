"""
Home Screen - Main Navigation Hub

Redesigned layout:
- PAINT NOW! as primary big button (top half)
- CHECK CHART, INVENTORY, SETTINGS as secondary row
- Info bar at bottom with slot counts and cloud status
"""

from kivy.uix.screenmanager import Screen
from kivy.lang import Builder
from kivy.app import App
from kivy.clock import Clock
import time

Builder.load_string('''
<HomeScreen>:
    BoxLayout:
        orientation: 'vertical'

        # ---- STATUS BAR ----
        StatusBar:
            Label:
                text: 'SMARTLOCKER'
                font_size: '20sp'
                bold: True
                color: 1, 1, 1, 1
                size_hint_x: 0.4
                halign: 'left'
                text_size: self.size
                valign: 'middle'

            Label:
                id: mode_label
                text: 'TEST MODE'
                font_size: '15sp'
                bold: True
                color: 0.18, 0.77, 0.71, 1
                size_hint_x: 0.3
                halign: 'center'
                text_size: self.size
                valign: 'middle'

            Label:
                id: clock_label
                text: '00:00'
                font_size: '15sp'
                color: 0.55, 0.60, 0.68, 1
                size_hint_x: 0.3
                halign: 'right'
                text_size: self.size
                valign: 'middle'

        # ---- MAIN CONTENT ----
        BoxLayout:
            orientation: 'vertical'
            padding: [15, 10, 15, 10]
            spacing: 10

            # ===== PAINT NOW! - BIG PRIMARY BUTTON =====
            Button:
                text: 'PAINT NOW!'
                font_size: '36sp'
                bold: True
                background_normal: ''
                background_color: 0.18, 0.77, 0.71, 1
                color: 1, 1, 1, 1
                size_hint_y: 0.45
                on_release: app.go_screen('paint_now')

            # Subtitle for Paint Now
            Label:
                text: 'Select area, calculate paint, start mixing'
                font_size: '13sp'
                color: 0.45, 0.55, 0.60, 1
                size_hint_y: None
                height: '20dp'
                halign: 'center'
                text_size: self.size

            # ===== SECONDARY BUTTONS ROW =====
            BoxLayout:
                spacing: 10
                size_hint_y: 0.30

                # CHECK CHART
                Button:
                    text: 'CHECK\\nCHART'
                    font_size: '18sp'
                    bold: True
                    background_normal: ''
                    background_color: 0.11, 0.29, 0.40, 1
                    color: 1, 1, 1, 1
                    on_release: app.go_screen('chart_viewer')
                    markup: True

                # INVENTORY
                Button:
                    text: 'INVENTORY\\nView'
                    font_size: '18sp'
                    bold: True
                    background_normal: ''
                    background_color: 0.10, 0.30, 0.22, 1
                    color: 1, 1, 1, 1
                    on_release: app.go_screen('inventory')
                    markup: True

                # SETTINGS
                Button:
                    text: 'SETTINGS\\n& Info'
                    font_size: '18sp'
                    bold: True
                    background_normal: ''
                    background_color: 0.20, 0.20, 0.30, 1
                    color: 0.8, 0.82, 0.88, 1
                    on_release: app.go_screen('settings')
                    markup: True

            # ===== BOTTOM INFO BAR =====
            BoxLayout:
                size_hint_y: None
                height: '30dp'
                padding: [5, 0]

                Label:
                    id: slot_summary
                    text: ''
                    font_size: '13sp'
                    color: 0.45, 0.50, 0.58, 1
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
            self.ids.mode_label.color = (0.37, 0.66, 0.83, 1)  # Blue
            self.ids.mode_label.text = f"{mode_text} | CLOUD"
        else:
            self.ids.mode_label.color = (0.18, 0.77, 0.71, 1)  # Teal

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
        """Show a brief slot status summary."""
        app = App.get_running_app()
        slots = app.inventory.get_all_slots()
        occupied = sum(1 for s in slots if s.status.value == 'occupied')
        total = len(slots)
        events = len(app.event_log)

        cloud = "[color=5fa8d3]CLOUD[/color]" if app.cloud.is_paired else "[color=8d99ae]OFFLINE[/color]"
        summary = f"Slots: {occupied}/{total}  |  Events: {events}  |  {cloud}"

        # Check if mixing is active
        if app.mixing.is_active:
            state = app.mixing.current_state.value.replace('_', ' ').upper()
            summary += f"  |  [color=2ec4b6]MIX: {state}[/color]"

        self.ids.slot_summary.text = summary
