"""
Settings Screen - Device Configuration & Cloud Status (v3.0 Redesign)

Card-based, scrollable layout built entirely in Python.
Shows device info, cloud connection, display mode, and system actions.
"""

import time

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.metrics import dp, sp

from ui.app import DS
from sync.update_manager import read_version


# ---------------------------------------------------------------------------
#  Drawing helpers
# ---------------------------------------------------------------------------

def _card_bg(widget, color=DS.BG_CARD, radius=DS.RADIUS):
    """Attach a rounded-rect background that tracks pos/size."""
    with widget.canvas.before:
        c = Color(*color)
        rr = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[radius])
    widget.bind(
        pos=lambda w, p: setattr(rr, 'pos', p),
        size=lambda w, s: setattr(rr, 'size', s),
    )
    return rr


def _make_label(text='', font_size=DS.FONT_BODY, color=DS.TEXT_PRIMARY,
                bold=False, halign='left', valign='middle',
                size_hint_y=None, height=None, markup=False):
    """Factory for a text label with sensible defaults."""
    kwargs = dict(
        text=text,
        font_size=font_size,
        bold=bold,
        color=color,
        halign=halign,
        valign=valign,
        markup=markup,
    )
    if height is not None:
        kwargs['size_hint_y'] = None
        kwargs['height'] = dp(height)
    elif size_hint_y is not None:
        kwargs['size_hint_y'] = size_hint_y
    lbl = Label(**kwargs)
    lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
    return lbl


def _make_button(text, font_size=DS.FONT_BODY, bold=True,
                 text_color=DS.TEXT_PRIMARY, bg_color=DS.BG_CARD,
                 height=DS.BTN_HEIGHT_MD, radius=DS.RADIUS,
                 size_hint_x=1, on_release=None):
    """Factory for a flat rounded button."""
    btn = Button(
        text=text,
        font_size=font_size,
        bold=bold,
        color=text_color,
        background_normal='',
        background_color=(0, 0, 0, 0),
        size_hint=(size_hint_x, None),
        height=dp(height),
    )
    _card_bg(btn, color=bg_color, radius=radius)
    if on_release:
        btn.bind(on_release=on_release)
    return btn


def _section_header(text):
    """Small blue section label above a card."""
    lbl = Label(
        text=text,
        font_size=DS.FONT_SMALL,
        bold=True,
        color=DS.SECONDARY,
        size_hint_y=None,
        height=dp(24),
        halign='left',
        valign='bottom',
        padding=[dp(4), 0],
    )
    lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
    return lbl


# ---------------------------------------------------------------------------
#  SettingsScreen
# ---------------------------------------------------------------------------

class SettingsScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._refresh_event = None
        self._refs = {}          # label references for live updates
        self._display_btns = {}  # display mode toggle buttons
        self._build_ui()

    # ── UI Construction ─────────────────────────────────────

    def _build_ui(self):
        root = BoxLayout(orientation='vertical')

        # Dark background
        with root.canvas.before:
            Color(*DS.BG_DARK)
            bg_rect = Rectangle(pos=root.pos, size=root.size)
        root.bind(
            pos=lambda w, p: setattr(bg_rect, 'pos', p),
            size=lambda w, s: setattr(bg_rect, 'size', s),
        )

        # ---- STATUS BAR ----
        status_bar = BoxLayout(
            size_hint_y=None, height=dp(DS.STATUS_BAR_H),
            padding=[dp(12), dp(4)], spacing=dp(8),
        )
        with status_bar.canvas.before:
            Color(*DS.BG_STATUS_BAR)
            sb_rect = Rectangle(pos=status_bar.pos, size=status_bar.size)
            Color(*DS.PRIMARY[:3], 0.25)
            accent_rect = Rectangle(pos=status_bar.pos, size=(status_bar.width, 1))
        status_bar.bind(
            pos=lambda w, p: (setattr(sb_rect, 'pos', p), setattr(accent_rect, 'pos', p)),
            size=lambda w, s: (setattr(sb_rect, 'size', s), setattr(accent_rect, 'size', (s[0], 1))),
        )

        back_btn = Button(
            text='<', font_size='22sp', bold=True,
            size_hint=(None, None), size=(dp(50), dp(36)),
            background_normal='', background_color=DS.BG_CARD_HOVER,
            color=DS.TEXT_SECONDARY,
        )
        back_btn.bind(on_release=lambda x: App.get_running_app().go_back())
        status_bar.add_widget(back_btn)

        title_lbl = _make_label(
            'SETTINGS', font_size='18sp', bold=True,
            color=DS.TEXT_PRIMARY, halign='center',
        )
        title_lbl.size_hint_x = 0.5
        status_bar.add_widget(title_lbl)

        status_bar.add_widget(Widget(size_hint_x=0.3))
        root.add_widget(status_bar)

        # ---- SCROLL CONTENT ----
        scroll = ScrollView(do_scroll_x=False)
        content = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            padding=[dp(DS.PAD_SCREEN), dp(8), dp(DS.PAD_SCREEN), dp(8)],
            spacing=dp(DS.SPACING),
        )
        content.bind(minimum_height=content.setter('height'))

        # ── DEVICE INFO CARD ──
        content.add_widget(_section_header('DEVICE INFO'))
        device_card = self._build_device_card()
        content.add_widget(device_card)

        # ── CLOUD CONNECTION CARD ──
        content.add_widget(_section_header('CLOUD CONNECTION'))
        cloud_card = self._build_cloud_card()
        content.add_widget(cloud_card)

        # Cloud action buttons
        cloud_btns = self._build_cloud_buttons()
        content.add_widget(cloud_btns)

        # ── DISPLAY MODE CARD ──
        content.add_widget(_section_header('DISPLAY'))
        display_card = self._build_display_card()
        content.add_widget(display_card)

        # ── SYSTEM CARD ──
        content.add_widget(_section_header('SYSTEM'))
        system_card = self._build_system_card()
        content.add_widget(system_card)

        # Bottom spacer
        content.add_widget(Widget(size_hint_y=None, height=dp(20)))

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    # ── Card builders ──────────────────────────────────────

    def _build_device_card(self):
        card = BoxLayout(
            orientation='vertical',
            size_hint_y=None, height=dp(120),
            padding=[dp(DS.PAD_CARD), dp(8)],
            spacing=dp(3),
        )
        _card_bg(card)

        # Device ID
        lbl_id = _make_label('Device ID: ---', DS.FONT_SMALL, DS.TEXT_SECONDARY,
                             size_hint_y=None, height=20)
        self._refs['device_id'] = lbl_id
        card.add_widget(lbl_id)

        # Mode + Version row
        row_mv = BoxLayout(size_hint_y=None, height=dp(20), spacing=dp(12))
        lbl_mode = _make_label('Mode: ---', DS.FONT_SMALL, DS.TEXT_SECONDARY, markup=True)
        lbl_version = _make_label('Version: ---', DS.FONT_SMALL, DS.TEXT_MUTED, halign='right')
        self._refs['mode'] = lbl_mode
        self._refs['version'] = lbl_version
        row_mv.add_widget(lbl_mode)
        row_mv.add_widget(lbl_version)
        card.add_widget(row_mv)

        # Drivers row
        lbl_drivers = _make_label('Drivers: ---', DS.FONT_SMALL, DS.TEXT_MUTED,
                                  markup=True, size_hint_y=None, height=20)
        self._refs['drivers'] = lbl_drivers
        card.add_widget(lbl_drivers)

        # Events row
        lbl_events = _make_label('Events: ---', DS.FONT_SMALL, DS.TEXT_MUTED,
                                 size_hint_y=None, height=20)
        self._refs['events'] = lbl_events
        card.add_widget(lbl_events)

        return card

    def _build_cloud_card(self):
        card = BoxLayout(
            orientation='vertical',
            size_hint_y=None, height=dp(100),
            padding=[dp(DS.PAD_CARD), dp(8)],
            spacing=dp(3),
        )
        _card_bg(card)

        lbl_status = _make_label('Status: NOT PAIRED', DS.FONT_BODY, DS.DANGER,
                                 bold=True, size_hint_y=None, height=22, markup=True)
        self._refs['cloud_status'] = lbl_status
        card.add_widget(lbl_status)

        lbl_vessel = _make_label('Vessel: ---', DS.FONT_SMALL, DS.TEXT_SECONDARY,
                                 size_hint_y=None, height=20)
        self._refs['vessel'] = lbl_vessel
        card.add_widget(lbl_vessel)

        lbl_sync = _make_label('Last sync: ---', DS.FONT_SMALL, DS.TEXT_MUTED,
                               size_hint_y=None, height=18)
        self._refs['sync'] = lbl_sync
        card.add_widget(lbl_sync)

        return card

    def _build_cloud_buttons(self):
        row = BoxLayout(
            size_hint_y=None, height=dp(DS.BTN_HEIGHT_MD),
            spacing=dp(DS.SPACING),
        )

        pair_btn = _make_button(
            'PAIR / RE-PAIR', DS.FONT_BODY, True,
            text_color=(0.02, 0.05, 0.08, 1), bg_color=DS.PRIMARY,
            on_release=lambda x: self.open_pair(),
        )
        row.add_widget(pair_btn)

        sync_btn = _make_button(
            'SYNC NOW', DS.FONT_BODY, True,
            text_color=DS.TEXT_PRIMARY, bg_color=DS.BG_CARD_HOVER,
            on_release=lambda x: self.force_sync(),
        )
        self._refs['sync_btn'] = sync_btn
        row.add_widget(sync_btn)

        unpair_btn = _make_button(
            'UNPAIR', DS.FONT_SMALL, True,
            text_color=DS.DANGER, bg_color=(0.16, 0.08, 0.08, 1),
            size_hint_x=0.35,
            on_release=lambda x: self.do_unpair(),
        )
        self._refs['unpair_btn'] = unpair_btn
        row.add_widget(unpair_btn)

        return row

    def _build_display_card(self):
        card = BoxLayout(
            size_hint_y=None, height=dp(DS.BTN_HEIGHT_MD),
            spacing=dp(DS.SPACING),
        )

        btn_touch = _make_button(
            'Touch 4.3"', DS.FONT_SMALL, True,
            text_color=DS.TEXT_PRIMARY,
            bg_color=(0.06, 0.12, 0.12, 1),
            on_release=lambda x: self.switch_display('touch43'),
        )
        self._display_btns['touch43'] = btn_touch
        card.add_widget(btn_touch)

        btn_desktop = _make_button(
            'Desktop', DS.FONT_SMALL, True,
            text_color=DS.TEXT_SECONDARY,
            bg_color=DS.BG_CARD,
            on_release=lambda x: self.switch_display('desktop'),
        )
        self._display_btns['desktop'] = btn_desktop
        card.add_widget(btn_desktop)

        return card

    def _build_system_card(self):
        card = BoxLayout(
            orientation='vertical',
            size_hint_y=None, height=dp(DS.BTN_HEIGHT_MD * 4 + DS.SPACING * 3),
            spacing=dp(DS.SPACING),
        )

        sensor_btn = _make_button(
            'SENSOR TESTING', DS.FONT_BODY, True,
            text_color=DS.SECONDARY, bg_color=(0.06, 0.08, 0.14, 1),
            on_release=lambda x: App.get_running_app().go_screen('sensor_test'),
        )
        card.add_widget(sensor_btn)

        health_btn = _make_button(
            'SYSTEM HEALTH', DS.FONT_BODY, True,
            text_color=DS.PRIMARY, bg_color=(0.06, 0.12, 0.12, 1),
            on_release=lambda x: App.get_running_app().go_screen('system_health'),
        )
        card.add_widget(health_btn)

        admin_btn = _make_button(
            'ADMIN ACCESS', DS.FONT_BODY, True,
            text_color=DS.ACCENT, bg_color=(0.16, 0.12, 0.06, 1),
            on_release=lambda x: self.open_admin(),
        )
        card.add_widget(admin_btn)

        demo_btn = _make_button(
            'DEMO', DS.FONT_BODY, True,
            text_color=DS.WARNING, bg_color=(0.14, 0.12, 0.06, 1),
            on_release=lambda x: App.get_running_app().go_screen('demo'),
        )
        card.add_widget(demo_btn)

        return card

    # ── Lifecycle ──────────────────────────────────────────

    def on_enter(self):
        """Refresh all info and start periodic update."""
        self._refresh_info()
        self._refresh_event = Clock.schedule_interval(
            lambda dt: self._refresh_info(), 5.0
        )

    def on_leave(self):
        """Cancel periodic refresh."""
        if self._refresh_event:
            self._refresh_event.cancel()
            self._refresh_event = None

    # ── Data refresh ───────────────────────────────────────

    def _refresh_info(self):
        """Update all labels from current app state."""
        app = App.get_running_app()

        # Device ID
        self._refs['device_id'].text = f'Device ID: {app.device_id}'

        # Mode with color coding
        mode_upper = app.mode.upper()
        mode_hex = {
            'hybrid': DS.hex_markup(DS.WARNING),
            'live':   DS.hex_markup(DS.SUCCESS),
            'test':   DS.hex_markup(DS.TEXT_MUTED),
        }.get(app.mode, DS.hex_markup(DS.TEXT_SECONDARY))
        self._refs['mode'].text = f'Mode: [color={mode_hex}]{mode_upper}[/color]'

        # Version
        self._refs['version'].text = f'v{read_version()}'

        # Driver status dots
        if hasattr(app, 'driver_status'):
            parts = []
            for name, status in app.driver_status.items():
                label = name.upper()
                if status == 'real':
                    dot = '[color=33d17a]\u25cf[/color]'
                else:
                    dot = '[color=616878]\u25cb[/color]'
                parts.append(f'{label}{dot}')
            self._refs['drivers'].text = f'Drivers: {"  ".join(parts)}'
        else:
            self._refs['drivers'].text = 'Drivers: all fake'

        # Events count
        total = len(app.event_log)
        self._refs['events'].text = f'Events in memory: {total}'

        # Cloud status
        if app.cloud.is_paired:
            info = app.cloud.get_pairing_info() or {}
            self._refs['cloud_status'].text = f'Status: PAIRED \u25cf'
            self._refs['cloud_status'].color = list(DS.SUCCESS)
            self._refs['vessel'].text = f"Vessel: {info.get('vessel_name', '---')}"

            # Sync info
            status = app.sync_engine.get_status()
            synced = status.get('events_synced', 0)
            unsynced = status.get('events_unsynced', 0)
            last_ts = status.get('last_sync_ts', 0)
            if last_ts:
                ago = int(time.time() - last_ts)
                if ago < 60:
                    ago_str = f'{ago}s ago'
                elif ago < 3600:
                    ago_str = f'{ago // 60} min ago'
                else:
                    ago_str = f'{ago // 3600}h ago'
            else:
                ago_str = 'never'
            self._refs['sync'].text = f'Last sync: {ago_str} | {synced} synced, {unsynced} pending'

            self._refs['unpair_btn'].disabled = False
            self._refs['sync_btn'].disabled = False
        else:
            self._refs['cloud_status'].text = 'Status: NOT PAIRED'
            self._refs['cloud_status'].color = list(DS.DANGER)
            self._refs['vessel'].text = 'Vessel: ---'
            self._refs['sync'].text = 'Sync: Disabled (pair first)'
            self._refs['unpair_btn'].disabled = True
            self._refs['sync_btn'].disabled = True

        # Display mode indicator
        from ui.display_mode import DisplayMode
        dm = DisplayMode.instance()
        for mode_key, btn in self._display_btns.items():
            if mode_key == dm.mode:
                btn.color = DS.TEXT_PRIMARY
            else:
                btn.color = DS.TEXT_MUTED

    # ── Actions ────────────────────────────────────────────

    def open_pair(self):
        """Navigate to the pairing screen."""
        App.get_running_app().go_screen('pairing')

    def force_sync(self):
        """Trigger an immediate cloud sync."""
        app = App.get_running_app()
        if app.cloud.is_paired and app.sync_engine.is_running:
            app.sync_engine.force_sync()
            self._refs['sync'].text = 'Sync: Manual sync triggered...'

    def do_unpair(self):
        """Unpair the device from cloud."""
        app = App.get_running_app()
        app.sync_engine.stop()
        app.cloud.unpair()
        self._refresh_info()

    def switch_display(self, mode_name):
        """Switch display mode with a confirmation popup (15s auto-revert)."""
        from ui.display_mode import DisplayMode

        dm = DisplayMode.instance()
        if dm.mode == mode_name:
            return  # Already in this mode

        dm.switch_mode(mode_name)

        # ── Confirmation popup ──
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))

        with content.canvas.before:
            Color(*DS.BG_CARD)
            popup_bg = RoundedRectangle(pos=content.pos, size=content.size,
                                        radius=[DS.RADIUS])
        content.bind(
            pos=lambda w, p: setattr(popup_bg, 'pos', p),
            size=lambda w, s: setattr(popup_bg, 'size', s),
        )

        msg = _make_label(
            f'Display switched to {mode_name.upper()}.\n\n'
            f'Confirm within 15 seconds\nor it will revert automatically.',
            font_size=DS.FONT_BODY, color=DS.TEXT_PRIMARY,
            halign='center', valign='middle',
        )
        content.add_widget(msg)

        countdown_lbl = _make_label(
            '15', font_size=DS.FONT_H1, color=DS.WARNING,
            halign='center', bold=True,
        )
        content.add_widget(countdown_lbl)

        btn_row = BoxLayout(size_hint_y=None, height=dp(DS.BTN_HEIGHT_MD), spacing=dp(10))

        confirm_btn = _make_button(
            'CONFIRM', DS.FONT_BODY, True,
            text_color=(0.02, 0.05, 0.08, 1), bg_color=DS.PRIMARY,
        )
        cancel_btn = _make_button(
            'CANCEL', DS.FONT_BODY, True,
            text_color=(1, 1, 1, 1), bg_color=DS.DANGER,
        )
        btn_row.add_widget(confirm_btn)
        btn_row.add_widget(cancel_btn)
        content.add_widget(btn_row)

        popup = Popup(
            title='Display Mode',
            content=content,
            size_hint=(0.85, 0.45),
            auto_dismiss=False,
            separator_color=DS.PRIMARY,
        )

        # Countdown timer
        self._countdown = 15
        self._countdown_lbl = countdown_lbl

        def _tick(dt):
            self._countdown -= 1
            if self._countdown <= 0:
                _on_cancel(None)
            else:
                countdown_lbl.text = str(self._countdown)

        countdown_event = Clock.schedule_interval(_tick, 1.0)

        def _on_confirm(_):
            countdown_event.cancel()
            dm.confirm()
            popup.dismiss()
            self._refresh_info()

        def _on_cancel(_):
            countdown_event.cancel()
            dm.cancel()
            popup.dismiss()
            self._refresh_info()

        confirm_btn.bind(on_release=_on_confirm)
        cancel_btn.bind(on_release=_on_cancel)
        popup.open()

    def open_admin(self):
        """Show password dialog then navigate to admin screen."""
        from ui.screens.admin import show_admin_password_dialog
        app = App.get_running_app()
        show_admin_password_dialog(lambda: app.go_screen('admin'))
