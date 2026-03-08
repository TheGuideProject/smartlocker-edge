"""
Pairing Screen - First Boot Cloud Connection Setup (2026 Redesign)

Shown automatically when the device is NOT paired with the cloud.
The technician enters ONLY the 6-digit pairing code (from admin panel).
The cloud URL is fixed in config/settings.py.

Design:
- Clean, centered layout with large pairing code input
- Prominent CONNECT button (64dp tall, teal)
- OFFLINE MODE as secondary option
- Status messages with color-coded feedback
- Device info in a subtle footer
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.lang import Builder
from kivy.app import App
from kivy.clock import Clock
from kivy.properties import StringProperty
from kivy.graphics import Color, RoundedRectangle, Rectangle

from config import settings


Builder.load_string('''
<PairingScreen>:
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
                size_hint_x: 0.5
                halign: 'left'
                text_size: self.size
                valign: 'middle'

            Label:
                text: 'FIRST BOOT'
                font_size: '13sp'
                bold: True
                color: 0.98, 0.65, 0.25, 1
                size_hint_x: 0.5
                halign: 'right'
                text_size: self.size
                valign: 'middle'

        # ---- MAIN CONTENT ----
        BoxLayout:
            orientation: 'vertical'
            padding: [50, 15, 50, 12]
            spacing: 8

            # Title area
            Label:
                text: 'Cloud Pairing'
                font_size: '26sp'
                bold: True
                color: 0.96, 0.97, 0.98, 1
                size_hint_y: None
                height: '38dp'
                halign: 'center'
                text_size: self.size

            Label:
                text: 'Enter the 6-digit code from the admin panel'
                font_size: '14sp'
                color: 0.38, 0.42, 0.50, 1
                size_hint_y: None
                height: '22dp'
                halign: 'center'
                text_size: self.size

            Widget:
                size_hint_y: None
                height: '10dp'

            # Pairing code label
            Label:
                text: 'PAIRING CODE'
                font_size: '11sp'
                bold: True
                color: 0.38, 0.42, 0.50, 1
                size_hint_y: None
                height: '16dp'
                halign: 'center'
                text_size: self.size

            # Big pairing code input - centered, large for fat fingers
            BoxLayout:
                size_hint_y: None
                height: '68dp'
                padding: [60, 0]
                TextInput:
                    id: pairing_code_input
                    hint_text: '_ _ _ _ _ _'
                    font_size: '36sp'
                    multiline: False
                    size_hint_y: None
                    height: '68dp'
                    background_color: 0.07, 0.09, 0.13, 1
                    foreground_color: 0.00, 0.82, 0.73, 1
                    cursor_color: 0.00, 0.82, 0.73, 1
                    hint_text_color: 0.20, 0.22, 0.28, 1
                    padding: [12, 12]
                    halign: 'center'

            Widget:
                size_hint_y: None
                height: '6dp'

            # Status message
            Label:
                id: status_label
                text: root.status_text
                font_size: '14sp'
                color: root._status_color
                size_hint_y: None
                height: '24dp'
                halign: 'center'
                text_size: self.size
                markup: True

            # Buttons row
            BoxLayout:
                spacing: 12
                size_hint_y: None
                height: '64dp'

                Button:
                    id: pair_button
                    text: 'CONNECT'
                    font_size: '20sp'
                    bold: True
                    background_normal: ''
                    background_color: 0, 0, 0, 0
                    color: 0.02, 0.05, 0.08, 1
                    on_release: root.do_pairing()
                    canvas.before:
                        Color:
                            rgba: 0.00, 0.82, 0.73, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [12]

                Button:
                    text: 'OFFLINE MODE'
                    font_size: '15sp'
                    bold: True
                    background_normal: ''
                    background_color: 0, 0, 0, 0
                    color: 0.60, 0.64, 0.72, 1
                    size_hint_x: 0.4
                    on_release: root.skip_pairing()
                    canvas.before:
                        Color:
                            rgba: 0.13, 0.15, 0.20, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [12]

            Widget:
                size_hint_y: 1

            # Info footer
            Label:
                text: root.device_info_text
                font_size: '10sp'
                color: 0.25, 0.28, 0.34, 1
                size_hint_y: None
                height: '16dp'
                halign: 'center'
                text_size: self.size
''')


class PairingScreen(Screen):
    status_text = StringProperty('')
    device_info_text = StringProperty('')
    _status_color = [0.38, 0.42, 0.50, 1]

    def on_enter(self):
        """Called when screen is displayed."""
        app = App.get_running_app()
        self.device_info_text = f"Device: {app.device_id}  |  Cloud: {settings.CLOUD_URL}"
        self.status_text = ''
        self._status_color = [0.38, 0.42, 0.50, 1]
        # Reset button state
        self.ids.pair_button.text = 'CONNECT'
        self.ids.pair_button.disabled = False
        self.ids.pairing_code_input.text = ''

    def do_pairing(self):
        """Execute the pairing process."""
        pairing_code = self.ids.pairing_code_input.text.strip().upper()

        # Validate
        if not pairing_code or len(pairing_code) != 6:
            self._set_status('Enter the 6-digit code', error=True)
            return

        # Cloud URL from settings (fixed)
        cloud_url = settings.CLOUD_URL
        if not cloud_url:
            self._set_status('Cloud URL not configured!', error=True)
            return

        # Disable button and show connecting
        self.ids.pair_button.text = 'CONNECTING...'
        self.ids.pair_button.disabled = True
        self._set_status('Connecting to cloud...', info=True)

        # Do pairing in next frame to let UI update
        Clock.schedule_once(
            lambda dt: self._execute_pairing(cloud_url, pairing_code), 0.1
        )

    def _execute_pairing(self, cloud_url, pairing_code):
        """Actually execute the pairing (called after UI update)."""
        app = App.get_running_app()

        try:
            success, data = app.cloud.pair_with_code(cloud_url, pairing_code)

            if success:
                # Save products and recipes to local DB
                config = data.get('config', {})
                self._save_config(app, config)

                vessel = data.get('vessel_name', 'Unknown')
                company = data.get('company_name', 'Unknown')
                self._set_status(
                    f'Paired! Vessel: {vessel} ({company})',
                    success=True
                )

                # Start sync engine
                app.sync_engine.start()

                # Navigate to home after a brief success display
                Clock.schedule_once(lambda dt: self._go_home(), 2.0)
            else:
                error = data.get('detail', 'Unknown error')
                self._set_status(f'{error}', error=True)
                self.ids.pair_button.text = 'CONNECT'
                self.ids.pair_button.disabled = False

        except Exception as e:
            self._set_status(f'Error: {str(e)}', error=True)
            self.ids.pair_button.text = 'CONNECT'
            self.ids.pair_button.disabled = False

    def _save_config(self, app, config):
        """Save downloaded products and recipes to local database."""
        for p in config.get('products', []):
            app.db.upsert_product({
                'product_id': p['id'],
                'ppg_code': p.get('ppg_code', ''),
                'name': p['name'],
                'product_type': p['product_type'],
                'density_g_per_ml': p.get('density_g_per_ml', 1.0),
                'pot_life_minutes': p.get('pot_life_minutes'),
                'hazard_class': p.get('hazard_class', ''),
                'can_sizes_ml': p.get('can_sizes_ml', []),
                'can_tare_weight_g': p.get('can_tare_weight_g', {}),
            })

        for r in config.get('recipes', []):
            app.db.upsert_recipe({
                'recipe_id': r['id'],
                'name': r['name'],
                'base_product_id': r['base_product_id'],
                'hardener_product_id': r['hardener_product_id'],
                'ratio_base': r['ratio_base'],
                'ratio_hardener': r['ratio_hardener'],
                'tolerance_pct': r.get('tolerance_pct', 5.0),
                'thinner_pct_brush': r.get('thinner_pct_brush', 5.0),
                'thinner_pct_roller': r.get('thinner_pct_roller', 5.0),
                'thinner_pct_spray': r.get('thinner_pct_spray', 10.0),
                'recommended_thinner_id': r.get('recommended_thinner_id'),
                'pot_life_minutes': r.get('pot_life_minutes', 480),
            })

        # Save maintenance chart if included
        chart = config.get('maintenance_chart')
        if chart:
            app.db.save_maintenance_chart(chart)
            app.maintenance_chart = chart

        # Reload catalog into mixing engine
        app._reload_catalog_from_db()

    def _go_home(self):
        """Navigate to home screen."""
        app = App.get_running_app()
        app.go_screen('home')

    def skip_pairing(self):
        """Skip pairing and go directly to home (offline mode)."""
        app = App.get_running_app()
        app.go_screen('home')

    def _set_status(self, text, error=False, success=False, info=False):
        """Update the status label with colored text."""
        self.status_text = text
        if error:
            self._status_color = [0.93, 0.27, 0.32, 1]   # Red
        elif success:
            self._status_color = [0.20, 0.82, 0.48, 1]    # Green
        elif info:
            self._status_color = [0.33, 0.58, 0.85, 1]    # Blue
        else:
            self._status_color = [0.38, 0.42, 0.50, 1]    # Gray
        # Force UI refresh
        self.ids.status_label.color = self._status_color
