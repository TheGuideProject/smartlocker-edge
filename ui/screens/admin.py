"""
Admin Screen - Password-protected device configuration (2026 Redesign)

Provides:
- Driver mode toggles (RFID, Weight, LED, Buzzer: fake/real)
- Hardware configuration (I2C, serial, GPIO settings)
- Polling & threshold tuning
- Security (change admin password, factory reset)

Design:
- Card-based scrollable layout with section headers
- Large touch targets for gloved hands
- Color-coded toggle buttons (green=REAL, gray=FAKE)
- Password dialog on entry via module-level function
"""

import hashlib
import time
import logging

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.lang import Builder
from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.properties import StringProperty, BooleanProperty, DictProperty

from ui.app import DS
from config import settings

logger = logging.getLogger("smartlocker.admin")

# Default admin password (SHA-256 hashed)
DEFAULT_ADMIN_PASSWORD = "Smartlocker2026"
_DEFAULT_HASH = hashlib.sha256(DEFAULT_ADMIN_PASSWORD.encode()).hexdigest()


# ==============================================================
# MODULE-LEVEL PASSWORD DIALOG (importable by other screens)
# ==============================================================

def _hash_password(raw: str) -> str:
    """SHA-256 hash of a password string."""
    return hashlib.sha256(raw.encode()).hexdigest()


def _get_stored_hash() -> str:
    """Retrieve the current admin password hash from DB or fallback to default."""
    try:
        app = App.get_running_app()
        if app and hasattr(app, 'db') and app.db:
            stored = app.db.get_config("admin_password_hash")
            if stored:
                return stored
    except Exception:
        pass
    return _DEFAULT_HASH


def show_admin_password_dialog(on_success_callback):
    """
    Show a modal password dialog. Calls on_success_callback() if the
    entered password matches the stored admin hash.

    This is a MODULE-LEVEL function so any screen can import and use it:
        from ui.screens.admin import show_admin_password_dialog
        show_admin_password_dialog(lambda: do_protected_thing())
    """
    content = BoxLayout(orientation='vertical', spacing=dp(12), padding=dp(16))

    # Dark card background for the popup content
    with content.canvas.before:
        Color(*DS.BG_CARD)
        content._bg_rect = RoundedRectangle(pos=content.pos, size=content.size, radius=[dp(DS.RADIUS)])
    content.bind(pos=lambda w, v: setattr(w._bg_rect, 'pos', v),
                 size=lambda w, v: setattr(w._bg_rect, 'size', v))

    title_lbl = Label(
        text='ADMIN ACCESS',
        font_size=DS.FONT_H2,
        bold=True,
        color=DS.TEXT_PRIMARY,
        size_hint_y=None,
        height=dp(36),
    )

    hint_lbl = Label(
        text='Enter admin password to continue',
        font_size=DS.FONT_SMALL,
        color=DS.TEXT_SECONDARY,
        size_hint_y=None,
        height=dp(24),
    )

    pwd_input = TextInput(
        hint_text='Password',
        password=True,
        multiline=False,
        font_size=DS.FONT_BODY,
        size_hint_y=None,
        height=dp(DS.BTN_HEIGHT_MD),
        background_color=DS.BG_INPUT,
        foreground_color=DS.TEXT_PRIMARY,
        hint_text_color=DS.TEXT_MUTED,
        cursor_color=DS.PRIMARY,
        padding=[dp(12), dp(12)],
    )

    error_lbl = Label(
        text='',
        font_size=DS.FONT_SMALL,
        color=DS.DANGER,
        size_hint_y=None,
        height=dp(22),
    )

    btn_row = BoxLayout(orientation='horizontal', spacing=dp(8), size_hint_y=None, height=dp(DS.BTN_HEIGHT_LG))

    cancel_btn = Button(
        text='CANCEL',
        font_size=DS.FONT_BODY,
        bold=True,
        size_hint_x=0.5,
        background_color=DS.BG_CARD_HOVER,
        color=DS.TEXT_SECONDARY,
        background_normal='',
    )

    confirm_btn = Button(
        text='UNLOCK',
        font_size=DS.FONT_BODY,
        bold=True,
        size_hint_x=0.5,
        background_color=DS.PRIMARY,
        color=DS.BG_DARK,
        background_normal='',
    )

    btn_row.add_widget(cancel_btn)
    btn_row.add_widget(confirm_btn)

    content.add_widget(title_lbl)
    content.add_widget(hint_lbl)
    content.add_widget(pwd_input)
    content.add_widget(error_lbl)
    content.add_widget(btn_row)

    popup = Popup(
        title='',
        separator_height=0,
        content=content,
        size_hint=(0.85, None),
        height=dp(300),
        auto_dismiss=False,
        background_color=(0, 0, 0, 0.85),
        background='',
    )

    def _on_cancel(_inst):
        popup.dismiss()

    def _on_confirm(_inst):
        entered = pwd_input.text.strip()
        if not entered:
            error_lbl.text = 'Password cannot be empty'
            return
        entered_hash = _hash_password(entered)
        stored_hash = _get_stored_hash()
        if entered_hash == stored_hash:
            popup.dismiss()
            if callable(on_success_callback):
                on_success_callback()
        else:
            error_lbl.text = 'Incorrect password'
            pwd_input.text = ''
            pwd_input.focus = True

    cancel_btn.bind(on_release=_on_cancel)
    confirm_btn.bind(on_release=_on_confirm)
    pwd_input.bind(on_text_validate=_on_confirm)

    popup.open()
    # Focus the input after a short delay (Kivy needs a frame)
    Clock.schedule_once(lambda dt: setattr(pwd_input, 'focus', True), 0.2)


