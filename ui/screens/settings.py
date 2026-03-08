"""
Settings Screen - Device Configuration & Cloud Connection

Shows:
- Device info (ID, mode, uptime)
- Cloud connection status (paired/not paired)
- Sync status (events synced/pending)
- Button to re-pair or change cloud connection
"""

from kivy.uix.screenmanager import Screen
from kivy.lang import Builder
from kivy.app import App
from kivy.clock import Clock
from kivy.properties import StringProperty
import time

Builder.load_string('''
<SettingsScreen>:
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
                text: 'SETTINGS'
                font_size: '15sp'
                bold: True
                color: 0.55, 0.60, 0.68, 1
                size_hint_x: 0.3
                halign: 'center'
                text_size: self.size
                valign: 'middle'

            Button:
                text: 'HOME'
                font_size: '14sp'
                bold: True
                size_hint_x: 0.3
                size_hint_y: None
                height: '36dp'
                background_normal: ''
                background_color: 0.11, 0.29, 0.40, 1
                color: 1, 1, 1, 1
                on_release: app.go_back()

        # ---- SCROLLABLE CONTENT ----
        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: 'vertical'
                padding: [20, 15, 20, 15]
                spacing: 15
                size_hint_y: None
                height: self.minimum_height

                # ==== DEVICE INFO ====
                Label:
                    text: 'Device Information'
                    font_size: '18sp'
                    bold: True
                    color: 0.37, 0.66, 0.83, 1
                    size_hint_y: None
                    height: '30dp'
                    halign: 'left'
                    text_size: self.size

                BoxLayout:
                    orientation: 'vertical'
                    size_hint_y: None
                    height: '100dp'
                    padding: [15, 10]
                    spacing: 4
                    canvas.before:
                        Color:
                            rgba: 0.09, 0.16, 0.24, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [8]

                    Label:
                        id: device_id_label
                        text: 'Device ID: ---'
                        font_size: '14sp'
                        color: 0.75, 0.80, 0.88, 1
                        halign: 'left'
                        text_size: self.size
                        size_hint_y: None
                        height: '20dp'

                    Label:
                        id: mode_label
                        text: 'Mode: ---'
                        font_size: '14sp'
                        color: 0.75, 0.80, 0.88, 1
                        halign: 'left'
                        text_size: self.size
                        size_hint_y: None
                        height: '20dp'

                    Label:
                        id: version_label
                        text: 'Software: v1.0.0'
                        font_size: '14sp'
                        color: 0.55, 0.60, 0.68, 1
                        halign: 'left'
                        text_size: self.size
                        size_hint_y: None
                        height: '20dp'

                    Label:
                        id: events_label
                        text: 'Events: ---'
                        font_size: '14sp'
                        color: 0.55, 0.60, 0.68, 1
                        halign: 'left'
                        text_size: self.size
                        size_hint_y: None
                        height: '20dp'

                # ==== CLOUD CONNECTION ====
                Label:
                    text: 'Cloud Connection'
                    font_size: '18sp'
                    bold: True
                    color: 0.37, 0.66, 0.83, 1
                    size_hint_y: None
                    height: '30dp'
                    halign: 'left'
                    text_size: self.size

                BoxLayout:
                    orientation: 'vertical'
                    size_hint_y: None
                    height: '140dp'
                    padding: [15, 10]
                    spacing: 4
                    canvas.before:
                        Color:
                            rgba: 0.09, 0.16, 0.24, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [8]

                    Label:
                        id: cloud_status_label
                        text: 'Status: Not paired'
                        font_size: '15sp'
                        bold: True
                        color: 0.90, 0.22, 0.27, 1
                        halign: 'left'
                        text_size: self.size
                        size_hint_y: None
                        height: '22dp'

                    Label:
                        id: cloud_url_label
                        text: 'URL: ---'
                        font_size: '13sp'
                        color: 0.55, 0.60, 0.68, 1
                        halign: 'left'
                        text_size: self.size
                        size_hint_y: None
                        height: '20dp'

                    Label:
                        id: vessel_label
                        text: 'Vessel: ---'
                        font_size: '14sp'
                        color: 0.75, 0.80, 0.88, 1
                        halign: 'left'
                        text_size: self.size
                        size_hint_y: None
                        height: '20dp'

                    Label:
                        id: company_label
                        text: 'Company: ---'
                        font_size: '14sp'
                        color: 0.75, 0.80, 0.88, 1
                        halign: 'left'
                        text_size: self.size
                        size_hint_y: None
                        height: '20dp'

                    Label:
                        id: sync_label
                        text: 'Sync: ---'
                        font_size: '13sp'
                        color: 0.55, 0.60, 0.68, 1
                        halign: 'left'
                        text_size: self.size
                        size_hint_y: None
                        height: '20dp'

                # Cloud action buttons
                BoxLayout:
                    spacing: 12
                    size_hint_y: None
                    height: '50dp'

                    Button:
                        id: pair_button
                        text: 'PAIR / RE-PAIR'
                        font_size: '16sp'
                        bold: True
                        background_normal: ''
                        background_color: 0.18, 0.77, 0.71, 1
                        color: 1, 1, 1, 1
                        on_release: root.go_pairing()

                    Button:
                        id: sync_now_button
                        text: 'SYNC NOW'
                        font_size: '16sp'
                        bold: True
                        background_normal: ''
                        background_color: 0.11, 0.29, 0.40, 1
                        color: 1, 1, 1, 1
                        on_release: root.force_sync()

                    Button:
                        id: unpair_button
                        text: 'UNPAIR'
                        font_size: '14sp'
                        background_normal: ''
                        background_color: 0.35, 0.15, 0.15, 1
                        color: 0.90, 0.22, 0.27, 1
                        size_hint_x: 0.35
                        on_release: root.do_unpair()

                # ==== SYSTEM ====
                Label:
                    text: 'System'
                    font_size: '18sp'
                    bold: True
                    color: 0.37, 0.66, 0.83, 1
                    size_hint_y: None
                    height: '30dp'
                    halign: 'left'
                    text_size: self.size

                BoxLayout:
                    spacing: 12
                    size_hint_y: None
                    height: '50dp'

                    Button:
                        text: 'VIEW LOGS'
                        font_size: '16sp'
                        background_normal: ''
                        background_color: 0.20, 0.25, 0.35, 1
                        color: 0.75, 0.80, 0.88, 1
                        on_release: pass

                    Button:
                        text: 'ABOUT'
                        font_size: '16sp'
                        background_normal: ''
                        background_color: 0.20, 0.25, 0.35, 1
                        color: 0.75, 0.80, 0.88, 1
                        on_release: pass
''')


