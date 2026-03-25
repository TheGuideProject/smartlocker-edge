"""
Demo Screen - Test mode simulation controls (2026 Redesign)

Only visible/accessible in TEST mode.
Left panel: Slot controls (add/remove simulated RFID tags)
Right panel: Weight controls (set shelf weight, mixing scale weight)

Uses FakeRFIDDriver.add_tag()/remove_tag() and FakeWeightDriver.set_weight()
to manipulate simulated sensor state.

Amber-tinted buttons to visually distinguish from real actions.
"""

import logging

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.lang import Builder
from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.graphics import Color, RoundedRectangle, Rectangle

from ui.app import DS

logger = logging.getLogger("smartlocker.demo")

# Predefined test tags for quick simulation
_TEST_TAGS = [
    ("TAG-001", "Sigma Cover 280 Base"),
    ("TAG-002", "Sigma Cover 280 Hardener"),
    ("TAG-003", "Sigma Thinner 91-92"),
    ("TAG-004", "Sigmaglide 1290 Base"),
]

# Predefined slot reader IDs
_SLOT_READERS = [
    "shelf1_slot1",
    "shelf1_slot2",
    "shelf1_slot3",
    "shelf1_slot4",
]


# ==============================================================
# KV LAYOUT
# ==============================================================

Builder.load_string('''
<DemoScreen>:
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
                text: 'TEST MODE CONTROLS'
                font_size: '18sp'
                bold: True
                color: 0.98, 0.65, 0.25, 1
                size_hint_x: 0.5
                halign: 'center'
                text_size: self.size
                valign: 'middle'

            Label:
                id: mode_indicator
                text: 'SIMULATION'
                font_size: '13sp'
                bold: True
                color: 0.98, 0.76, 0.22, 1
                size_hint_x: 0.2
                halign: 'right'
                text_size: self.size
                valign: 'middle'

        # ---- TWO-PANEL CONTENT ----
        BoxLayout:
            orientation: 'horizontal'
            padding: [dp(8), dp(6)]
            spacing: dp(8)

            # LEFT: RFID Slot Controls
            BoxLayout:
                orientation: 'vertical'
                size_hint_x: 0.5
                spacing: dp(6)

                Label:
                    text: 'RFID SLOTS'
                    font_size: '15sp'
                    bold: True
                    color: 0.98, 0.65, 0.25, 1
                    size_hint_y: None
                    height: dp(26)
                    halign: 'left'
                    text_size: self.size
                    valign: 'middle'

                ScrollView:
                    do_scroll_x: False
                    bar_width: '3dp'
                    bar_color: 0.98, 0.65, 0.25, 0.4

                    GridLayout:
                        id: slot_grid
                        cols: 1
                        size_hint_y: None
                        height: self.minimum_height
                        spacing: dp(6)

            # RIGHT: Weight Controls
            BoxLayout:
                orientation: 'vertical'
                size_hint_x: 0.5
                spacing: dp(6)

                Label:
                    text: 'WEIGHT CONTROLS'
                    font_size: '15sp'
                    bold: True
                    color: 0.98, 0.65, 0.25, 1
                    size_hint_y: None
                    height: dp(26)
                    halign: 'left'
                    text_size: self.size
                    valign: 'middle'

                ScrollView:
                    do_scroll_x: False
                    bar_width: '3dp'
                    bar_color: 0.98, 0.65, 0.25, 0.4

                    GridLayout:
                        id: weight_grid
                        cols: 1
                        size_hint_y: None
                        height: self.minimum_height
                        spacing: dp(6)

        # ---- BOTTOM INFO BAR ----
        BoxLayout:
            size_hint_y: None
            height: dp(32)
            padding: [dp(12), dp(4)]
            canvas.before:
                Color:
                    rgba: 0.10, 0.12, 0.16, 1
                Rectangle:
                    pos: self.pos
                    size: self.size

            Label:
                id: status_label
                text: 'Ready - Use controls to simulate sensor events'
                font_size: '12sp'
                color: 0.60, 0.64, 0.72, 1
                halign: 'left'
                text_size: self.size
                valign: 'middle'
''')


