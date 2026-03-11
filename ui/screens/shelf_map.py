"""
Shelf Map Screen - Scrollable grid of all slot positions.

Shows WHAT product is loaded WHERE, with mini progress bars.
Scales to 40-60 positions for production devices via ScrollView.
4 columns layout for 800px width.
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.lang import Builder
from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.metrics import dp


# ── Status colors ──
SLOT_COLORS = {
    'occupied': (0.00, 0.82, 0.73, 1),   # Teal
    'removed':  (0.98, 0.65, 0.25, 1),   # Amber
    'in_use':   (0.98, 0.76, 0.22, 1),   # Yellow
    'anomaly':  (0.93, 0.27, 0.32, 1),   # Red
    'empty':    (0.20, 0.22, 0.28, 1),   # Dark gray
}

COLS = 4  # 4 columns for 800px touchscreen


Builder.load_string('''
<ShelfMapScreen>:
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: 0.08, 0.09, 0.12, 1
            Rectangle:
                pos: self.pos
                size: self.size

        # ---- STATUS BAR ----
        StatusBar:
            BackButton:
                on_release: app.sm.current = 'inventory'

            Label:
                text: 'SHELF MAP'
                font_size: '18sp'
                bold: True
                color: 0.96, 0.97, 0.98, 1
                size_hint_x: 0.5
                halign: 'center'
                text_size: self.size
                valign: 'middle'

            Label:
                id: slot_count_label
                text: '-- slots'
                font_size: '13sp'
                color: 0.38, 0.42, 0.50, 1
                size_hint_x: 0.3
                halign: 'right'
                text_size: self.size
                valign: 'middle'

        # ---- GRID AREA ----
        BoxLayout:
            id: grid_area
            orientation: 'vertical'
''')


class ShelfMapScreen(Screen):
    """Scrollable grid showing all slot positions with product info."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._refresh_event = None

    def on_enter(self):
        self._refresh_event = Clock.schedule_interval(self._refresh, 1.5)
        self._refresh(0)

    def on_leave(self):
        if self._refresh_event:
            self._refresh_event.cancel()
            self._refresh_event = None

    def _build_slot_cell(self, slot, product_info):
        """Build a single slot cell widget (~180x100dp)."""
        status_val = slot.status.value
        accent = SLOT_COLORS.get(status_val, SLOT_COLORS['empty'])

        cell = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=dp(100),
            padding=[dp(8), dp(6), dp(8), dp(6)],
            spacing=dp(2),
        )

        # Background
        with cell.canvas.before:
            Color(0.11, 0.13, 0.17, 1)
            rr = RoundedRectangle(pos=cell.pos, size=cell.size, radius=[8])
        cell.bind(
            pos=lambda w, p, r=rr: setattr(r, 'pos', p),
            size=lambda w, s, r=rr: setattr(r, 'size', s),
        )

        # Top accent line (colored by status)
        with cell.canvas.after:
            Color(*accent)
            accent_rect = Rectangle(
                pos=(cell.x, cell.y + cell.height - dp(3)),
                size=(cell.width, dp(3)),
            )

        def _upd_accent(w, *_, ar=accent_rect):
            ar.pos = (w.x, w.y + w.height - dp(3))
            ar.size = (w.width, dp(3))
        cell.bind(pos=_upd_accent, size=_upd_accent)

        # Slot number label
        slot_lbl = Label(
            text=f'S{slot.position}',
            font_size='12sp',
            bold=True,
            color=accent,
            size_hint_y=None, height=dp(16),
            halign='left', valign='middle',
        )
        slot_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
        cell.add_widget(slot_lbl)

        if product_info and status_val == 'occupied':
            # Product name (truncated)
            name = product_info.get('name', 'Unknown')
            display_name = (name[:13] + '..') if len(name) > 15 else name
            name_lbl = Label(
                text=display_name,
                font_size='11sp',
                color=(0.93, 0.95, 0.97, 1),
                size_hint_y=None, height=dp(16),
                halign='left', valign='middle',
            )
            name_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
            cell.add_widget(name_lbl)

            # Remaining liters
            density = product_info.get('density_g_per_ml', 1.0) or 1.0
            liters = (slot.weight_current_g / density) / 1000.0 if density > 0 else 0
            liters_lbl = Label(
                text=f'{liters:.1f} L',
                font_size='14sp',
                bold=True,
                color=(0.96, 0.97, 0.98, 1),
                size_hint_y=None, height=dp(20),
                halign='left', valign='middle',
            )
            liters_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
            cell.add_widget(liters_lbl)

            # Mini progress bar
            fill_pct = 0.0
            if slot.weight_when_placed_g > 0:
                fill_pct = (slot.weight_current_g / slot.weight_when_placed_g) * 100.0
            fill_pct = max(0.0, min(100.0, fill_pct))

            bar_w = Widget(size_hint_y=None, height=dp(6))
            with bar_w.canvas.before:
                Color(0.20, 0.22, 0.28, 1)
                bg_rect = RoundedRectangle(pos=bar_w.pos, size=bar_w.size, radius=[3])
            if fill_pct > 50:
                bar_col = (0.00, 0.82, 0.73, 1)
            elif fill_pct > 25:
                bar_col = (0.98, 0.76, 0.22, 1)
            else:
                bar_col = (0.93, 0.27, 0.32, 1)
            with bar_w.canvas.after:
                Color(*bar_col)
                fill_rect = RoundedRectangle(
                    pos=bar_w.pos,
                    size=(bar_w.width * fill_pct / 100.0, bar_w.height),
                    radius=[3],
                )

            def _upd_bar(w, *_, bg=bg_rect, fl=fill_rect, pct=fill_pct):
                bg.pos = w.pos
                bg.size = w.size
                fl.pos = w.pos
                fl.size = (w.width * pct / 100.0, w.height)
            bar_w.bind(pos=_upd_bar, size=_upd_bar)
            cell.add_widget(bar_w)
        else:
            # Empty slot placeholder
            empty_lbl = Label(
                text='empty' if status_val == 'empty' else status_val,
                font_size='12sp',
                color=(0.38, 0.42, 0.50, 1),
                size_hint_y=None, height=dp(50),
                halign='center', valign='middle',
            )
            empty_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
            cell.add_widget(empty_lbl)

        return cell

    def _refresh(self, dt):
        """Rebuild the shelf grid."""
        app = App.get_running_app()
        grid_area = self.ids.grid_area
        grid_area.clear_widgets()

        slots = app.inventory.get_all_slots()
        total = len(slots)
        self.ids.slot_count_label.text = f'{total} slot{"s" if total != 1 else ""}'

        scroll = ScrollView(do_scroll_x=False)
        grid = GridLayout(
            cols=COLS,
            size_hint_y=None,
            spacing=dp(8),
            padding=[dp(10), dp(8), dp(10), dp(8)],
        )
        grid.bind(minimum_height=grid.setter('height'))

        for slot in sorted(slots, key=lambda s: s.position):
            product_info = None
            if slot.current_tag_id and slot.status.value == 'occupied':
                try:
                    product_info = app.db.get_product_for_tag(slot.current_tag_id)
                except Exception:
                    pass
            cell = self._build_slot_cell(slot, product_info)
            grid.add_widget(cell)

        scroll.add_widget(grid)
        grid_area.add_widget(scroll)
