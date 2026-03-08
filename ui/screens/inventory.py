"""
Inventory Screen - Real-time Shelf & Slot View (2026 Redesign)

Layout (800x480):
+--------------------------------------------------+
| <  |        INVENTORY         |   Shelf: 18.5 kg |  44dp
+--------------------------------------------------+
|  +--------+  +--------+  +--------+  +--------+  |
|  | SLOT 1 |  | SLOT 2 |  | SLOT 3 |  | SLOT 4 |  |  Slot cards
|  | SIGMA..|  | SIGMA..|  | THINNE.|  |  EMPTY |  |  with colored
|  | 6.2 kg |  | 1.8 kg |  | 4.1 kg |  |   ---  |  |  left accent
|  |  OCC   |  |  OCC   |  |  REM   |  |        |  |  bar + status
|  +--------+  +--------+  +--------+  +--------+  |
+--------------------------------------------------+
|  RECENT EVENTS (scrollable log with color-coded)  |
+--------------------------------------------------+

Design:
- Slot cards have colored left accent bar (status color)
- Large status indicators visible from distance
- Event log with colored event type badges
- Auto-refresh every 500ms
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.lang import Builder
from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle, Rectangle


Builder.load_string('''
#:import DS ui.app.DS

<InventoryScreen>:
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
                text: 'INVENTORY'
                font_size: '18sp'
                bold: True
                color: 0.96, 0.97, 0.98, 1
                size_hint_x: 0.5
                halign: 'center'
                text_size: self.size
                valign: 'middle'

            Label:
                id: shelf_weight
                text: 'Shelf: -- g'
                font_size: '13sp'
                color: 0.38, 0.42, 0.50, 1
                size_hint_x: 0.3
                halign: 'right'
                text_size: self.size
                valign: 'middle'

        # ---- SLOT GRID ----
        BoxLayout:
            id: slot_grid
            orientation: 'horizontal'
            padding: [10, 8, 10, 4]
            spacing: 8
            size_hint_y: 0.52

        # ---- LEGEND BAR ----
        BoxLayout:
            size_hint_y: None
            height: '22dp'
            padding: [12, 0]
            spacing: 16

            Label:
                text: '[color=00d1ba]|[/color] Occupied'
                markup: True
                font_size: '11sp'
                color: 0.38, 0.42, 0.50, 1
                halign: 'center'
                text_size: self.size
                valign: 'middle'

            Label:
                text: '[color=4d5566]|[/color] Empty'
                markup: True
                font_size: '11sp'
                color: 0.38, 0.42, 0.50, 1
                halign: 'center'
                text_size: self.size
                valign: 'middle'

            Label:
                text: '[color=fba640]|[/color] Removed'
                markup: True
                font_size: '11sp'
                color: 0.38, 0.42, 0.50, 1
                halign: 'center'
                text_size: self.size
                valign: 'middle'

            Label:
                text: '[color=ed4552]|[/color] Alert'
                markup: True
                font_size: '11sp'
                color: 0.38, 0.42, 0.50, 1
                halign: 'center'
                text_size: self.size
                valign: 'middle'

        # ---- EVENT LOG SECTION ----
        BoxLayout:
            size_hint_y: None
            height: '22dp'
            padding: [12, 2]
            Label:
                text: 'RECENT EVENTS'
                font_size: '11sp'
                bold: True
                color: 0.38, 0.42, 0.50, 1
                halign: 'left'
                text_size: self.size
                valign: 'middle'

        ScrollView:
            size_hint_y: 0.35
            do_scroll_x: False
            Label:
                id: event_log_label
                text: ''
                font_size: '12sp'
                color: 0.50, 0.54, 0.62, 1
                halign: 'left'
                valign: 'top'
                text_size: self.width - 24, None
                size_hint_y: None
                height: self.texture_size[1] + 10
                padding: [12, 4]
                markup: True
''')


class SlotCard(BoxLayout):
    """Visual card representing a single shelf slot with left accent bar."""

    def __init__(self, slot_index, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = [10, 8]
        self.spacing = 3
        self.slot_index = slot_index

        # Background card
        with self.canvas.before:
            self._bg_color = Color(0.10, 0.12, 0.16, 1)
            self._bg_rect = RoundedRectangle(radius=[10])
            # Left accent bar
            self._accent_color = Color(0.30, 0.33, 0.38, 1)
            self._accent_rect = RoundedRectangle(radius=[10, 0, 0, 10])

        self.bind(pos=self._update_bg, size=self._update_bg)

        # Slot number (top)
        self._slot_label = Label(
            text=f'SLOT {slot_index + 1}',
            font_size='12sp',
            bold=True,
            color=(0.38, 0.42, 0.50, 1),
            size_hint_y=0.12,
        )
        self.add_widget(self._slot_label)

        # Status indicator (large text)
        self._status_icon = Label(
            text='---',
            font_size='15sp',
            bold=True,
            color=(0.30, 0.33, 0.38, 1),
            size_hint_y=0.18,
        )
        self.add_widget(self._status_icon)

        # Product name
        self._name_label = Label(
            text='EMPTY',
            font_size='13sp',
            bold=True,
            color=(0.60, 0.64, 0.72, 1),
            size_hint_y=0.25,
            halign='center',
            text_size=(None, None),
        )
        self.add_widget(self._name_label)

        # Weight
        self._weight_label = Label(
            text='',
            font_size='12sp',
            color=(0.38, 0.42, 0.50, 1),
            size_hint_y=0.20,
        )
        self.add_widget(self._weight_label)

        # Status text badge
        self._status_text = Label(
            text='EMPTY',
            font_size='11sp',
            bold=True,
            color=(0.30, 0.33, 0.38, 1),
            size_hint_y=0.15,
        )
        self.add_widget(self._status_text)

    def _update_bg(self, *args):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        # Left accent bar: 4px wide on the left edge
        self._accent_rect.pos = (self.x, self.y)
        self._accent_rect.size = (4, self.height)

    def _get_product_name(self, tag_uid):
        """Look up product name for an RFID tag."""
        try:
            app = App.get_running_app()
            product = app.db.get_product_for_tag(tag_uid)
            if product:
                name = product.get('name', '')
                if len(name) > 14:
                    return name[:12] + '..'
                return name
        except Exception:
            pass
        return None

    def update(self, slot):
        """Update card display from a Slot object."""
        status = slot.status.value

        # Colors per status
        status_configs = {
            'occupied': {
                'accent': (0.00, 0.82, 0.73, 1),
                'bg': (0.06, 0.14, 0.13, 1),
                'icon_color': (0.00, 0.82, 0.73, 1),
                'icon': 'OCC',
                'status_text': 'OCCUPIED',
            },
            'removed': {
                'accent': (0.98, 0.65, 0.25, 1),
                'bg': (0.16, 0.12, 0.06, 1),
                'icon_color': (0.98, 0.65, 0.25, 1),
                'icon': 'REM',
                'status_text': 'REMOVED',
            },
            'in_use': {
                'accent': (0.98, 0.76, 0.22, 1),
                'bg': (0.16, 0.14, 0.06, 1),
                'icon_color': (0.98, 0.76, 0.22, 1),
                'icon': 'USE',
                'status_text': 'IN USE',
            },
            'anomaly': {
                'accent': (0.93, 0.27, 0.32, 1),
                'bg': (0.16, 0.06, 0.06, 1),
                'icon_color': (0.93, 0.27, 0.32, 1),
                'icon': '!',
                'status_text': 'ANOMALY',
            },
        }

        config = status_configs.get(status, {
            'accent': (0.20, 0.22, 0.28, 1),
            'bg': (0.10, 0.12, 0.16, 1),
            'icon_color': (0.30, 0.33, 0.38, 1),
            'icon': '---',
            'status_text': 'EMPTY',
        })

        self._accent_color.rgba = config['accent']
        self._bg_color.rgba = config['bg']
        self._status_icon.text = config['icon']
        self._status_icon.color = config['icon_color']
        self._status_text.text = config['status_text']
        self._status_text.color = config['icon_color']

        # Product name
        if status == 'occupied':
            tag = slot.current_tag_id or '???'
            product_name = self._get_product_name(tag)
            self._name_label.text = product_name if product_name else tag[:14]
            self._name_label.color = (0.85, 0.88, 0.95, 1)
        elif status == 'removed':
            tag = slot.current_tag_id or '?'
            product_name = self._get_product_name(tag)
            self._name_label.text = product_name or tag[:12]
            self._name_label.color = (0.70, 0.65, 0.55, 1)
        elif status == 'in_use':
            self._name_label.text = '(elsewhere)'
            self._name_label.color = (0.70, 0.68, 0.50, 1)
        elif status == 'anomaly':
            self._name_label.text = 'CHECK SLOT'
            self._name_label.color = (0.93, 0.27, 0.32, 1)
        else:
            self._name_label.text = '---'
            self._name_label.color = (0.30, 0.33, 0.38, 1)

        # Weight display
        w = slot.weight_current_g
        if w > 0:
            if w >= 1000:
                self._weight_label.text = f'{w/1000:.1f} kg'
            else:
                self._weight_label.text = f'{w:.0f} g'
            self._weight_label.color = (0.50, 0.54, 0.62, 1)
        else:
            self._weight_label.text = ''


class InventoryScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._slot_cards = []
        self._refresh_event = None

    def on_enter(self):
        """Build slot cards and start refresh loop."""
        app = App.get_running_app()

        # Build cards if not yet created
        grid = self.ids.slot_grid
        if not self._slot_cards:
            grid.clear_widgets()
            slots = app.inventory.get_all_slots()
            for i, slot in enumerate(slots):
                card = SlotCard(i)
                card.update(slot)
                self._slot_cards.append(card)
                grid.add_widget(card)

        # Start refresh
        self._refresh_event = Clock.schedule_interval(self._refresh, 0.5)
        self._refresh(0)

    def on_leave(self):
        if self._refresh_event:
            self._refresh_event.cancel()

    def _refresh(self, dt):
        """Update all slot cards and event log."""
        app = App.get_running_app()
        slots = app.inventory.get_all_slots()

        # Update slot cards
        for i, slot in enumerate(slots):
            if i < len(self._slot_cards):
                self._slot_cards[i].update(slot)

        # Update shelf weight
        try:
            reading = app.weight.read_weight('shelf1')
            if reading.grams >= 1000:
                self.ids.shelf_weight.text = f'Shelf: {reading.grams/1000:.1f} kg'
            else:
                self.ids.shelf_weight.text = f'Shelf: {reading.grams:.0f} g'
        except Exception:
            self.ids.shelf_weight.text = 'Shelf: -- g'

        # Update event log
        events = app.event_log[-8:]  # Last 8 events
        lines = []
        for e in reversed(events):
            etype = e.event_type.value.replace('_', ' ')
            tag = e.tag_id[:12] if e.tag_id else ''
            slot_id = e.slot_id.replace('shelf1_', '') if e.slot_id else ''

            # Color by event type
            if 'unauthorized' in etype or 'error' in etype:
                color = 'ed4552'
            elif 'removed' in etype:
                color = 'fba640'
            elif 'placed' in etype or 'returned' in etype:
                color = '00d1ba'
            elif 'mix' in etype:
                color = '5494d9'
            else:
                color = '6b7280'

            lines.append(f'[color={color}]{etype}[/color]  {slot_id}  {tag}')

        self.ids.event_log_label.text = '\n'.join(lines) if lines else 'No events yet'