# ==============================================================
# SLOT CONTROL CARD
# ==============================================================

class _SlotControlCard(BoxLayout):
    """Control card for a single RFID slot: shows status + add/remove buttons."""

    def __init__(self, slot_index, reader_id, screen_ref, **kwargs):
        super().__init__(
            orientation='vertical',
            size_hint_y=None,
            height=dp(110),
            spacing=dp(4),
            padding=dp(8),
            **kwargs,
        )
        self._slot_index = slot_index
        self._reader_id = reader_id
        self._screen = screen_ref
        self._current_tag = None

        # Card background
        with self.canvas.before:
            Color(*DS.BG_CARD)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(DS.RADIUS)])
        self.bind(pos=lambda w, v: setattr(w._bg, 'pos', v),
                  size=lambda w, v: setattr(w._bg, 'size', v))

        # Header row
        header = BoxLayout(size_hint_y=None, height=dp(24), spacing=dp(4))
        header.add_widget(Label(
            text=f'SLOT {slot_index + 1}',
            font_size=DS.FONT_SMALL,
            bold=True,
            color=DS.ACCENT,
            size_hint_x=0.4,
            halign='left',
            text_size=(None, None),
        ))
        self._status_lbl = Label(
            text='EMPTY',
            font_size=DS.FONT_TINY,
            color=DS.TEXT_MUTED,
            size_hint_x=0.6,
            halign='right',
            text_size=(None, None),
        )
        header.add_widget(self._status_lbl)
        self.add_widget(header)

        # Tag info label
        self._tag_lbl = Label(
            text='No tag',
            font_size=DS.FONT_TINY,
            color=DS.TEXT_SECONDARY,
            size_hint_y=None,
            height=dp(18),
            halign='left',
            text_size=(None, None),
        )
        self.add_widget(self._tag_lbl)

        # Buttons row
        btn_row = BoxLayout(size_hint_y=None, height=dp(DS.BTN_HEIGHT_SM), spacing=dp(4))

        # Add tag button (uses preset tags)
        tag_data = _TEST_TAGS[slot_index % len(_TEST_TAGS)]
        self._add_btn = Button(
            text=f'ADD {tag_data[0]}',
            font_size=DS.FONT_TINY,
            bold=True,
            size_hint_x=0.55,
            background_normal='',
            background_color=DS.ACCENT_DIM,
            color=DS.TEXT_PRIMARY,
        )
        self._add_btn.bind(on_release=self._on_add)

        self._remove_btn = Button(
            text='REMOVE',
            font_size=DS.FONT_TINY,
            bold=True,
            size_hint_x=0.45,
            background_normal='',
            background_color=DS.DANGER_DIM,
            color=DS.TEXT_PRIMARY,
        )
        self._remove_btn.bind(on_release=self._on_remove)

        btn_row.add_widget(self._add_btn)
        btn_row.add_widget(self._remove_btn)
        self.add_widget(btn_row)

    def _on_add(self, _inst):
        """Add a simulated tag to this slot."""
        app = App.get_running_app()
        if not app or not hasattr(app, 'rfid'):
            return

        tag_data = _TEST_TAGS[self._slot_index % len(_TEST_TAGS)]
        tag_id = tag_data[0]

        try:
            app.rfid.add_tag(self._reader_id, tag_id)
            self._current_tag = tag_id
            self._status_lbl.text = 'OCCUPIED'
            self._status_lbl.color = DS.SUCCESS
            self._tag_lbl.text = f'{tag_id} ({tag_data[1]})'
            self._screen._set_status(f'Tag {tag_id} added to slot {self._slot_index + 1}')
            logger.info(f"[DEMO] Added tag {tag_id} to {self._reader_id}")
        except Exception as e:
            self._screen._set_status(f'Error: {e}')

    def _on_remove(self, _inst):
        """Remove the simulated tag from this slot."""
        app = App.get_running_app()
        if not app or not hasattr(app, 'rfid'):
            return

        try:
            app.rfid.remove_tag(self._reader_id)
            tag_id = self._current_tag or '?'
            self._current_tag = None
            self._status_lbl.text = 'EMPTY'
            self._status_lbl.color = DS.TEXT_MUTED
            self._tag_lbl.text = 'No tag'
            self._screen._set_status(f'Tag removed from slot {self._slot_index + 1}')
            logger.info(f"[DEMO] Removed tag from {self._reader_id}")
        except Exception as e:
            self._screen._set_status(f'Error: {e}')

    def refresh_status(self):
        """Sync visual state with actual fake driver state."""
        app = App.get_running_app()
        if not app or not hasattr(app, 'rfid'):
            return
        try:
            tags_map = getattr(app.rfid, '_tags', {})
            tag = tags_map.get(self._reader_id)
            if tag:
                self._current_tag = tag
                self._status_lbl.text = 'OCCUPIED'
                self._status_lbl.color = DS.SUCCESS
                # Find label from test tags
                name = next((t[1] for t in _TEST_TAGS if t[0] == tag), tag)
                self._tag_lbl.text = f'{tag} ({name})'
            else:
                self._current_tag = None
                self._status_lbl.text = 'EMPTY'
                self._status_lbl.color = DS.TEXT_MUTED
                self._tag_lbl.text = 'No tag'
        except Exception:
            pass