# ==============================================================
# KV LAYOUT
# ==============================================================
Builder.load_string('''
<AdminScreen>:
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
                on_release: root.go_back()

            Label:
                text: 'ADMIN PANEL'
                font_size: '18sp'
                bold: True
                color: 0.96, 0.97, 0.98, 1
                size_hint_x: 0.5
                halign: 'center'
                text_size: self.size
                valign: 'middle'

            Widget:
                size_hint_x: 0.2

        # ---- SCROLLABLE CONTENT ----
        ScrollView:
            do_scroll_x: False
            bar_width: '4dp'
            bar_color: 0.00, 0.82, 0.73, 0.5
            bar_inactive_color: 0.18, 0.20, 0.26, 0.3

            BoxLayout:
                id: content_box
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: [dp(12), dp(8)]
                spacing: dp(8)
''')


# ==============================================================
# HELPER WIDGETS
# ==============================================================

class _SectionHeader(BoxLayout):
    """Section title bar with optional icon."""

    def __init__(self, title, icon='', **kwargs):
        super().__init__(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(36),
            padding=[dp(8), dp(4)],
            **kwargs,
        )
        txt = f'{icon}  {title}' if icon else title
        self.add_widget(Label(
            text=txt,
            font_size=DS.FONT_H3,
            bold=True,
            color=DS.PRIMARY,
            halign='left',
            valign='middle',
            text_size=(None, None),
        ))


class _DriverToggleRow(BoxLayout):
    """A row with sensor name, current mode, and toggle button."""

    def __init__(self, sensor_label, sensor_key, screen_ref, **kwargs):
        super().__init__(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(DS.BTN_HEIGHT_MD),
            spacing=dp(8),
            padding=[dp(8), dp(4)],
            **kwargs,
        )
        self._sensor_key = sensor_key
        self._screen_ref = screen_ref

        # Card background
        with self.canvas.before:
            Color(*DS.BG_CARD)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(DS.RADIUS)])
        self.bind(pos=lambda w, v: setattr(w._bg, 'pos', v),
                  size=lambda w, v: setattr(w._bg, 'size', v))

        self._name_lbl = Label(
            text=sensor_label,
            font_size=DS.FONT_BODY,
            bold=True,
            color=DS.TEXT_PRIMARY,
            size_hint_x=0.4,
            halign='left',
            text_size=(None, None),
        )

        self._status_lbl = Label(
            text='FAKE',
            font_size=DS.FONT_SMALL,
            color=DS.TEXT_MUTED,
            size_hint_x=0.25,
        )

        self._toggle_btn = Button(
            text='SWITCH',
            font_size=DS.FONT_SMALL,
            bold=True,
            size_hint_x=0.35,
            background_normal='',
            background_color=DS.PRIMARY,
            color=DS.BG_DARK,
        )
        self._toggle_btn.bind(on_release=self._on_toggle)

        self.add_widget(self._name_lbl)
        self.add_widget(self._status_lbl)
        self.add_widget(self._toggle_btn)

    def refresh(self):
        """Update visual state from current config."""
        mode = self._screen_ref.driver_modes.get(self._sensor_key, 'fake')
        is_real = mode == 'real'
        self._status_lbl.text = 'REAL' if is_real else 'FAKE'
        self._status_lbl.color = DS.SUCCESS if is_real else DS.TEXT_MUTED
        self._toggle_btn.text = 'SET FAKE' if is_real else 'SET REAL'
        self._toggle_btn.background_color = DS.ACCENT if is_real else DS.PRIMARY

    def _on_toggle(self, _inst):
        self._screen_ref.toggle_driver(self._sensor_key)


