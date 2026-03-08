"""
Home Screen - Main Navigation Hub

Shows 4 large buttons for the primary workflows:
- MIXING ASSISTANT: Start a guided mixing session
- INVENTORY: View current shelf/slot status
- DEMO CONTROLS: Simulate sensor events (TEST mode)
- SETTINGS: System info and configuration
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

        # ---- MAIN CONTENT: 2x2 BUTTON GRID ----
        BoxLayout:
            orientation: 'vertical'
            padding: [20, 15, 20, 15]
            spacing: 12

            # Device info line
            Label:
                text: root.device_info
                font_size: '13sp'
                color: 0.45, 0.50, 0.58, 1
                size_hint_y: None
                height: '22dp'
                halign: 'center'
                text_size: self.size

            # Row 1
            BoxLayout:
                spacing: 12

                Button:
                    text: 'MIXING\\nAssistant'
                    font_size: '22sp'
                    bold: True
                    background_normal: ''
                    background_color: 0.06, 0.35, 0.50, 1
                    color: 1, 1, 1, 1
                    on_release: app.go_screen('mixing')
                    markup: True

                Button:
                    text: 'INVENTORY\\nView'
                    font_size: '22sp'
                    bold: True
                    background_normal: ''
                    background_color: 0.10, 0.30, 0.22, 1
                    color: 1, 1, 1, 1
                    on_release: app.go_screen('inventory')

            # Row 2
            BoxLayout:
                spacing: 12

                Button:
                    text: 'DEMO\\nControls'
                    font_size: '22sp'
                    bold: True
                    background_normal: ''
                    background_color: 0.40, 0.28, 0.10, 1
                    color: 1, 1, 1, 1
                    on_release: app.go_screen('demo')

                Button:
                    text: 'SETTINGS\\n& Info'
                    font_size: '22sp'
                    bold: True
                    background_normal: ''
                    background_color: 0.20, 0.20, 0.30, 1
                    color: 0.8, 0.82, 0.88, 1
                    on_release: app.go_screen('settings')

            # Slot summary at bottom
            Label:
                id: slot_summary
                text: ''
                font_size: '14sp'
                color: 0.55, 0.60, 0.68, 1
                size_hint_y: None
                height: '25dp'
                halign: 'center'
                text_size: self.size
                markup: True
''')


class HomeScreen(Screen):
    device_info = ''

    def on_enter(self):
        """Called when screen is displayed."""
        app = App.get_running_app()
        cloud_status = "CLOUD" if app.cloud.is_paired else "OFFLINE"
        self.device_info = f"Device: {app.device_id} | Mode: {app.mode.upper()} | {cloud_status}"

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

        summary = f"Slots: {occupied}/{total} occupied  |  Events: {events}"

        # Check if mixing is active
        if app.mixing.is_active:
            state = app.mixing.current_state.value.replace('_', ' ').upper()
            summary += f"  |  [color=2ec4b6]MIX: {state}[/color]"

        self.ids.slot_summary.text = summary
