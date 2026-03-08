"""
Pairing Screen - First Boot Cloud Connection Setup

Shown automatically when the device is NOT paired with the cloud.
Allows the technician to enter:
1. Cloud URL (e.g., https://smartlocker-cloud-xxx.up.railway.app)
2. 6-digit pairing code (from admin panel)

After successful pairing, navigates to the home screen.
"""

from kivy.uix.screenmanager import Screen
from kivy.lang import Builder
from kivy.app import App
from kivy.clock import Clock
from kivy.properties import StringProperty

Builder.load_string('''
<PairingScreen>:
    BoxLayout:
        orientation: 'vertical'

        # ---- STATUS BAR ----
        StatusBar:
            Label:
                text: 'SMARTLOCKER'
                font_size: '20sp'
                bold: True
                color: 1, 1, 1, 1
                size_hint_x: 0.5
                halign: 'left'
                text_size: self.size
                valign: 'middle'

            Label:
                text: 'SETUP'
                font_size: '15sp'
                bold: True
                color: 0.96, 0.63, 0.38, 1
                size_hint_x: 0.5
                halign: 'right'
                text_size: self.size
                valign: 'middle'

        # ---- MAIN CONTENT ----
        BoxLayout:
            orientation: 'vertical'
            padding: [40, 20, 40, 20]
            spacing: 12

            # Title
            Label:
                text: 'Cloud Pairing'
                font_size: '26sp'
                bold: True
                color: 1, 1, 1, 1
                size_hint_y: None
                height: '40dp'
                halign: 'center'
                text_size: self.size

            Label:
                text: 'Enter the cloud URL and pairing code from your admin panel'
                font_size: '14sp'
                color: 0.55, 0.60, 0.68, 1
                size_hint_y: None
                height: '25dp'
                halign: 'center'
                text_size: self.size

            Widget:
                size_hint_y: None
                height: '8dp'

            # Cloud URL
            Label:
                text: 'Cloud URL'
                font_size: '14sp'
                bold: True
                color: 0.75, 0.80, 0.88, 1
                size_hint_y: None
                height: '22dp'
                halign: 'left'
                text_size: self.size

            TextInput:
                id: cloud_url_input
                hint_text: 'https://smartlocker-cloud-xxx.up.railway.app'
                font_size: '16sp'
                multiline: False
                size_hint_y: None
                height: '44dp'
                background_color: 0.09, 0.14, 0.21, 1
                foreground_color: 1, 1, 1, 1
                cursor_color: 0.18, 0.77, 0.71, 1
                hint_text_color: 0.35, 0.40, 0.48, 1
                padding: [12, 10]

            Widget:
                size_hint_y: None
                height: '6dp'

            # Pairing Code
            Label:
                text: 'Pairing Code (6 digits)'
                font_size: '14sp'
                bold: True
                color: 0.75, 0.80, 0.88, 1
                size_hint_y: None
                height: '22dp'
                halign: 'left'
                text_size: self.size

            TextInput:
                id: pairing_code_input
                hint_text: 'e.g. A3K7M2'
                font_size: '28sp'
                multiline: False
                size_hint_y: None
                height: '52dp'
                background_color: 0.09, 0.14, 0.21, 1
                foreground_color: 0.18, 0.77, 0.71, 1
                cursor_color: 0.18, 0.77, 0.71, 1
                hint_text_color: 0.35, 0.40, 0.48, 1
                padding: [12, 8]
                input_filter: lambda text, from_undo: text.upper()
                halign: 'center'

            Widget:
                size_hint_y: None
                height: '8dp'

            # Status message
            Label:
                id: status_label
                text: root.status_text
                font_size: '14sp'
                color: root._status_color
                size_hint_y: None
                height: '25dp'
                halign: 'center'
                text_size: self.size
                markup: True

            # Buttons row
            BoxLayout:
                spacing: 12
                size_hint_y: None
                height: '55dp'

                Button:
                    id: pair_button
                    text: 'PAIR DEVICE'
                    font_size: '18sp'
                    bold: True
                    background_normal: ''
                    background_color: 0.18, 0.77, 0.71, 1
                    color: 1, 1, 1, 1
                    on_release: root.do_pairing()

                Button:
                    text: 'SKIP'
                    font_size: '16sp'
                    background_normal: ''
                    background_color: 0.20, 0.25, 0.35, 1
                    color: 0.6, 0.65, 0.72, 1
                    size_hint_x: 0.35
                    on_release: root.skip_pairing()

            # Info footer
            Label:
                text: root.device_info_text
                font_size: '12sp'
                color: 0.35, 0.40, 0.48, 1
                size_hint_y: None
                height: '20dp'
                halign: 'center'
                text_size: self.size
''')


class PairingScreen(Screen):
    status_text = StringProperty('')
    device_info_text = StringProperty('')
    _status_color = [0.55, 0.60, 0.68, 1]

    def on_enter(self):
        """Called when screen is displayed."""
        app = App.get_running_app()
        self.device_info_text = f"Device: {app.device_id}  |  Mode: {app.mode.upper()}"
        self.status_text = ''
        self._status_color = [0.55, 0.60, 0.68, 1]

    def do_pairing(self):
        """Execute the pairing process."""
        cloud_url = self.ids.cloud_url_input.text.strip()
        pairing_code = self.ids.pairing_code_input.text.strip().upper()

        # Validate inputs
        if not cloud_url:
            self._set_status('Please enter the Cloud URL', error=True)
            return

        if not cloud_url.startswith('http'):
            cloud_url = 'https://' + cloud_url
            self.ids.cloud_url_input.text = cloud_url

        if not pairing_code or len(pairing_code) != 6:
            self._set_status('Pairing code must be exactly 6 characters', error=True)
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
                self._set_status(f'Failed: {error}', error=True)
                self.ids.pair_button.text = 'PAIR DEVICE'
                self.ids.pair_button.disabled = False

        except Exception as e:
            self._set_status(f'Error: {str(e)}', error=True)
            self.ids.pair_button.text = 'PAIR DEVICE'
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
            self._status_color = [0.90, 0.22, 0.27, 1]  # Red
        elif success:
            self._status_color = [0.18, 0.77, 0.71, 1]  # Green
        elif info:
            self._status_color = [0.37, 0.66, 0.83, 1]  # Blue
        else:
            self._status_color = [0.55, 0.60, 0.68, 1]  # Gray
        # Force UI refresh
        self.ids.status_label.color = self._status_color
