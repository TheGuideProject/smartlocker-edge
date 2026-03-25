"""
Shelf Map Screen - Visual grid of all shelf slots (2026 Redesign)

Displays a 4-column grid of slot cards showing:
- Slot number, product name, weight, fill percentage, status color

Status colors:
    occupied  = teal
    empty     = gray
    removed   = amber
    in_use    = yellow
    anomaly   = red

Refreshes every 1.5 seconds.
Data from app.inventory_engine.shelves dict with nested slots.

Slot object attrs:
    slot_id, status, current_tag_id, current_product_name,
    weight_current_g, weight_placed_g (mapped to weight_when_placed_g)
"""

import logging

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.lang import Builder
from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.graphics import Color, RoundedRectangle, Rectangle

from ui.app import DS
from core.models import SlotStatus

logger = logging.getLogger("smartlocker.shelf_map")

# Map SlotStatus to DS color tokens
_STATUS_COLORS = {
    SlotStatus.OCCUPIED:         DS.SLOT_OCCUPIED,
    SlotStatus.EMPTY:            DS.SLOT_EMPTY,
    SlotStatus.REMOVED:          DS.SLOT_REMOVED,
    SlotStatus.IN_USE_ELSEWHERE: DS.SLOT_IN_USE,
    SlotStatus.ANOMALY:          DS.SLOT_ANOMALY,
}

_STATUS_LABELS = {
    SlotStatus.OCCUPIED:         'OCCUPIED',
    SlotStatus.EMPTY:            'EMPTY',
    SlotStatus.REMOVED:          'REMOVED',
    SlotStatus.IN_USE_ELSEWHERE: 'IN USE',
    SlotStatus.ANOMALY:          'ANOMALY',
}


# ==============================================================
# KV LAYOUT
# ==============================================================

Builder.load_string('''
<ShelfMapScreen>:
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
                text: 'SHELF MAP'
                font_size: '18sp'
                bold: True
                color: 0.96, 0.97, 0.98, 1
                size_hint_x: 0.4
                halign: 'center'
                text_size: self.size
                valign: 'middle'

            Label:
                id: summary_label
                text: ''
                font_size: '13sp'
                color: 0.60, 0.64, 0.72, 1
                size_hint_x: 0.3
                halign: 'right'
                text_size: self.size
                valign: 'middle'

        # ---- GRID AREA ----
        ScrollView:
            do_scroll_x: False
            bar_width: '4dp'
            bar_color: 0.00, 0.82, 0.73, 0.5
            bar_inactive_color: 0.18, 0.20, 0.26, 0.3

            GridLayout:
                id: slot_grid
                cols: 4
                size_hint_y: None
                height: self.minimum_height
                padding: [dp(8), dp(8)]
                spacing: dp(6)
''')


# ==============================================================
# SLOT CARD WIDGET
# ==============================================================

