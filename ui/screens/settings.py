"""
Settings Screen - Device Configuration & Cloud Status (2026 Redesign)

Shows:
- Device info card (ID, mode, version, events)
- Cloud connection card (status, vessel, sync)
- Action buttons (pair, sync, unpair)
- System section (logs, about)

Design:
- Card-based layout with section headers
- Color-coded status indicators
- Large action buttons for gloved hands
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.lang import Builder
from kivy.app import App
from kivy.clock import Clock
from kivy.properties import StringProperty
from kivy.graphics import Color, RoundedRectangle, Rectangle
import time


Builder.load_string('''
<SettingsScreen>:
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
                on_release: app.go_back()

            Label:
                text: 'SETTINGS'
                font_size: '18sp'
                bold: True
                color: 0.96, 0.97, 0.98, 1
                size_hint_x: 0.5
                halign: 'center'
                text_size: self.size
                valign: 'middle'

            Widget:
                size_hint_x: 0.3

        # ---- SCROLLABLE CONTENT ----
        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: 'vertical'
                padding: [12, 8, 12, 8]
                spacing: 8
                size_hint_y: None
                height: self.minimum_height

                # ==== DEVICE INFO CARD ====
                Label:
                    text: 'Device Information'
                    font_size: '14sp'
                    bold: True
                    color: 0.33, 0.58, 0.85, 1
                    size_hint_y: None
                    height: '22dp'
                    halign: 'left'
                    text_size: self.size
                    padding: [4, 0]

                BoxLayout:
                    orientation: 'vertical'
                    size_hint_y: None
                    height: '126dp'
                    padding: [14, 8]
                    spacing: 3
                    canvas.before:
                        Color:
                            rgba: 0.10, 0.12, 0.16, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10]

                    Label:
                        id: device_id_label
                        text: 'Device ID: ---'
                        font_size: '13sp'
                        color: 0.65, 0.68, 0.76, 1
                        halign: 'left'
                        text_size: self.size
                        size_hint_y: None
                        height: '18dp'

                    Label:
                        id: mode_label
                        text: 'Mode: ---'
                        font_size: '13sp'
                        color: 0.65, 0.68, 0.76, 1
                        halign: 'left'
                        text_size: self.size
                        size_hint_y: None
                        height: '18dp'

                    Label:
                        id: drivers_label
                        text: 'Drivers: ---'
                        font_size: '12sp'
                        color: 0.38, 0.42, 0.50, 1
                        halign: 'left'
                        text_size: self.size
                        size_hint_y: None
                        height: '18dp'
                        markup: True

                    Label:
                        id: version_label
                        text: 'Software: v1.0.0'
                        font_size: '12sp'
                        color: 0.38, 0.42, 0.50, 1
                        halign: 'left'
                        text_size: self.size
                        size_hint_y: None
                        height: '18dp'

                    Label:
                        id: events_label
                        text: 'Events: ---'
                        font_size: '12sp'
                        color: 0.38, 0.42, 0.50, 1
                        halign: 'left'
                        text_size: self.size
                        size_hint_y: None
                        height: '18dp'

                # ==== CLOUD CONNECTION CARD ====
                Label:
                    text: 'Cloud Connection'
                    font_size: '14sp'
                    bold: True
                    color: 0.33, 0.58, 0.85, 1
                    size_hint_y: None
                    height: '22dp'
                    halign: 'left'
                    text_size: self.size
                    padding: [4, 0]

                BoxLayout:
                    orientation: 'vertical'
                    size_hint_y: None
                    height: '110dp'
                    padding: [14, 8]
                    spacing: 3
                    canvas.before:
                        Color:
                            rgba: 0.10, 0.12, 0.16, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10]

                    Label:
                        id: cloud_status_label
                        text: 'Status: Not paired'
                        font_size: '14sp'
                        bold: True
                        color: 0.93, 0.27, 0.32, 1
                        halign: 'left'
                        text_size: self.size
                        size_hint_y: None
                        height: '20dp'

                    Label:
                        id: cloud_url_label
                        text: 'URL: ---'
                        font_size: '11sp'
                        color: 0.38, 0.42, 0.50, 1
                        halign: 'left'
                        text_size: self.size
                        size_hint_y: None
                        height: '16dp'

                    Label:
                        id: vessel_label
                        text: 'Vessel: ---'
                        font_size: '13sp'
                        color: 0.65, 0.68, 0.76, 1
                        halign: 'left'
                        text_size: self.size
                        size_hint_y: None
                        height: '18dp'

                    Label:
                        id: company_label
                        text: 'Company: ---'
                        font_size: '13sp'
                        color: 0.65, 0.68, 0.76, 1
                        halign: 'left'
                        text_size: self.size
                        size_hint_y: None
                        height: '18dp'

                    Label:
                        id: sync_label
                        text: 'Sync: ---'
                        font_size: '12sp'
                        color: 0.38, 0.42, 0.50, 1
                        halign: 'left'
                        text_size: self.size
                        size_hint_y: None
                        height: '16dp'

                # Cloud action buttons row
                BoxLayout:
                    spacing: 8
                    size_hint_y: None
                    height: '54dp'

                    Button:
                        id: pair_button
                        text: 'PAIR / RE-PAIR'
                        font_size: '15sp'
                        bold: True
                        background_normal: ''
                        background_color: 0, 0, 0, 0
                        color: 0.02, 0.05, 0.08, 1
                        on_release: root.go_pairing()
                        canvas.before:
                            Color:
                                rgba: 0.00, 0.82, 0.73, 1
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [10]

                    Button:
                        id: sync_now_button
                        text: 'SYNC NOW'
                        font_size: '15sp'
                        bold: True
                        background_normal: ''
                        background_color: 0, 0, 0, 0
                        color: 0.96, 0.97, 0.98, 1
                        on_release: root.force_sync()
                        canvas.before:
                            Color:
                                rgba: 0.13, 0.15, 0.20, 1
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [10]

                    Button:
                        id: unpair_button
                        text: 'UNPAIR'
                        font_size: '13sp'
                        bold: True
                        background_normal: ''
                        background_color: 0, 0, 0, 0
                        color: 0.93, 0.27, 0.32, 1
                        size_hint_x: 0.35
                        on_release: root.do_unpair()
                        canvas.before:
                            Color:
                                rgba: 0.16, 0.08, 0.08, 1
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [10]

                # ==== SYSTEM SECTION ====
                Label:
                    text: 'System'
                    font_size: '14sp'
                    bold: True
                    color: 0.33, 0.58, 0.85, 1
                    size_hint_y: None
                    height: '22dp'
                    halign: 'left'
                    text_size: self.size
                    padding: [4, 0]

                BoxLayout:
                    spacing: 8
                    size_hint_y: None
                    height: '48dp'

                    Button:
                        text: 'VIEW LOGS'
                        font_size: '14sp'
                        bold: True
                        background_normal: ''
                        background_color: 0, 0, 0, 0
                        color: 0.60, 0.64, 0.72, 1
                        on_release: pass
                        canvas.before:
                            Color:
                                rgba: 0.10, 0.12, 0.16, 1
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [10]

                    Button:
                        text: 'DEMO'
                        font_size: '14sp'
                        bold: True
                        background_normal: ''
                        background_color: 0, 0, 0, 0
                        color: 0.98, 0.76, 0.22, 1
                        on_release: app.go_screen('demo')
                        canvas.before:
                            Color:
                                rgba: 0.14, 0.12, 0.06, 1
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [10]

                    Button:
                        text: 'ABOUT'
                        font_size: '14sp'
                        bold: True
                        background_normal: ''
                        background_color: 0, 0, 0, 0
                        color: 0.60, 0.64, 0.72, 1
                        on_release: pass
                        canvas.before:
                            Color:
                                rgba: 0.10, 0.12, 0.16, 1
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [10]

                # ==== ADMIN ACCESS ====
                BoxLayout:
                    size_hint_y: None
                    height: '54dp'
                    Button:
                        text: 'ADMIN'
                        font_size: '15sp'
                        bold: True
                        background_normal: ''
                        background_color: 0, 0, 0, 0
                        color: 0.98, 0.65, 0.25, 1
                        on_release: root.open_admin()
                        markup: True
                        canvas.before:
                            Color:
                                rgba: 0.16, 0.12, 0.06, 1
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [10]
''')


from sync.update_manager import read_version


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

        # Mode label with color coding
        mode_upper = app.mode.upper()
        if app.mode == 'hybrid':
            self.ids.mode_label.text = f'Mode: [color=fac238]{mode_upper}[/color]'
            self.ids.mode_label.markup = True
        elif app.mode == 'live':
            self.ids.mode_label.text = f'Mode: [color=33d17a]{mode_upper}[/color]'
            self.ids.mode_label.markup = True
        else:
            self.ids.mode_label.text = f'Mode: {mode_upper}'

        # Driver status (show which are real vs fake)
        if hasattr(app, 'driver_status'):
            parts = []
            for name, status in app.driver_status.items():
                label = name.upper()
                if status == 'real':
                    parts.append(f'[color=33d17a]{label}[/color]')
                else:
                    parts.append(f'[color=616878]{label}[/color]')
            self.ids.drivers_label.text = f'Drivers: {" | ".join(parts)}'
            self.ids.drivers_label.markup = True
        else:
            self.ids.drivers_label.text = f'Drivers: all fake'

        self.ids.version_label.text = f'Software: v{read_version()}'

        total_events = len(app.event_log)
        self.ids.events_label.text = f'Events in memory: {total_events}'

        # Cloud status
        if app.cloud.is_paired:
            info = app.cloud.get_pairing_info() or {}
            self.ids.cloud_status_label.text = 'Status: PAIRED'
            self.ids.cloud_status_label.color = [0.20, 0.82, 0.48, 1]   # Green

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
            self.ids.cloud_status_label.color = [0.93, 0.27, 0.32, 1]  # Red

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

    def open_admin(self):
        """Open the admin screen after password verification."""
        from ui.screens.admin import show_admin_password_dialog
        app = App.get_running_app()
        show_admin_password_dialog(lambda: app.go_screen('admin'))
