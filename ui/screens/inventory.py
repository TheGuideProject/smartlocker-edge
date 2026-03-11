"""
Inventory Screen - Product-by-Product View (v1.0.5)

Layout (800x480):
+--------------------------------------------------+
| <  |        INVENTORY         |   4 items         |  44dp
+--------------------------------------------------+
|  ScrollView: Product cards                        |
|  +----------------------------------------------+ |
|  | [bar] SIGMACOVER 280        x2   5.8 L       | |
|  |       Colors: (grey dot) Grey, (white dot).. | |
|  |       Hardener: 4:1 ratio                    | |
|  +----------------------------------------------+ |
|  | [bar] SIGMAPRIME 200        x1   2.9 L       | |
|  |       Colors: (red dot) Red, (grey dot) Grey | |
|  +----------------------------------------------+ |
|  | [bar] THINNER 21-06         x1   3.5 L       | |
|  +----------------------------------------------+ |
+--------------------------------------------------+
|  [S1: teal] [S2: teal] [S3: gray] [S4: gray]    |  40dp
+--------------------------------------------------+

Design:
- Product cards with colored left accent bar (by type)
- Color dots from maintenance chart
- Hardener ratio for 2-component products
- Mini slot strip at bottom for at-a-glance slot status
- Auto-refresh every 1 second
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
from kivy.graphics import Color, RoundedRectangle, Rectangle, Ellipse
from kivy.metrics import dp


# ── Paint color name -> RGBA ──
PAINT_COLORS = {
    'red':       (0.90, 0.25, 0.25, 1),
    'dark red':  (0.70, 0.15, 0.15, 1),
    'brown':     (0.60, 0.38, 0.20, 1),
    'green':     (0.20, 0.70, 0.35, 1),
    'dark green': (0.12, 0.48, 0.20, 1),
    'blue':      (0.25, 0.50, 0.85, 1),
    'dark blue': (0.15, 0.30, 0.60, 1),
    'white':     (0.92, 0.92, 0.94, 1),
    'black':     (0.18, 0.18, 0.20, 1),
    'grey':      (0.55, 0.57, 0.60, 1),
    'gray':      (0.55, 0.57, 0.60, 1),
    'yellow':    (0.95, 0.85, 0.25, 1),
    'orange':    (0.95, 0.60, 0.18, 1),
    'pink':      (0.90, 0.48, 0.58, 1),
    'maroon':    (0.55, 0.15, 0.18, 1),
    'copper':    (0.75, 0.48, 0.22, 1),
    'beige':     (0.85, 0.78, 0.65, 1),
    'cream':     (0.92, 0.89, 0.78, 1),
    'silver':    (0.72, 0.74, 0.78, 1),
    'aluminum':  (0.68, 0.70, 0.74, 1),
    'aluminium': (0.68, 0.70, 0.74, 1),
}

# ── Type accent colors ──
TYPE_ACCENTS = {
    'base_paint': (0.00, 0.82, 0.73, 1),   # Teal
    'hardener':   (0.98, 0.65, 0.25, 1),    # Amber
    'thinner':    (0.40, 0.65, 0.95, 1),    # Blue
    'primer':     (0.70, 0.50, 0.90, 1),    # Purple
}

# ── Type icons / badges ──
TYPE_BADGES = {
    'base_paint': '\U0001F3A8 Base',
    'hardener':   '\U0001F9EA Hardener',
    'thinner':    '\U0001F527 Thinner',
    'primer':     '\U0001F6E1 Primer',
}

# ── Slot status colors ──
SLOT_STATUS_COLORS = {
    'occupied': (0.00, 0.82, 0.73, 1),   # Teal
    'removed':  (0.98, 0.65, 0.25, 1),   # Amber
    'in_use':   (0.98, 0.76, 0.22, 1),   # Yellow
    'anomaly':  (0.93, 0.27, 0.32, 1),   # Red
    'empty':    (0.20, 0.22, 0.28, 1),   # Dark gray
}


# ── KV Layout ──
Builder.load_string('''
<InventoryScreen>:
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
                id: item_count
                text: '-- items'
                font_size: '13sp'
                color: 0.38, 0.42, 0.50, 1
                size_hint_x: 0.3
                halign: 'right'
                text_size: self.size
                valign: 'middle'

        # ---- CONTENT ----
        BoxLayout:
            id: content_area
            orientation: 'vertical'
''')


# ── Drawing helpers ──

def _bg(widget, color, radius=10):
    """Rounded background that tracks widget size."""
    with widget.canvas.before:
        Color(*color)
        rr = RoundedRectangle(pos=widget.pos, size=widget.size,
                              radius=[radius])
    widget.bind(
        pos=lambda w, p: setattr(rr, 'pos', p),
        size=lambda w, s: setattr(rr, 'size', s),
    )


def _bar(widget, color, w=4):
    """Colored vertical accent bar on left edge."""
    with widget.canvas.after:
        Color(*color)
        bar = RoundedRectangle(
            pos=(widget.x + 2, widget.y + 4),
            size=(w, widget.height - 8),
            radius=[2],
        )

    def _upd(wid, *_):
        bar.pos = (wid.x + 2, wid.y + 4)
        bar.size = (w, wid.height - 8)

    widget.bind(pos=_upd, size=_upd)


def _dot_widget(color_rgba, size=14):
    """Create a small colored circle widget."""
    dot = Widget(size_hint=(None, None), size=(dp(size), dp(size)))
    with dot.canvas:
        Color(*color_rgba)
        ell = Ellipse(pos=dot.pos, size=dot.size)
    dot.bind(
        pos=lambda w, p: setattr(ell, 'pos', p),
        size=lambda w, s: setattr(ell, 'size', s),
    )
    return dot


def _resolve_color(name):
    """Get RGBA for a paint color name."""
    if not name:
        return None
    key = name.strip().lower()
    if key in PAINT_COLORS:
        return PAINT_COLORS[key]
    first_word = key.split()[0] if key else ''
    return PAINT_COLORS.get(first_word)


def _progress_bar(parent, fill_pct, color, height=8):
    """Draw a rounded progress bar on a widget via canvas."""
    fill_pct = max(0.0, min(100.0, fill_pct))
    with parent.canvas.before:
        Color(0.20, 0.22, 0.28, 1)
        track = RoundedRectangle(pos=parent.pos, size=parent.size, radius=[4])
    with parent.canvas.after:
        Color(*color)
        bar = RoundedRectangle(
            pos=parent.pos,
            size=(parent.width * fill_pct / 100.0, parent.height),
            radius=[4],
        )

    def _upd(w, *_):
        track.pos = w.pos
        track.size = w.size
        bar.pos = w.pos
        bar.size = (w.width * fill_pct / 100.0, w.height)

    parent.bind(pos=_upd, size=_upd)


class InventoryScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._refresh_event = None
        self._built = False

    def on_enter(self):
        """Start refresh loop on screen enter."""
        self._built = False
        self._refresh_event = Clock.schedule_interval(self._refresh, 1.0)
        self._refresh(0)

    def on_leave(self):
        if self._refresh_event:
            self._refresh_event.cancel()
            self._refresh_event = None

    # ── Data helpers ──

    def _get_product_colors(self):
        """Extract product -> colors mapping from maintenance chart."""
        app = App.get_running_app()
        chart = getattr(app, 'maintenance_chart', None)
        if not chart:
            return {}
        colors = {}
        for area in chart.get('areas', []):
            for layer in area.get('layers', []):
                product = layer.get('product', '')
                color = layer.get('color', '')
                if product and color:
                    colors.setdefault(product, [])
                    if color not in colors[product]:
                        colors[product].append(color)
        return colors

    def _get_hardener_map(self):
        """From chart products, find which bases have hardeners (components>=2)."""
        app = App.get_running_app()
        chart = getattr(app, 'maintenance_chart', None)
        if not chart:
            return {}
        bicomp = {}
        for p in chart.get('products', []):
            if p.get('components', 1) >= 2:
                bicomp[p['name']] = {
                    'base_ratio': p.get('base_ratio', 0),
                    'hardener_ratio': p.get('hardener_ratio', 0),
                }
        return bicomp

    def _get_current_inventory(self):
        """Build product inventory from occupied slots, with progress bar data."""
        app = App.get_running_app()
        slots = app.inventory.get_all_slots()
        product_inventory = {}
        for slot in slots:
            if slot.status.value == 'occupied' and slot.current_tag_id:
                try:
                    product = app.db.get_product_for_tag(slot.current_tag_id)
                except Exception:
                    product = None
                if product:
                    name = product.get('name', 'Unknown')
                    entry = product_inventory.setdefault(name, {
                        'cans': 0,
                        'weight_current_g': 0,
                        'weight_full_g': 0,
                        'density': product.get('density_g_per_ml', 1.0),
                        'type': product.get('product_type', 'base_paint'),
                    })
                    entry['cans'] += 1
                    entry['weight_current_g'] += slot.weight_current_g
                    entry['weight_full_g'] += slot.weight_when_placed_g if slot.weight_when_placed_g > 0 else slot.weight_current_g
        return product_inventory

    # ── UI building ──

    def _build_product_card(self, name, info, product_colors, hardener_map):
        """Build a single product card widget."""
        ptype = info.get('type', 'base_paint')
        accent = TYPE_ACCENTS.get(ptype, (0.50, 0.55, 0.64, 1))
        badge_text = TYPE_BADGES.get(ptype, 'Product')
        cans = info['cans']
        weight_current_g = info.get('weight_current_g', 0)
        weight_full_g = info.get('weight_full_g', 0)
        density = info.get('density', 1.0) or 1.0
        liters = (weight_current_g / density) / 1000.0 if density > 0 else 0
        if weight_full_g > 0:
            fill_pct = (weight_current_g / weight_full_g) * 100
        else:
            fill_pct = 100 if weight_current_g > 0 else 0

        # Card container
        card = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            padding=[14, 8, 10, 8],
            spacing=3,
        )

        # Calculate card height based on content
        has_colors = name in product_colors and product_colors[name]
        has_hardener = name in hardener_map
        card_height = 78  # base: name row + progress bar row (was 62)
        if has_colors:
            card_height += 26
        if has_hardener:
            card_height += 22
        card.height = dp(card_height)

        _bg(card, (0.11, 0.13, 0.17, 1), radius=10)
        _bar(card, accent)

        # ── Row 1: Product name + type badge + quantity + liters ──
        row1 = BoxLayout(
            orientation='horizontal',
            size_hint_y=None, height=dp(28),
            spacing=8,
        )

        # Product name (bold, white)
        name_label = Label(
            text=name,
            font_size='15sp',
            bold=True,
            color=(0.93, 0.95, 0.97, 1),
            halign='left',
            valign='middle',
            size_hint_x=0.48,
        )
        name_label.bind(size=lambda w, s: setattr(w, 'text_size', s))
        row1.add_widget(name_label)

        # Type badge
        badge_label = Label(
            text=badge_text,
            font_size='11sp',
            color=accent,
            halign='center',
            valign='middle',
            size_hint_x=0.22,
        )
        badge_label.bind(size=lambda w, s: setattr(w, 'text_size', s))
        row1.add_widget(badge_label)

        # Can count
        count_label = Label(
            text=f'x{cans}',
            font_size='15sp',
            bold=True,
            color=(0.93, 0.95, 0.97, 1),
            halign='center',
            valign='middle',
            size_hint_x=0.10,
        )
        count_label.bind(size=lambda w, s: setattr(w, 'text_size', s))
        row1.add_widget(count_label)

        # Estimated liters
        liters_label = Label(
            text=f'{liters:.1f} L',
            font_size='13sp',
            color=(0.50, 0.55, 0.64, 1),
            halign='right',
            valign='middle',
            size_hint_x=0.20,
        )
        liters_label.bind(size=lambda w, s: setattr(w, 'text_size', s))
        row1.add_widget(liters_label)

        card.add_widget(row1)

        # ── Row 1.5: Progress Bar ──
        bar_row = BoxLayout(
            orientation='horizontal',
            size_hint_y=None, height=dp(16),
            spacing=8,
            padding=[4, 2, 4, 2],
        )
        bar_container = Widget(size_hint_x=0.78, size_hint_y=None, height=dp(8))
        if fill_pct > 50:
            bar_color = (0.00, 0.82, 0.73, 1)  # Teal
        elif fill_pct > 25:
            bar_color = (0.98, 0.76, 0.22, 1)  # Yellow
        else:
            bar_color = (0.93, 0.27, 0.32, 1)  # Red
        _progress_bar(bar_container, fill_pct, bar_color)
        bar_row.add_widget(bar_container)

        pct_label = Label(
            text=f'{fill_pct:.0f}%',
            font_size='11sp',
            color=(0.50, 0.55, 0.64, 1),
            size_hint_x=0.22,
            halign='right',
            valign='middle',
        )
        pct_label.bind(size=lambda w, s: setattr(w, 'text_size', s))
        bar_row.add_widget(pct_label)
        card.add_widget(bar_row)

        # ── Row 2: Color dots (if any) ──
        if has_colors:
            color_row = BoxLayout(
                orientation='horizontal',
                size_hint_y=None, height=dp(22),
                spacing=6,
                padding=[2, 0, 0, 0],
            )

            # Small "Colors:" label
            clabel = Label(
                text='Colors:',
                font_size='11sp',
                color=(0.50, 0.55, 0.64, 1),
                size_hint=(None, 1),
                width=dp(48),
                halign='left',
                valign='middle',
            )
            clabel.bind(size=lambda w, s: setattr(w, 'text_size', s))
            color_row.add_widget(clabel)

            for cname in product_colors[name][:5]:  # max 5 colors
                rgba = _resolve_color(cname)
                if rgba:
                    dot = _dot_widget(rgba, size=12)
                    color_row.add_widget(dot)

                # Color name text
                ctxt = Label(
                    text=cname.capitalize(),
                    font_size='11sp',
                    color=(0.60, 0.64, 0.72, 1),
                    size_hint=(None, 1),
                    halign='left',
                    valign='middle',
                )
                ctxt.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0] + 4))
                ctxt.bind(size=lambda w, s: setattr(w, 'text_size', s))
                color_row.add_widget(ctxt)

            # Spacer to fill right side
            color_row.add_widget(Widget())
            card.add_widget(color_row)

        # ── Row 3: Hardener info (if 2-component) ──
        if has_hardener:
            hinfo = hardener_map[name]
            base_r = hinfo.get('base_ratio', 0)
            hard_r = hinfo.get('hardener_ratio', 0)
            ratio_text = f'2-component  |  Mix ratio {base_r}:{hard_r}'

            hardener_row = BoxLayout(
                orientation='horizontal',
                size_hint_y=None, height=dp(18),
                padding=[2, 0, 0, 0],
            )
            hlabel = Label(
                text=ratio_text,
                font_size='11sp',
                color=(0.98, 0.65, 0.25, 0.85),
                halign='left',
                valign='middle',
            )
            hlabel.bind(size=lambda w, s: setattr(w, 'text_size', s))
            hardener_row.add_widget(hlabel)
            card.add_widget(hardener_row)

        return card

    def _build_empty_card(self):
        """Build placeholder when no products are in inventory."""
        card = BoxLayout(
            orientation='vertical',
            size_hint_y=None, height=dp(80),
            padding=[20, 15],
        )
        _bg(card, (0.11, 0.13, 0.17, 1), radius=10)

        lbl = Label(
            text='No products in locker.\nPlace cans on slots to begin tracking.',
            font_size='14sp',
            color=(0.50, 0.55, 0.64, 1),
            halign='center',
            valign='middle',
        )
        lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
        card.add_widget(lbl)
        return card

    def _build_slot_strip(self):
        """Build the mini slot strip at the bottom."""
        app = App.get_running_app()
        slots = app.inventory.get_all_slots()

        strip = BoxLayout(
            orientation='horizontal',
            size_hint_y=None, height=dp(40),
            padding=[10, 4, 10, 6],
            spacing=8,
        )

        for i, slot in enumerate(slots):
            status_val = slot.status.value
            color = SLOT_STATUS_COLORS.get(status_val, (0.20, 0.22, 0.28, 1))

            slot_box = BoxLayout(
                orientation='vertical',
                spacing=2,
            )

            # Colored square
            square = Widget(size_hint_y=0.6)
            with square.canvas.before:
                Color(*color)
                rr = RoundedRectangle(pos=square.pos, size=square.size,
                                      radius=[4])
            square.bind(
                pos=lambda w, p, r=rr: setattr(r, 'pos', p),
                size=lambda w, s, r=rr: setattr(r, 'size', s),
            )
            slot_box.add_widget(square)

            # Slot label
            slabel = Label(
                text=f'S{i+1}',
                font_size='9sp',
                color=(0.38, 0.42, 0.50, 1),
                size_hint_y=0.4,
                halign='center',
                valign='top',
            )
            slabel.bind(size=lambda w, s: setattr(w, 'text_size', s))
            slot_box.add_widget(slabel)

            strip.add_widget(slot_box)

        return strip

    # ── Refresh ──

    def _refresh(self, dt):
        """Rebuild the entire product list and slot strip."""
        app = App.get_running_app()
        content = self.ids.content_area
        content.clear_widgets()

        # Get data
        product_inv = self._get_current_inventory()
        product_colors = self._get_product_colors()
        hardener_map = self._get_hardener_map()

        # Update item count in status bar
        total = sum(v['cans'] for v in product_inv.values())
        self.ids.item_count.text = f'{total} item{"s" if total != 1 else ""}'

        # ── ScrollView with product cards ──
        scroll = ScrollView(do_scroll_x=False)
        product_list = GridLayout(
            cols=1,
            size_hint_y=None,
            spacing=dp(6),
            padding=[dp(10), dp(6), dp(10), dp(6)],
        )
        product_list.bind(
            minimum_height=product_list.setter('height')
        )

        if product_inv:
            # Sort: base paints first, then hardeners, thinners, primers
            type_order = {'base_paint': 0, 'primer': 1, 'hardener': 2, 'thinner': 3}
            sorted_products = sorted(
                product_inv.items(),
                key=lambda x: (type_order.get(x[1]['type'], 9), x[0])
            )

            for name, info in sorted_products:
                card = self._build_product_card(
                    name, info, product_colors, hardener_map
                )
                product_list.add_widget(card)
        else:
            product_list.add_widget(self._build_empty_card())

        scroll.add_widget(product_list)
        content.add_widget(scroll)

        # ── "Check Shelves" button ──
        from kivy.uix.button import Button
        btn_box = BoxLayout(
            size_hint_y=None, height=dp(74),
            padding=[dp(10), dp(5), dp(10), dp(5)],
        )
        check_btn = Button(
            text='CHECK SHELVES',
            font_size='18sp',
            bold=True,
            size_hint=(1, 1),
            background_normal='',
            background_color=(0.00, 0.82, 0.73, 1),
            color=(0.02, 0.05, 0.08, 1),
        )
        check_btn.bind(on_release=lambda x: app.go_screen('shelf_map'))
        btn_box.add_widget(check_btn)
        content.add_widget(btn_box)