class _SlotCard(BoxLayout):
    """Visual card for a single shelf slot."""

    def __init__(self, slot_id='', **kwargs):
        super().__init__(
            orientation='vertical',
            size_hint_y=None,
            height=dp(110),
            size_hint_x=1,
            spacing=dp(2),
            padding=dp(8),
            **kwargs,
        )
        self._slot_id = slot_id

        # Card background (drawn in canvas.before)
        with self.canvas.before:
            Color(*DS.BG_CARD)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(DS.RADIUS)])
        self.bind(pos=self._update_bg, size=self._update_bg)

        # Status color accent bar at top
        self._accent_bar = Widget(size_hint_y=None, height=dp(4))
        with self._accent_bar.canvas:
            Color(*DS.SLOT_EMPTY)
            self._accent_rect = RoundedRectangle(
                pos=self._accent_bar.pos, size=self._accent_bar.size,
                radius=[dp(2)],
            )
        self._accent_bar.bind(
            pos=lambda w, v: setattr(self._accent_rect, 'pos', v),
            size=lambda w, v: setattr(self._accent_rect, 'size', v),
        )
        self.add_widget(self._accent_bar)

        # Slot number label
        self._slot_lbl = Label(
            text='--',
            font_size=DS.FONT_H3,
            bold=True,
            color=DS.TEXT_PRIMARY,
            size_hint_y=None,
            height=dp(22),
            halign='center',
            text_size=(None, None),
        )
        self.add_widget(self._slot_lbl)

        # Product name
        self._product_lbl = Label(
            text='',
            font_size=DS.FONT_TINY,
            color=DS.TEXT_SECONDARY,
            size_hint_y=None,
            height=dp(16),
            halign='center',
            text_size=(None, None),
            shorten=True,
            shorten_from='right',
        )
        self.add_widget(self._product_lbl)

        # Weight / fill row
        weight_row = BoxLayout(size_hint_y=None, height=dp(16))
        self._weight_lbl = Label(
            text='0 g',
            font_size=DS.FONT_TINY,
            color=DS.TEXT_MUTED,
            size_hint_x=0.5,
            halign='left',
            text_size=(None, None),
        )
        self._fill_lbl = Label(
            text='',
            font_size=DS.FONT_TINY,
            bold=True,
            color=DS.TEXT_MUTED,
            size_hint_x=0.5,
            halign='right',
            text_size=(None, None),
        )
        weight_row.add_widget(self._weight_lbl)
        weight_row.add_widget(self._fill_lbl)
        self.add_widget(weight_row)

        # Fill bar background + fill
        bar_container = Widget(size_hint_y=None, height=dp(6))
        with bar_container.canvas:
            Color(*DS.BG_INPUT)
            self._bar_bg = RoundedRectangle(
                pos=bar_container.pos, size=bar_container.size, radius=[dp(3)])
            Color(*DS.SLOT_EMPTY)
            self._bar_fill = RoundedRectangle(
                pos=bar_container.pos, size=(0, dp(6)), radius=[dp(3)])
        bar_container.bind(
            pos=self._update_bar,
            size=self._update_bar,
        )
        self._bar_container = bar_container
        self._fill_pct = 0
        self.add_widget(bar_container)

        # Status badge
        self._status_lbl = Label(
            text='EMPTY',
            font_size=DS.FONT_TINY,
            bold=True,
            color=DS.SLOT_EMPTY,
            size_hint_y=None,
            height=dp(14),
            halign='center',
            text_size=(None, None),
        )
        self.add_widget(self._status_lbl)

    def _update_bg(self, *_args):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def _update_bar(self, *_args):
        c = self._bar_container
        self._bar_bg.pos = c.pos
        self._bar_bg.size = c.size
        fill_w = max(0, c.width * self._fill_pct / 100.0)
        self._bar_fill.pos = c.pos
        self._bar_fill.size = (fill_w, c.height)

    def update(self, slot):
        """Refresh card with current slot data."""
        # Slot number
        position = getattr(slot, 'position', 0)
        self._slot_lbl.text = f'#{position}'
        self._slot_id = getattr(slot, 'slot_id', '')

        # Status
        status = getattr(slot, 'status', SlotStatus.EMPTY)
        if isinstance(status, str):
            # Handle string status values
            status_map = {s.value: s for s in SlotStatus}
            status = status_map.get(status, SlotStatus.EMPTY)

        color = _STATUS_COLORS.get(status, DS.SLOT_EMPTY)
        label = _STATUS_LABELS.get(status, 'UNKNOWN')

        self._status_lbl.text = label
        self._status_lbl.color = color

        # Accent bar color
        self._accent_bar.canvas.clear()
        with self._accent_bar.canvas:
            Color(*color)
            self._accent_rect = RoundedRectangle(
                pos=self._accent_bar.pos, size=self._accent_bar.size,
                radius=[dp(2)],
            )

        # Product name
        product_name = getattr(slot, 'current_product_name',
                               getattr(slot, 'current_product_id', ''))
        if product_name:
            self._product_lbl.text = str(product_name)[:20]
            self._product_lbl.color = DS.TEXT_SECONDARY
        else:
            self._product_lbl.text = 'No product' if status == SlotStatus.EMPTY else '--'
            self._product_lbl.color = DS.TEXT_MUTED

        # Weight
        weight_current = getattr(slot, 'weight_current_g', 0)
        weight_placed = getattr(slot, 'weight_when_placed_g',
                                getattr(slot, 'weight_placed_g', 0))

        self._weight_lbl.text = f'{weight_current:.0f}g'

        # Fill percentage
        if weight_placed and weight_placed > 0:
            pct = max(0, min(100, (weight_current / weight_placed) * 100))
        else:
            pct = 100.0 if status == SlotStatus.OCCUPIED else 0.0

        self._fill_pct = pct
        self._fill_lbl.text = f'{pct:.0f}%'

        # Fill bar color
        if pct > 50:
            bar_color = DS.SUCCESS
        elif pct > 25:
            bar_color = DS.WARNING
        elif pct > 0:
            bar_color = DS.DANGER
        else:
            bar_color = DS.SLOT_EMPTY

        self._fill_lbl.color = bar_color

        # Redraw the fill bar with updated color
        c = self._bar_container
        fill_w = max(0, c.width * self._fill_pct / 100.0)
        c.canvas.clear()
        with c.canvas:
            Color(*DS.BG_INPUT)
            self._bar_bg = RoundedRectangle(pos=c.pos, size=c.size, radius=[dp(3)])
            Color(*bar_color)
            self._bar_fill = RoundedRectangle(pos=c.pos, size=(fill_w, c.height), radius=[dp(3)])


