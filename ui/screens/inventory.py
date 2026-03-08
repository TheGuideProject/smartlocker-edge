"""
Inventory Screen - Real-time Shelf & Slot View

Displays a visual grid of all shelf slots with:
- Slot status (occupied/empty/removed) with color coding
- RFID tag ID for each occupied slot
- Shelf weight reading
- Auto-refreshes every 0.5 seconds
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.lang import Builder
from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle, Rectangle


Builder.load_string('''
<InventoryScreen>:
    BoxLayout:
        orientation: 'vertical'

        # ---- STATUS BAR ----
        StatusBar:
            Button:
                text: '<  BACK'
                font_size: '16sp'
                size_hint_x: 0.2
                background_normal: ''
                background_color: 0.15, 0.20, 0.30, 1
                on_release: app.go_back()

            Label:
                text: 'INVENTORY'
                font_size: '20sp'
                bold: True
                size_hint_x: 0.6
                halign: 'center'
                text_size: self.size
                valign: 'middle'

            Label:
                id: shelf_weight
                text: 'Shelf: -- g'
                font_size: '14sp'
                color: 0.55, 0.60, 0.68, 1
                size_hint_x: 0.2
                halign: 'right'
                text_size: self.size
                valign: 'middle'

        # ---- SHELF HEADER ----
        BoxLayout:
            size_hint_y: None
            height: '35dp'
            padding: [15, 5]
            Label:
                text: 'SHELF 1 - Slot Status'
                font_size: '15sp'
                color: 0.55, 0.60, 0.68, 1
                halign: 'left'
                text_size: self.size
                valign: 'middle'

        # ---- SLOT GRID ----
        BoxLayout:
            id: slot_grid
            orientation: 'horizontal'
            padding: [15, 5, 15, 10]
            spacing: 10

        # ---- LEGEND ----
        BoxLayout:
            size_hint_y: None
            height: '30dp'
            padding: [15, 0]
            spacing: 20

            Label:
                text: '[color=2ec4b6]O[/color] Occupied'
                markup: True
                font_size: '13sp'
                color: 0.55, 0.60, 0.68, 1

            Label:
                text: '[color=555555]O[/color] Empty'
                markup: True
                font_size: '13sp'
                color: 0.55, 0.60, 0.68, 1

            Label:
                text: '[color=f4a261]O[/color] Removed'
                markup: True
                font_size: '13sp'
                color: 0.55, 0.60, 0.68, 1

            Label:
                text: '[color=e63946]O[/color] Alert'
                markup: True
                font_size: '13sp'
                color: 0.55, 0.60, 0.68, 1

        # ---- EVENT LOG ----
        BoxLayout:
            size_hint_y: None
            height: '30dp'
            padding: [15, 5]
            Label:
                text: 'RECENT EVENTS'
                font_size: '14sp'
                color: 0.45, 0.50, 0.58, 1
                halign: 'left'
                text_size: self.size
                valign: 'middle'

        ScrollView:
            size_hint_y: 0.35
            Label:
                id: event_log_label
                text: ''
                font_size: '13sp'
                color: 0.60, 0.65, 0.72, 1
                halign: 'left'
                valign: 'top'
                text_size: self.width - 30, None
                size_hint_y: None
                height: self.texture_size[1] + 10
                padding: [15, 5]
                markup: True
''')


class SlotCard(BoxLayout):
    """Visual card representing a single shelf slot."""

    def __init__(self, slot_index, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = [8, 8]
        self.spacing = 4
        self.slot_index = slot_index

        # Background
        with self.canvas.before:
            self._bg_color = Color(0.11, 0.16, 0.22, 1)
            self._bg_rect = RoundedRectangle(radius=[8])

        self.bind(pos=self._update_bg, size=self._update_bg)

        # Status indicator (colored circle)
        self._status_label = Label(
            text='O',
            font_size='28sp',
            bold=True,
            color=(0.33, 0.33, 0.33, 1),
            size_hint_y=0.25,
        )
        self.add_widget(self._status_label)

        # Slot name
        self._name_label = Label(
            text=f'SLOT {slot_index + 1}',
            font_size='14sp',
            bold=True,
            color=(0.75, 0.80, 0.88, 1),
            size_hint_y=0.15,
        )
        self.add_widget(self._name_label)

        # Tag ID
        self._tag_label = Label(
            text='---',
            font_size='12sp',
            color=(0.55, 0.60, 0.68, 1),
            size_hint_y=0.2,
        )
        self.add_widget(self._tag_label)

        # Status text
        self._status_text = Label(
            text='EMPTY',
            font_size='13sp',
            bold=True,
            color=(0.55, 0.60, 0.68, 1),
            size_hint_y=0.2,
        )
        self.add_widget(self._status_text)

        # Weight
        self._weight_label = Label(
            text='',
            font_size='12sp',
            color=(0.45, 0.50, 0.58, 1),
            size_hint_y=0.2,
        )
        self.add_widget(self._weight_label)

    def _update_bg(self, *args):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def _get_product_name(self, tag_uid):
        """Look up product name for an RFID tag. Returns short name or None."""
        try:
            app = App.get_running_app()
            product = app.db.get_product_for_tag(tag_uid)
            if product:
                name = product.get('name', '')
                # Shorten long names for display
                if len(name) > 16:
                    return name[:14] + '..'
                return name
        except Exception:
            pass
        return None

    def update(self, slot):
        """Update card display from a Slot object."""
        status = slot.status.value

        if status == 'occupied':
            self._status_label.color = (0.18, 0.77, 0.71, 1)  # Green
            self._bg_color.rgba = (0.08, 0.18, 0.18, 1)
            self._status_text.text = 'OCCUPIED'
            self._status_text.color = (0.18, 0.77, 0.71, 1)
            tag = slot.current_tag_id or '???'
            # Look up product name from RFID tag
            product_name = self._get_product_name(tag)
            self._tag_label.text = product_name if product_name else tag[:16]
        elif status == 'removed':
            self._status_label.color = (0.96, 0.63, 0.38, 1)  # Orange
            self._bg_color.rgba = (0.18, 0.14, 0.08, 1)
            self._status_text.text = 'REMOVED'
            self._status_text.color = (0.96, 0.63, 0.38, 1)
            tag = slot.current_tag_id or '?'
            product_name = self._get_product_name(tag)
            self._tag_label.text = f'was: {product_name or tag[:12]}'
        elif status == 'in_use':
            self._status_label.color = (0.91, 0.77, 0.42, 1)  # Yellow
            self._bg_color.rgba = (0.18, 0.16, 0.08, 1)
            self._status_text.text = 'IN USE'
            self._status_text.color = (0.91, 0.77, 0.42, 1)
            self._tag_label.text = '(elsewhere)'
        elif status == 'anomaly':
            self._status_label.color = (0.90, 0.22, 0.27, 1)  # Red
            self._bg_color.rgba = (0.18, 0.08, 0.08, 1)
            self._status_text.text = 'ANOMALY'
            self._status_text.color = (0.90, 0.22, 0.27, 1)
            self._tag_label.text = '!'
        else:  # empty
            self._status_label.color = (0.33, 0.33, 0.33, 1)  # Gray
            self._bg_color.rgba = (0.11, 0.16, 0.22, 1)
            self._status_text.text = 'EMPTY'
            self._status_text.color = (0.55, 0.60, 0.68, 1)
            self._tag_label.text = '---'

        # Weight display
        w = slot.weight_current_g
        if w > 0:
            if w >= 1000:
                self._weight_label.text = f'{w/1000:.1f} kg'
            else:
                self._weight_label.text = f'{w:.0f} g'
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
                color = 'e63946'
            elif 'removed' in etype:
                color = 'f4a261'
            elif 'placed' in etype or 'returned' in etype:
                color = '2ec4b6'
            elif 'mix' in etype:
                color = '5fa8d3'
            else:
                color = '8d99ae'

            lines.append(f'[color={color}]{etype}[/color]  {slot_id}  {tag}')

        self.ids.event_log_label.text = '\n'.join(lines) if lines else 'No events yet'