# ==============================================================
# WEIGHT CONTROL CARD
# ==============================================================

class _WeightControlCard(BoxLayout):
    """Control card for a weight channel with preset buttons and custom input."""

    def __init__(self, channel_name, display_name, presets, screen_ref, **kwargs):
        super().__init__(
            orientation='vertical',
            size_hint_y=None,
            height=dp(130),
            spacing=dp(4),
            padding=dp(8),
            **kwargs,
        )
        self._channel = channel_name
        self._screen = screen_ref

        # Card background
        with self.canvas.before:
            Color(*DS.BG_CARD)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(DS.RADIUS)])
        self.bind(pos=lambda w, v: setattr(w._bg, 'pos', v),
                  size=lambda w, v: setattr(w._bg, 'size', v))

        # Header
        header = BoxLayout(size_hint_y=None, height=dp(24))
        header.add_widget(Label(
            text=display_name,
            font_size=DS.FONT_SMALL,
            bold=True,
            color=DS.ACCENT,
            size_hint_x=0.5,
            halign='left',
            text_size=(None, None),
        ))
        self._current_lbl = Label(
            text='0 g',
            font_size=DS.FONT_SMALL,
            bold=True,
            color=DS.TEXT_PRIMARY,
            size_hint_x=0.5,
            halign='right',
            text_size=(None, None),
        )
        header.add_widget(self._current_lbl)
        self.add_widget(header)

        # Preset buttons row
        preset_row = BoxLayout(size_hint_y=None, height=dp(DS.BTN_HEIGHT_SM), spacing=dp(4))
        for label, grams in presets:
            btn = Button(
                text=label,
                font_size=DS.FONT_TINY,
                bold=True,
                background_normal='',
                background_color=DS.ACCENT_DIM,
                color=DS.TEXT_PRIMARY,
            )
            btn.bind(on_release=lambda inst, g=grams: self._set_weight(g))
            preset_row.add_widget(btn)
        self.add_widget(preset_row)

        # Custom input row
        input_row = BoxLayout(size_hint_y=None, height=dp(DS.BTN_HEIGHT_SM), spacing=dp(4))
        self._weight_input = TextInput(
            hint_text='grams',
            multiline=False,
            input_filter='float',
            font_size=DS.FONT_SMALL,
            size_hint_x=0.6,
            background_color=DS.BG_INPUT,
            foreground_color=DS.TEXT_PRIMARY,
            hint_text_color=DS.TEXT_MUTED,
            cursor_color=DS.PRIMARY,
            padding=[dp(8), dp(8)],
        )
        set_btn = Button(
            text='SET',
            font_size=DS.FONT_SMALL,
            bold=True,
            size_hint_x=0.4,
            background_normal='',
            background_color=DS.ACCENT,
            color=DS.BG_DARK,
        )
        set_btn.bind(on_release=self._on_custom_set)
        input_row.add_widget(self._weight_input)
        input_row.add_widget(set_btn)
        self.add_widget(input_row)

    def _set_weight(self, grams):
        """Set weight on the fake driver channel."""
        app = App.get_running_app()
        if not app or not hasattr(app, 'weight'):
            return
        try:
            app.weight.set_weight(self._channel, float(grams))
            self._current_lbl.text = f'{grams:.0f} g'
            self._screen._set_status(f'{self._channel}: {grams:.0f}g')
            logger.info(f"[DEMO] Weight {self._channel} = {grams}g")
        except Exception as e:
            self._screen._set_status(f'Error: {e}')

    def _on_custom_set(self, _inst):
        """Set custom weight from the text input."""
        val = self._weight_input.text.strip()
        if val:
            try:
                grams = float(val)
                self._set_weight(grams)
                self._weight_input.text = ''
            except ValueError:
                self._screen._set_status('Invalid weight value')

    def refresh_current(self):
        """Read current weight from driver."""
        app = App.get_running_app()
        if not app or not hasattr(app, 'weight'):
            return
        try:
            weights = getattr(app.weight, '_weights', {})
            w = weights.get(self._channel, 0)
            self._current_lbl.text = f'{w:.0f} g'
        except Exception:
            pass