# ==============================================================
# SHELF MAP SCREEN
# ==============================================================

class ShelfMapScreen(Screen):
    """Visual grid display of all shelf slots."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._slot_cards = {}  # slot_id -> _SlotCard
        self._refresh_event = None
        self._built = False

    # ----------------------------------------------------------
    # Lifecycle
    # ----------------------------------------------------------

    def on_enter(self):
        """Build grid and start refresh."""
        if not self._built:
            self._build_grid()
        self._refresh_slots(0)
        self._refresh_event = Clock.schedule_interval(self._refresh_slots, 1.5)

    def on_leave(self):
        """Stop refresh."""
        if self._refresh_event:
            self._refresh_event.cancel()
            self._refresh_event = None

    def go_back(self):
        app = App.get_running_app()
        if app:
            app.root.current = 'home'

    # ----------------------------------------------------------
    # Build grid
    # ----------------------------------------------------------

    def _build_grid(self):
        """Create slot cards for all slots in inventory_engine."""
        self._built = True
        grid = self.ids.get('slot_grid')
        if not grid:
            return

        grid.clear_widgets()
        self._slot_cards.clear()

        app = App.get_running_app()
        all_slots = self._get_all_slots(app)

        if not all_slots:
            # No slots configured - show placeholder cards for 4 default slots
            for i in range(4):
                card = _SlotCard(slot_id=f'slot_{i+1}')
                card._slot_lbl.text = f'#{i+1}'
                self._slot_cards[f'slot_{i+1}'] = card
                grid.add_widget(card)
            return

        for slot in all_slots:
            slot_id = getattr(slot, 'slot_id', f'slot_{id(slot)}')
            card = _SlotCard(slot_id=slot_id)
            card.update(slot)
            self._slot_cards[slot_id] = card
            grid.add_widget(card)

    # ----------------------------------------------------------
    # Get slots from inventory engine
    # ----------------------------------------------------------

    @staticmethod
    def _get_all_slots(app):
        """Extract all Slot objects from inventory engine shelves."""
        slots = []
        if not app or not hasattr(app, 'inventory_engine') or not app.inventory_engine:
            return slots

        engine = app.inventory_engine

        # inventory_engine.shelves could be a dict or list
        shelves = getattr(engine, 'shelves', {})
        if isinstance(shelves, dict):
            shelf_list = shelves.values()
        elif isinstance(shelves, list):
            shelf_list = shelves
        else:
            return slots

        for shelf in shelf_list:
            shelf_slots = getattr(shelf, 'slots', [])
            for slot in shelf_slots:
                slots.append(slot)

        # Sort by position
        slots.sort(key=lambda s: (
            getattr(s, 'shelf_id', ''),
            getattr(s, 'position', 0),
        ))
        return slots

    # ----------------------------------------------------------
    # Refresh
    # ----------------------------------------------------------

    def _refresh_slots(self, dt):
        """Update all slot cards with current inventory state."""
        app = App.get_running_app()
        all_slots = self._get_all_slots(app)

        # If slot count changed, rebuild
        if len(all_slots) != len(self._slot_cards) and all_slots:
            self._built = False
            self._build_grid()
            return

        occupied = 0
        total = len(all_slots) or len(self._slot_cards)

        for slot in all_slots:
            slot_id = getattr(slot, 'slot_id', '')
            card = self._slot_cards.get(slot_id)
            if card:
                card.update(slot)
            status = getattr(slot, 'status', SlotStatus.EMPTY)
            if isinstance(status, str):
                if status in ('occupied',):
                    occupied += 1
            elif status == SlotStatus.OCCUPIED:
                occupied += 1

        # Update summary
        summary_lbl = self.ids.get('summary_label')
        if summary_lbl:
            summary_lbl.text = f'{occupied}/{total} occupied'