class _ConfigValueRow(BoxLayout):
    """A config parameter row with label, current value, and edit field."""

    def __init__(self, label_text, config_key, current_val, screen_ref, suffix='', **kwargs):
        super().__init__(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(DS.BTN_HEIGHT_SM),
            spacing=dp(6),
            padding=[dp(8), dp(2)],
            **kwargs,
        )
        self._config_key = config_key
        self._screen_ref = screen_ref
        self._suffix = suffix

        with self.canvas.before:
            Color(*DS.BG_CARD)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(8)])
        self.bind(pos=lambda w, v: setattr(w._bg, 'pos', v),
                  size=lambda w, v: setattr(w._bg, 'size', v))

        self.add_widget(Label(
            text=label_text,
            font_size=DS.FONT_SMALL,
            color=DS.TEXT_SECONDARY,
            size_hint_x=0.45,
            halign='left',
            text_size=(None, None),
        ))

        self._input = TextInput(
            text=str(current_val),
            multiline=False,
            font_size=DS.FONT_SMALL,
            size_hint_x=0.3,
            background_color=DS.BG_INPUT,
            foreground_color=DS.TEXT_PRIMARY,
            hint_text_color=DS.TEXT_MUTED,
            cursor_color=DS.PRIMARY,
            padding=[dp(6), dp(6)],
        )

        save_btn = Button(
            text='SAVE',
            font_size=DS.FONT_TINY,
            bold=True,
            size_hint_x=0.25,
            background_normal='',
            background_color=DS.PRIMARY_DIM,
            color=DS.TEXT_PRIMARY,
        )
        save_btn.bind(on_release=self._on_save)

        self.add_widget(self._input)
        self.add_widget(save_btn)

    def _on_save(self, _inst):
        val = self._input.text.strip()
        if val:
            self._screen_ref.save_config(self._config_key, val)


# ==============================================================
# ADMIN SCREEN
# ==============================================================

