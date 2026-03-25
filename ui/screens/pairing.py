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

import logging

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.metrics import dp
from kivy.properties import StringProperty, ListProperty

from ui.app import DS
from config import settings

logger = logging.getLogger("smartlocker")


def _card_bg(widget, color, radius=12):
    """Attach a rounded-rectangle background that tracks pos/size."""
    with widget.canvas.before:
        Color(*color)
        rr = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[radius])
    widget.bind(
        pos=lambda w, p: setattr(rr, 'pos', p),
        size=lambda w, s: setattr(rr, 'size', s),
    )


class PairingScreen(Screen):
    status_text = StringProperty('')
    status_color = ListProperty(list(DS.TEXT_MUTED))
    device_info_text = StringProperty('')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._keyboard = None
        self._code_input = None
        self._connect_btn = None

    # ================================================================
    # SCREEN LIFECYCLE
    # ================================================================

    def on_enter(self):
        """Build the full UI from scratch each time we enter."""
        app = App.get_running_app()
        self.device_info_text = (
            f"Device: {app.device_id}  |  v{self._get_version()}  |  "
            f"Cloud: {settings.CLOUD_URL}"
        )
        self.status_text = ''
        self.status_color = list(DS.TEXT_MUTED)
        self._build_ui()

    def on_leave(self):
        """Cleanup when leaving the screen."""
        self._hide_keyboard()

    # ================================================================
    # UI CONSTRUCTION
    # ================================================================

    def _build_ui(self):
        self.clear_widgets()

        # Root container with dark background
        root = BoxLayout(orientation='vertical')
        with root.canvas.before:
            Color(*DS.BG_DARK)
            self._root_bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(
            pos=lambda w, p: setattr(self._root_bg, 'pos', p),
            size=lambda w, s: setattr(self._root_bg, 'size', s),
        )

        # ---- STATUS BAR ----
        status_bar = BoxLayout(
            size_hint_y=None, height=dp(DS.STATUS_BAR_H),
            padding=[dp(12), dp(4)], spacing=dp(8),
        )
        with status_bar.canvas.before:
            Color(*DS.BG_STATUS_BAR)
            sb_bg = Rectangle(pos=status_bar.pos, size=status_bar.size)
            Color(*DS.PRIMARY + (0.25,) if len(DS.PRIMARY) == 3 else DS.PRIMARY[:3] + (0.25,))
            sb_line = Rectangle(pos=status_bar.pos, size=(status_bar.width, 1))
        status_bar.bind(
            pos=lambda w, p: (setattr(sb_bg, 'pos', p), setattr(sb_line, 'pos', p)),
            size=lambda w, s: (setattr(sb_bg, 'size', s), setattr(sb_line, 'size', (s[0], 1))),
        )

        status_bar.add_widget(Label(
            text='SMARTLOCKER', font_size=DS.FONT_H2, bold=True,
            color=DS.TEXT_PRIMARY, size_hint_x=0.5,
            halign='left', valign='middle', text_size=(dp(300), None),
        ))
        status_bar.add_widget(Label(
            text='FIRST BOOT', font_size=DS.FONT_SMALL, bold=True,
            color=DS.ACCENT, size_hint_x=0.5,
            halign='right', valign='middle', text_size=(dp(300), None),
        ))
        root.add_widget(status_bar)

        # ---- MAIN CONTENT ----
        content = BoxLayout(
            orientation='vertical',
            padding=[dp(50), dp(15), dp(50), dp(12)],
            spacing=dp(8),
        )

        # Title
        content.add_widget(Label(
            text='Cloud Pairing', font_size=DS.FONT_H1, bold=True,
            color=DS.TEXT_PRIMARY, size_hint_y=None, height=dp(38),
            halign='center', text_size=(dp(700), None),
        ))

        # Subtitle
        content.add_widget(Label(
            text='Enter the 6-digit code from the admin panel',
            font_size='14sp', color=DS.TEXT_MUTED,
            size_hint_y=None, height=dp(22),
            halign='center', text_size=(dp(700), None),
        ))

        content.add_widget(Widget(size_hint_y=None, height=dp(10)))

        # PAIRING CODE label
        content.add_widget(Label(
            text='PAIRING CODE', font_size=DS.FONT_TINY, bold=True,
            color=DS.TEXT_MUTED, size_hint_y=None, height=dp(16),
            halign='center', text_size=(dp(700), None),
        ))

        # Big pairing code input
        input_row = BoxLayout(size_hint_y=None, height=dp(68), padding=[dp(60), 0])
        self._code_input = TextInput(
            hint_text='_ _ _ _ _ _',
            font_size='36sp',
            multiline=False,
            size_hint_y=None, height=dp(68),
            background_color=DS.BG_INPUT,
            foreground_color=DS.PRIMARY,
            cursor_color=DS.PRIMARY,
            hint_text_color=(0.20, 0.22, 0.28, 1),
            padding=[dp(12), dp(12)],
            halign='center',
        )
        input_row.add_widget(self._code_input)
        content.add_widget(input_row)

        content.add_widget(Widget(size_hint_y=None, height=dp(6)))

        # Status message
        self._status_label = Label(
            text=self.status_text, font_size='14sp',
            color=self.status_color,
            size_hint_y=None, height=dp(24),
            halign='center', text_size=(dp(600), None), markup=True,
        )
        content.add_widget(self._status_label)

        # Buttons row
        btn_row = BoxLayout(spacing=dp(12), size_hint_y=None, height=dp(DS.BTN_HEIGHT_LG))

        # CONNECT button
        self._connect_btn = Button(
            text='CONNECT', font_size=DS.FONT_H2, bold=True,
            background_normal='', background_color=(0, 0, 0, 0),
            color=(0.02, 0.05, 0.08, 1),
            on_release=lambda x: self.do_pairing(),
        )
        _card_bg(self._connect_btn, DS.PRIMARY, radius=DS.RADIUS)
        btn_row.add_widget(self._connect_btn)

        # OFFLINE MODE button
        offline_btn = Button(
            text='OFFLINE MODE', font_size=DS.FONT_BODY, bold=True,
            background_normal='', background_color=(0, 0, 0, 0),
            color=DS.TEXT_SECONDARY, size_hint_x=0.4,
            on_release=lambda x: self.skip_pairing(),
        )
        _card_bg(offline_btn, DS.BG_CARD_HOVER, radius=DS.RADIUS)
        btn_row.add_widget(offline_btn)

        content.add_widget(btn_row)

        # Virtual keyboard container
        self._kb_container = BoxLayout(size_hint_y=None, height=0)
        content.add_widget(self._kb_container)

        # Spacer
        content.add_widget(Widget(size_hint_y=1))

        # Device info footer
        content.add_widget(Label(
            text=self.device_info_text, font_size='10sp',
            color=(0.25, 0.28, 0.34, 1),
            size_hint_y=None, height=dp(16),
            halign='center', text_size=(dp(700), None),
        ))

        root.add_widget(content)
        self.add_widget(root)

        # Setup virtual keyboard
        self._setup_virtual_keyboard()

    # ================================================================
    # PAIRING LOGIC
    # ================================================================

    def do_pairing(self):
        """Execute the pairing process."""
        pairing_code = self._code_input.text.strip().upper()

        if not pairing_code or len(pairing_code) != 6:
            self._set_status('Enter the 6-digit code', error=True)
            return

        cloud_url = settings.CLOUD_URL
        if not cloud_url:
            self._set_status('Cloud URL not configured!', error=True)
            return

        # Disable button and show connecting
        self._connect_btn.text = 'CONNECTING...'
        self._connect_btn.disabled = True
        self._set_status('Connecting to cloud...', info=True)

        # Execute in next frame to let UI update
        Clock.schedule_once(
            lambda dt: self._execute_pairing(cloud_url, pairing_code), 0.1
        )

    def _execute_pairing(self, cloud_url, pairing_code):
        """Actually execute the pairing (called after UI update)."""
        app = App.get_running_app()

        try:
            success, data = app.cloud.pair_with_code(cloud_url, pairing_code)

            if success:
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
                self._reset_connect_button()

        except Exception as e:
            logger.exception("Pairing failed")
            self._set_status(f'Error: {str(e)}', error=True)
            self._reset_connect_button()

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

    # ================================================================
    # STATUS HELPERS
    # ================================================================

    def _set_status(self, text, error=False, success=False, info=False):
        """Update the status label with colored text."""
        self.status_text = text
        if error:
            self.status_color = list(DS.DANGER)
        elif success:
            self.status_color = list(DS.SUCCESS)
        elif info:
            self.status_color = list(DS.INFO)
        else:
            self.status_color = list(DS.TEXT_MUTED)

        if hasattr(self, '_status_label') and self._status_label:
            self._status_label.text = text
            self._status_label.color = self.status_color

    def _reset_connect_button(self):
        """Re-enable the connect button after failure."""
        if self._connect_btn:
            self._connect_btn.text = 'CONNECT'
            self._connect_btn.disabled = False

    def _get_version(self):
        """Read version string from config/VERSION file."""
        try:
            import os
            version_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'config', 'VERSION'
            )
            with open(version_path, 'r') as f:
                return f.read().strip()
        except Exception:
            return '?.?.?'

    # ================================================================
    # VIRTUAL KEYBOARD
    # ================================================================

    def _setup_virtual_keyboard(self):
        """Create and bind the numeric virtual keyboard."""
        try:
            from ui.widgets.virtual_keyboard import VirtualKeyboard
        except ImportError:
            logger.debug("VirtualKeyboard not available, skipping")
            return

        if self._keyboard is None:
            self._keyboard = VirtualKeyboard(mode='numeric')
            self._keyboard.bind_to(self._code_input)

        self._code_input.bind(focus=self._on_input_focus)

    def _on_input_focus(self, instance, focused):
        """Show keyboard when input gets focus, hide when unfocused."""
        if focused:
            self._show_keyboard()
        else:
            self._hide_keyboard()

    def _show_keyboard(self):
        """Show the virtual keyboard below the input."""
        if not hasattr(self, '_kb_container') or not self._kb_container:
            return
        if self._keyboard and self._keyboard.parent is None:
            self._kb_container.add_widget(self._keyboard)
        self._kb_container.height = (
            self._keyboard.NUMERIC_HEIGHT if self._keyboard else dp(220)
        )

    def _hide_keyboard(self):
        """Hide the virtual keyboard."""
        if not hasattr(self, '_kb_container') or not self._kb_container:
            return
        if self._keyboard and self._keyboard.parent == self._kb_container:
            self._kb_container.remove_widget(self._keyboard)
        self._kb_container.height = 0