# ==============================================================
# DEMO SCREEN
# ==============================================================

class DemoScreen(Screen):
    """Test mode simulation controls screen."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._slot_cards = []
        self._weight_cards = []
        self._built = False
        self._refresh_event = None

    # ----------------------------------------------------------
    # Lifecycle
    # ----------------------------------------------------------

    def on_enter(self):
        """Build controls and start refresh loop."""
        # Guard: only accessible in TEST/HYBRID mode
        app = App.get_running_app()
        mode = getattr(app, 'mode', getattr(settings, 'MODE', 'auto')) if app else 'auto'
        if mode == 'live':
            self._set_status('Demo controls are disabled in LIVE mode')
            return

        if not self._built:
            self._build_controls()
        self._refresh_all()
        self._refresh_event = Clock.schedule_interval(self._on_refresh_tick, 2.0)

    def on_leave(self):
        """Stop refresh."""
        if self._refresh_event:
            self._refresh_event.cancel()
            self._refresh_event = None

    def go_back(self):
        app = App.get_running_app()
        if app:
            app.root.current = 'settings'

    # ----------------------------------------------------------
    # Status
    # ----------------------------------------------------------

    def _set_status(self, text):
        """Update the bottom status label."""
        lbl = self.ids.get('status_label')
        if lbl:
            lbl.text = str(text)

    # ----------------------------------------------------------
    # Build controls
    # ----------------------------------------------------------

    def _build_controls(self):
        """Create slot and weight control cards."""
        self._built = True

        # --- Slot (RFID) controls ---
        slot_grid = self.ids.get('slot_grid')
        if slot_grid:
            for i, reader_id in enumerate(_SLOT_READERS):
                card = _SlotControlCard(i, reader_id, self)
                self._slot_cards.append(card)
                slot_grid.add_widget(card)

        # --- Weight controls ---
        weight_grid = self.ids.get('weight_grid')
        if weight_grid:
            # Shelf weight
            shelf_card = _WeightControlCard(
                channel_name='shelf1',
                display_name='SHELF WEIGHT',
                presets=[
                    ('0 kg', 0),
                    ('5 kg', 5000),
                    ('15 kg', 15000),
                    ('25 kg', 25000),
                ],
                screen_ref=self,
            )
            self._weight_cards.append(shelf_card)
            weight_grid.add_widget(shelf_card)

            # Mixing scale
            scale_card = _WeightControlCard(
                channel_name='mixing_scale',
                display_name='MIXING SCALE',
                presets=[
                    ('0 g', 0),
                    ('200 g', 200),
                    ('500 g', 500),
                    ('1 kg', 1000),
                ],
                screen_ref=self,
            )
            self._weight_cards.append(scale_card)
            weight_grid.add_widget(scale_card)

            # Spacer
            weight_grid.add_widget(Widget(size_hint_y=None, height=dp(8)))

            # Quick actions
            weight_grid.add_widget(Label(
                text='QUICK ACTIONS',
                font_size=DS.FONT_SMALL,
                bold=True,
                color=DS.ACCENT,
                size_hint_y=None,
                height=dp(24),
                halign='left',
                text_size=(None, None),
            ))

            # Full shelf button
            full_btn = Button(
                text='LOAD ALL SLOTS',
                font_size=DS.FONT_SMALL,
                bold=True,
                size_hint_y=None,
                height=dp(DS.BTN_HEIGHT_SM),
                background_normal='',
                background_color=DS.ACCENT_DIM,
                color=DS.TEXT_PRIMARY,
            )
            full_btn.bind(on_release=lambda _: self._load_all_slots())
            weight_grid.add_widget(full_btn)

            # Clear all button
            clear_btn = Button(
                text='CLEAR ALL SLOTS',
                font_size=DS.FONT_SMALL,
                bold=True,
                size_hint_y=None,
                height=dp(DS.BTN_HEIGHT_SM),
                background_normal='',
                background_color=DS.DANGER_DIM,
                color=DS.TEXT_PRIMARY,
            )
            clear_btn.bind(on_release=lambda _: self._clear_all_slots())
            weight_grid.add_widget(clear_btn)

    # ----------------------------------------------------------
    # Quick actions
    # ----------------------------------------------------------

    def _load_all_slots(self):
        """Add a tag to every slot and set shelf weight high."""
        app = App.get_running_app()
        if not app or not hasattr(app, 'rfid'):
            return
        for i, reader_id in enumerate(_SLOT_READERS):
            tag_data = _TEST_TAGS[i % len(_TEST_TAGS)]
            try:
                app.rfid.add_tag(reader_id, tag_data[0])
            except Exception:
                pass
        # Set shelf weight for 4 cans (~5kg each)
        if hasattr(app, 'weight'):
            try:
                app.weight.set_weight('shelf1', 20000)
            except Exception:
                pass
        self._refresh_all()
        self._set_status('All slots loaded with test tags')

    def _clear_all_slots(self):
        """Remove all tags and zero out weight."""
        app = App.get_running_app()
        if not app or not hasattr(app, 'rfid'):
            return
        for reader_id in _SLOT_READERS:
            try:
                app.rfid.remove_tag(reader_id)
            except Exception:
                pass
        if hasattr(app, 'weight'):
            try:
                app.weight.set_weight('shelf1', 0)
                app.weight.set_weight('mixing_scale', 0)
            except Exception:
                pass
        self._refresh_all()
        self._set_status('All slots cleared')

    # ----------------------------------------------------------
    # Refresh
    # ----------------------------------------------------------

    def _refresh_all(self):
        """Sync all card visuals with current driver state."""
        for card in self._slot_cards:
            card.refresh_status()
        for card in self._weight_cards:
            card.refresh_current()

    def _on_refresh_tick(self, dt):
        """Periodic refresh."""
        self._refresh_all()