class AdminScreen(Screen):
    """Password-protected admin configuration screen."""

    authenticated = BooleanProperty(False)
    driver_modes = DictProperty({
        'rfid': 'fake',
        'weight': 'fake',
        'led': 'fake',
        'buzzer': 'fake',
    })

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._driver_rows = {}
        self._built = False

    # ----------------------------------------------------------
    # Lifecycle
    # ----------------------------------------------------------

    def on_enter(self):
        """Show password dialog, then build content on success."""
        self._load_driver_modes()
        if not self.authenticated:
            show_admin_password_dialog(self._on_auth_success)
        else:
            self._refresh_all()

    def on_leave(self):
        """Reset auth so re-entry requires password."""
        self.authenticated = False

    def go_back(self):
        app = App.get_running_app()
        if app:
            app.root.current = 'settings'

    # ----------------------------------------------------------
    # Auth
    # ----------------------------------------------------------

    def _on_auth_success(self):
        self.authenticated = True
        if not self._built:
            self._build_content()
        self._refresh_all()

    # ----------------------------------------------------------
    # Driver mode management
    # ----------------------------------------------------------

    def _load_driver_modes(self):
        """Read current driver modes from settings module."""
        self.driver_modes = {
            'rfid': getattr(settings, 'DRIVER_RFID', 'fake'),
            'weight': getattr(settings, 'DRIVER_WEIGHT', 'fake'),
            'led': getattr(settings, 'DRIVER_LED', 'fake'),
            'buzzer': getattr(settings, 'DRIVER_BUZZER', 'fake'),
        }

    def toggle_driver(self, sensor_key):
        """Switch a single driver between fake and real, persist to DB config."""
        current = self.driver_modes.get(sensor_key, 'fake')
        new_mode = 'real' if current == 'fake' else 'fake'
        self.driver_modes[sensor_key] = new_mode

        # Persist to settings module (runtime)
        attr_name = f'DRIVER_{sensor_key.upper()}'
        setattr(settings, attr_name, new_mode)

        # Persist to DB config (survives restart)
        app = App.get_running_app()
        if app and hasattr(app, 'db') and app.db:
            try:
                app.db.set_config(attr_name, new_mode)
            except Exception as e:
                logger.warning(f"Could not persist driver mode: {e}")

        # Update driver_status dict on app if available
        if app and hasattr(app, 'driver_status'):
            app.driver_status[sensor_key] = new_mode

        # Refresh UI
        if sensor_key in self._driver_rows:
            self._driver_rows[sensor_key].refresh()

        logger.info(f"Driver {sensor_key} toggled to {new_mode}")

    # ----------------------------------------------------------
    # Config save
    # ----------------------------------------------------------

    def save_config(self, key, value):
        """Save a config value to the database and settings module."""
        app = App.get_running_app()

        # Try to cast numeric values
        try:
            if '.' in value:
                cast_val = float(value)
            else:
                cast_val = int(value)
        except ValueError:
            cast_val = value

        # Update runtime settings
        if hasattr(settings, key):
            setattr(settings, key, cast_val)

        # Persist to DB
        if app and hasattr(app, 'db') and app.db:
            try:
                app.db.set_config(key, str(value))
            except Exception as e:
                logger.warning(f"Could not persist config {key}: {e}")

        logger.info(f"Config saved: {key} = {value}")

    # ----------------------------------------------------------
    # Change admin password
    # ----------------------------------------------------------

    def _change_password(self):
        """Show a popup to change the admin password."""
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(14))

        with content.canvas.before:
            Color(*DS.BG_CARD)
            content._bg = RoundedRectangle(pos=content.pos, size=content.size, radius=[dp(DS.RADIUS)])
        content.bind(pos=lambda w, v: setattr(w._bg, 'pos', v),
                     size=lambda w, v: setattr(w._bg, 'size', v))

        content.add_widget(Label(
            text='CHANGE ADMIN PASSWORD',
            font_size=DS.FONT_H3, bold=True, color=DS.TEXT_PRIMARY,
            size_hint_y=None, height=dp(30),
        ))

        new_pwd = TextInput(
            hint_text='New password', password=True, multiline=False,
            font_size=DS.FONT_BODY, size_hint_y=None, height=dp(DS.BTN_HEIGHT_MD),
            background_color=DS.BG_INPUT, foreground_color=DS.TEXT_PRIMARY,
            hint_text_color=DS.TEXT_MUTED, cursor_color=DS.PRIMARY,
            padding=[dp(10), dp(10)],
        )
        confirm_pwd = TextInput(
            hint_text='Confirm password', password=True, multiline=False,
            font_size=DS.FONT_BODY, size_hint_y=None, height=dp(DS.BTN_HEIGHT_MD),
            background_color=DS.BG_INPUT, foreground_color=DS.TEXT_PRIMARY,
            hint_text_color=DS.TEXT_MUTED, cursor_color=DS.PRIMARY,
            padding=[dp(10), dp(10)],
        )
        error_lbl = Label(text='', font_size=DS.FONT_SMALL, color=DS.DANGER,
                          size_hint_y=None, height=dp(20))

        btn_row = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(DS.BTN_HEIGHT_LG))
        cancel_btn = Button(text='CANCEL', font_size=DS.FONT_BODY, bold=True,
                            size_hint_x=0.5, background_normal='',
                            background_color=DS.BG_CARD_HOVER, color=DS.TEXT_SECONDARY)
        save_btn = Button(text='SAVE', font_size=DS.FONT_BODY, bold=True,
                          size_hint_x=0.5, background_normal='',
                          background_color=DS.PRIMARY, color=DS.BG_DARK)
        btn_row.add_widget(cancel_btn)
        btn_row.add_widget(save_btn)

        content.add_widget(new_pwd)
        content.add_widget(confirm_pwd)
        content.add_widget(error_lbl)
        content.add_widget(btn_row)

        popup = Popup(
            title='', separator_height=0, content=content,
            size_hint=(0.85, None), height=dp(320),
            auto_dismiss=False, background_color=(0, 0, 0, 0.85), background='',
        )

        def _cancel(_inst):
            popup.dismiss()

        def _save(_inst):
            p1 = new_pwd.text.strip()
            p2 = confirm_pwd.text.strip()
            if len(p1) < 6:
                error_lbl.text = 'Password must be at least 6 characters'
                return
            if p1 != p2:
                error_lbl.text = 'Passwords do not match'
                return
            new_hash = _hash_password(p1)
            app = App.get_running_app()
            if app and hasattr(app, 'db') and app.db:
                try:
                    app.db.set_config("admin_password_hash", new_hash)
                except Exception as e:
                    error_lbl.text = f'Save failed: {e}'
                    return
            popup.dismiss()
            logger.info("Admin password changed successfully")

        cancel_btn.bind(on_release=_cancel)
        save_btn.bind(on_release=_save)

        popup.open()
        Clock.schedule_once(lambda dt: setattr(new_pwd, 'focus', True), 0.2)

    # ----------------------------------------------------------
    # Factory reset confirmation
    # ----------------------------------------------------------

    def _factory_reset(self):
        """Show confirmation dialog for factory reset."""
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(14))

        with content.canvas.before:
            Color(*DS.BG_CARD)
            content._bg = RoundedRectangle(pos=content.pos, size=content.size, radius=[dp(DS.RADIUS)])
        content.bind(pos=lambda w, v: setattr(w._bg, 'pos', v),
                     size=lambda w, v: setattr(w._bg, 'size', v))

        content.add_widget(Label(
            text='FACTORY RESET',
            font_size=DS.FONT_H2, bold=True, color=DS.DANGER,
            size_hint_y=None, height=dp(30),
        ))
        content.add_widget(Label(
            text='This will erase all local data, unpair the device, and reset all settings to defaults.',
            font_size=DS.FONT_SMALL, color=DS.TEXT_SECONDARY,
            size_hint_y=None, height=dp(48), text_size=(dp(280), None),
            halign='center',
        ))

        btn_row = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(DS.BTN_HEIGHT_LG))
        cancel_btn = Button(text='CANCEL', font_size=DS.FONT_BODY, bold=True,
                            size_hint_x=0.5, background_normal='',
                            background_color=DS.BG_CARD_HOVER, color=DS.TEXT_SECONDARY)
        reset_btn = Button(text='RESET', font_size=DS.FONT_BODY, bold=True,
                           size_hint_x=0.5, background_normal='',
                           background_color=DS.DANGER, color=DS.TEXT_PRIMARY)
        btn_row.add_widget(cancel_btn)
        btn_row.add_widget(reset_btn)

        content.add_widget(Widget(size_hint_y=None, height=dp(8)))
        content.add_widget(btn_row)

        popup = Popup(
            title='', separator_height=0, content=content,
            size_hint=(0.75, None), height=dp(240),
            auto_dismiss=False, background_color=(0, 0, 0, 0.85), background='',
        )

        def _cancel(_inst):
            popup.dismiss()

        def _reset(_inst):
            popup.dismiss()
            app = App.get_running_app()
            if app and hasattr(app, 'db') and app.db:
                try:
                    app.db.factory_reset()
                    logger.info("Factory reset executed")
                except Exception as e:
                    logger.error(f"Factory reset failed: {e}")

        cancel_btn.bind(on_release=_cancel)
        reset_btn.bind(on_release=_reset)

        popup.open()

    # ----------------------------------------------------------
    # Build UI content (once)
    # ----------------------------------------------------------

    def _build_content(self):
        """Construct all admin panel cards and widgets."""
        self._built = True
        box = self.ids.content_box

        # ===================== DRIVER MODES =====================
        box.add_widget(_SectionHeader('DRIVER MODES', icon=''))

        drivers = [
            ('RFID Reader', 'rfid'),
            ('Weight Sensor', 'weight'),
            ('LED Strip', 'led'),
            ('Buzzer', 'buzzer'),
        ]
        for label, key in drivers:
            row = _DriverToggleRow(label, key, self)
            self._driver_rows[key] = row
            box.add_widget(row)

        box.add_widget(Widget(size_hint_y=None, height=dp(6)))

        # ===================== HARDWARE CONFIG =====================
        box.add_widget(_SectionHeader('HARDWARE CONFIG', icon=''))

        hw_configs = [
            ('RFID Module', 'RFID_MODULE', getattr(settings, 'RFID_MODULE', 'rc522')),
            ('Device ID', 'DEVICE_ID', getattr(settings, 'DEVICE_ID', 'LOCKER-DEV-001')),
        ]
        for label, key, val in hw_configs:
            box.add_widget(_ConfigValueRow(label, key, val, self))

        box.add_widget(Widget(size_hint_y=None, height=dp(6)))

        # ===================== POLLING & THRESHOLDS =====================
        box.add_widget(_SectionHeader('THRESHOLDS & POLLING', icon=''))

        threshold_configs = [
            ('RFID Poll (ms)', 'RFID_POLL_INTERVAL_MS',
             getattr(settings, 'RFID_POLL_INTERVAL_MS', 500), 'ms'),
            ('Weight Poll (ms)', 'WEIGHT_POLL_INTERVAL_MS',
             getattr(settings, 'WEIGHT_POLL_INTERVAL_MS', 200), 'ms'),
            ('Stable Window (s)', 'WEIGHT_STABLE_WINDOW_S',
             getattr(settings, 'WEIGHT_STABLE_WINDOW_S', 3.0), 's'),
            ('Stable Tolerance (g)', 'WEIGHT_STABLE_TOLERANCE_G',
             getattr(settings, 'WEIGHT_STABLE_TOLERANCE_G', 10), 'g'),
            ('Removal Timeout (s)', 'CAN_REMOVAL_TIMEOUT_S',
             getattr(settings, 'CAN_REMOVAL_TIMEOUT_S', 14400), 's'),
        ]
        for label, key, val, suffix in threshold_configs:
            box.add_widget(_ConfigValueRow(label, key, val, self, suffix=suffix))

        box.add_widget(Widget(size_hint_y=None, height=dp(6)))

        # ===================== SECURITY =====================
        box.add_widget(_SectionHeader('SECURITY', icon=''))

        # Change password button
        pwd_btn = Button(
            text='CHANGE ADMIN PASSWORD',
            font_size=DS.FONT_BODY,
            bold=True,
            size_hint_y=None,
            height=dp(DS.BTN_HEIGHT_MD),
            background_normal='',
            background_color=DS.SECONDARY,
            color=DS.TEXT_PRIMARY,
        )
        pwd_btn.bind(on_release=lambda _: self._change_password())
        box.add_widget(pwd_btn)

        box.add_widget(Widget(size_hint_y=None, height=dp(6)))

        # Factory reset button
        reset_btn = Button(
            text='FACTORY RESET',
            font_size=DS.FONT_BODY,
            bold=True,
            size_hint_y=None,
            height=dp(DS.BTN_HEIGHT_MD),
            background_normal='',
            background_color=DS.DANGER_DIM,
            color=DS.TEXT_PRIMARY,
        )
        reset_btn.bind(on_release=lambda _: self._factory_reset())
        box.add_widget(reset_btn)

        # ===================== DEVICE INFO =====================
        box.add_widget(Widget(size_hint_y=None, height=dp(8)))
        box.add_widget(_SectionHeader('DEVICE INFO', icon=''))

        app = App.get_running_app()
        device_id = getattr(app, 'device_id', getattr(settings, 'DEVICE_ID', 'N/A'))

        info_texts = [
            f'Device ID:  {device_id}',
            f'Vessel:  {getattr(settings, "VESSEL_NAME", "N/A")}',
            f'Mode:  {getattr(settings, "MODE", "auto")}',
        ]
        for txt in info_texts:
            lbl = Label(
                text=txt,
                font_size=DS.FONT_SMALL,
                color=DS.TEXT_MUTED,
                size_hint_y=None,
                height=dp(22),
                halign='left',
                text_size=(None, None),
            )
            box.add_widget(lbl)

        # Bottom padding
        box.add_widget(Widget(size_hint_y=None, height=dp(20)))

    # ----------------------------------------------------------
    # Refresh
    # ----------------------------------------------------------

    def _refresh_all(self):
        """Refresh driver toggle states."""
        self._load_driver_modes()
        for key, row in self._driver_rows.items():
            row.refresh()