class SettingsScreen(Screen):

    def on_enter(self):
        """Refresh all info when screen is shown."""
        self._refresh_info()
        # Auto-refresh every 5 seconds
        self._refresh_event = Clock.schedule_interval(
            lambda dt: self._refresh_info(), 5.0
        )

    def on_leave(self):
        if hasattr(self, '_refresh_event'):
            self._refresh_event.cancel()

    def _refresh_info(self):
        """Update all labels with current status."""
        app = App.get_running_app()

        # Device info
        self.ids.device_id_label.text = f'Device ID: {app.device_id}'
        self.ids.mode_label.text = f'Mode: {app.mode.upper()}'

        total_events = len(app.event_log)
        self.ids.events_label.text = f'Events in memory: {total_events}'

        # Cloud status
        if app.cloud.is_paired:
            info = app.cloud.get_pairing_info() or {}
            self.ids.cloud_status_label.text = 'Status: PAIRED'
            self.ids.cloud_status_label.color = [0.18, 0.77, 0.71, 1]  # Green

            self.ids.cloud_url_label.text = f"URL: {info.get('cloud_url', '---')}"
            self.ids.vessel_label.text = f"Vessel: {info.get('vessel_name', '---')}"
            self.ids.company_label.text = f"Company: {info.get('company_name', '---')} / {info.get('fleet_name', '---')}"

            # Sync status
            status = app.sync_engine.get_status()
            synced = status.get('events_synced', 0)
            unsynced = status.get('events_unsynced', 0)
            sync_running = 'Active' if status.get('is_syncing') else 'Stopped'
            self.ids.sync_label.text = f'Sync: {sync_running} | {synced} synced, {unsynced} pending'

            self.ids.unpair_button.disabled = False
            self.ids.sync_now_button.disabled = False
        else:
            self.ids.cloud_status_label.text = 'Status: NOT PAIRED'
            self.ids.cloud_status_label.color = [0.90, 0.22, 0.27, 1]  # Red

            self.ids.cloud_url_label.text = 'URL: ---'
            self.ids.vessel_label.text = 'Vessel: ---'
            self.ids.company_label.text = 'Company: ---'
            self.ids.sync_label.text = 'Sync: Disabled (pair first)'

            self.ids.unpair_button.disabled = True
            self.ids.sync_now_button.disabled = True

    def go_pairing(self):
        """Navigate to the pairing screen."""
        app = App.get_running_app()
        app.go_screen('pairing')

    def force_sync(self):
        """Force immediate cloud sync."""
        app = App.get_running_app()
        if app.cloud.is_paired and app.sync_engine.is_running:
            app.sync_engine.force_sync()
            self.ids.sync_label.text = 'Sync: Triggered manual sync...'

    def do_unpair(self):
        """Unpair the device from cloud."""
        app = App.get_running_app()
        app.sync_engine.stop()
        app.cloud.unpair()
        self._refresh_info()
