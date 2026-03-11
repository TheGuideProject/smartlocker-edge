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


# ── Paint color name -> RGBA (expanded for marine paint names) ──
PAINT_COLORS = {
    # Basic colors
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
    # Marine / PPG compound colors
    'redbrown':       (0.71, 0.27, 0.16, 1),
    'red brown':      (0.71, 0.27, 0.16, 1),
    'reddish brown':  (0.71, 0.27, 0.16, 1),
    'light grey':     (0.69, 0.71, 0.74, 1),
    'light gray':     (0.69, 0.71, 0.74, 1),
    'dark grey':      (0.35, 0.37, 0.40, 1),
    'dark gray':      (0.35, 0.37, 0.40, 1),
    'rust':           (0.77, 0.36, 0.16, 1),
    'rust red':       (0.77, 0.36, 0.16, 1),
    'oxide red':      (0.71, 0.27, 0.16, 1),
    'navy':           (0.12, 0.20, 0.40, 1),
    'navy blue':      (0.12, 0.20, 0.40, 1),
    'mid grey':       (0.47, 0.49, 0.53, 1),
    'mid gray':       (0.47, 0.49, 0.53, 1),
    'off white':      (0.88, 0.86, 0.82, 1),
    'pale grey':      (0.78, 0.80, 0.83, 1),
    'pale gray':      (0.78, 0.80, 0.83, 1),
    'signal red':     (0.85, 0.18, 0.18, 1),
    'vermilion':      (0.89, 0.26, 0.20, 1),
    'teal':           (0.00, 0.82, 0.73, 1),
    'primer':         (0.72, 0.58, 0.42, 1),
    'tan':            (0.82, 0.71, 0.55, 1),
    'buff':           (0.85, 0.78, 0.62, 1),
    'oxide':          (0.71, 0.27, 0.16, 1),
    'charcoal':       (0.30, 0.31, 0.34, 1),
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


def _hex_to_rgba(hex_str):
    """Convert hex color string (#RRGGBB) to RGBA tuple."""
    if not hex_str or not hex_str.startswith('#'):
        return None
    try:
        h = hex_str.lstrip('#')
        if len(h) == 3:
            h = ''.join(c * 2 for c in h)
        if len(h) != 6:
            return None
        r = int(h[0:2], 16) / 255.0
        g = int(h[2:4], 16) / 255.0
        b = int(h[4:6], 16) / 255.0
        return (r, g, b, 1)
    except (ValueError, IndexError):
        return None


def _resolve_color(name):
    """Get RGBA for a paint color name or hex code.

    Matching strategy (same as cloud _color_name_to_hex):
    1. Exact match
    2. Strip product code numbers (e.g. "Redbrown 6179" -> "redbrown")
    3. First word match
    4. Substring match (both directions)
    """
    if not name:
        return None
    # Handle hex codes directly
    if name.startswith('#'):
        return _hex_to_rgba(name)

    key = name.strip().lower()
    words = key.split()

    # Strip numeric codes: "redbrown 6179" -> "redbrown"
    name_only = ' '.join(w for w in words if not w.isdigit())
    if not name_only:
        name_only = key

    # 1. Exact match
    if key in PAINT_COLORS:
        return PAINT_COLORS[key]

    # 2. Name without numbers
    if name_only in PAINT_COLORS:
        return PAINT_COLORS[name_only]

    # 3. First word match
    first = words[0] if words else ''
    if first in PAINT_COLORS:
        return PAINT_COLORS[first]

    # 4. Substring match (both directions)
    for color_key, rgba_val in PAINT_COLORS.items():
        if color_key in name_only or name_only in color_key:
            return rgba_val

    return None


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
        self._last_data_hash = None  # Cache to avoid rebuild when data unchanged

    def on_enter(self):
        """Start refresh loop on screen enter."""
        self._built = False
        self._last_data_hash = None  # Force rebuild on enter
        self._refresh_event = Clock.schedule_interval(self._refresh, 2.0)
        self._refresh(0)

    def on_leave(self):
        if self._refresh_event:
            self._refresh_event.cancel()
            self._refresh_event = None

    # ── Data helpers ──

    def _get_product_colors(self):
        """Extract product -> colors mapping.

        Priority: product.colors_json (DB, from color picker) > maintenance chart.
        Returns dict of {product_name: [{"name": str, "hex": str}, ...]}.
        """
        import json as _json
        app = App.get_running_app()
        colors = {}

        # Fallback: maintenance chart colors (string names)
        chart = getattr(app, 'maintenance_chart', None)
        if chart:
            for area in chart.get('areas', []):
                for layer in area.get('layers', []):
                    product = layer.get('product', '')
                    color = layer.get('color', '')
                    if product and color:
                        colors.setdefault(product, [])
                        if not any(c.get('name') == color for c in colors[product]):
                            colors[product].append({'name': color, 'hex': ''})

        # Override: DB-stored product colors (from cloud color picker)
        try:
            products = app.db.get_products()
            for p in products:
                raw = p.get("colors_json", "[]")
                if isinstance(raw, str):
                    try:
                        db_colors = _json.loads(raw)
                    except (ValueError, TypeError):
                        db_colors = []
                else:
                    db_colors = raw or []
                if db_colors:
                    colors[p["name"]] = db_colors
        except Exception:
            pass

        # Also include colors from vessel_stock
        try:
            vessel_stock = app.db.get_vessel_stock()
            for vs in vessel_stock:
                raw = vs.get("colors_json", "[]")
                if isinstance(raw, str):
                    try:
                        vs_colors = _json.loads(raw)
                    except (ValueError, TypeError):
                        vs_colors = []
                else:
                    vs_colors = raw or []
                if vs_colors and vs["product_name"] not in colors:
                    colors[vs["product_name"]] = vs_colors
        except Exception:
            pass

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
        """Build product inventory from occupied RFID slots."""
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

    def _get_vessel_stock(self):
        """Get vessel-level stock from cloud sync cache."""
        app = App.get_running_app()
        try:
            return app.db.get_vessel_stock()
        except Exception:
            return []

    def _build_merged_inventory(self):
        """Merge vessel stock (primary) with RFID slot data (enrichment).

        Returns dict of {product_name: {liters, initial_liters, fill_pct,
                                         cans, density, type, source}}.
        """
        vessel_stock = self._get_vessel_stock()
        rfid_inv = self._get_current_inventory()

        merged = {}

        # Primary source: cloud vessel stock
        for vs in vessel_stock:
            name = vs["product_name"]
            initial = vs.get("initial_liters", 0) or 0
            current = vs.get("current_liters", 0) or 0
            fill_pct = (current / initial * 100) if initial > 0 else (100 if current > 0 else 0)
            merged[name] = {
                'cans': 0,
                'liters': current,
                'initial_liters': initial,
                'fill_pct': fill_pct,
                'density': vs.get("density_g_per_ml", 1.0) or 1.0,
                'type': vs.get("product_type", "base_paint"),
                'source': 'cloud',
            }

        # Enrich with RFID data (add cans count)
        for name, rfid_data in rfid_inv.items():
            if name in merged:
                merged[name]['cans'] = rfid_data['cans']
            else:
                # Product on shelf but not in vessel stock (RFID-only)
                weight_g = rfid_data.get('weight_current_g', 0)
                full_g = rfid_data.get('weight_full_g', 0)
                density = rfid_data.get('density', 1.0) or 1.0
                liters = (weight_g / density) / 1000.0
                fill_pct = (weight_g / full_g * 100) if full_g > 0 else (100 if weight_g > 0 else 0)
                merged[name] = {
                    'cans': rfid_data['cans'],
                    'liters': round(liters, 1),
                    'initial_liters': 0,
                    'fill_pct': fill_pct,
                    'density': density,
                    'type': rfid_data.get('type', 'base_paint'),
                    'source': 'rfid',
                }

        return merged

    # ── UI building ──

    def _build_product_card(self, name, info, product_colors, hardener_map):
        """Build a single product card widget."""
        ptype = info.get('type', 'base_paint')
        accent = TYPE_ACCENTS.get(ptype, (0.50, 0.55, 0.64, 1))
        badge_text = TYPE_BADGES.get(ptype, 'Product')
        cans = info.get('cans', 0)
        liters = info.get('liters', 0)
        fill_pct = info.get('fill_pct', 0)

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

        # Can count (show only if > 0)
        count_text = f'x{cans}' if cans > 0 else ''
        count_label = Label(
            text=count_text,
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

            for cinfo in product_colors[name][:5]:  # max 5 colors
                # Support both dict format {"name": "X", "hex": "#Y"} and legacy string
                if isinstance(cinfo, dict):
                    cname = cinfo.get('name', '')
                    chex = cinfo.get('hex', '')
                    rgba = _hex_to_rgba(chex) if chex else _resolve_color(cname)
                else:
                    cname = str(cinfo)
                    rgba = _resolve_color(cname)

                if rgba:
                    dot = _dot_widget(rgba, size=12)
                    color_row.add_widget(dot)

                # Color name text
                display_name = cname.capitalize() if cname else ''
                if display_name:
                    ctxt = Label(
                        text=display_name,
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
            text='No products in inventory.\nAdd stock via cloud or place cans on slots.',
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

    def _compute_data_hash(self, merged_inv, slot_data=None):
        """Compute a fingerprint of current data to detect changes."""
        parts = []
        for name in sorted(merged_inv.keys()):
            info = merged_inv[name]
            parts.append(f"{name}:{info.get('liters',0):.1f}:{info.get('fill_pct',0):.0f}:{info.get('cans',0)}")
        if slot_data:
            for s in slot_data:
                parts.append(f"s:{s.status.value}")
        return "|".join(parts)

    def _refresh(self, dt):
        """Rebuild the product list only when data changes (prevents animation glitch)."""
        app = App.get_running_app()
        content = self.ids.content_area

        # Get merged data (vessel stock + RFID enrichment)
        merged_inv = self._build_merged_inventory()

        # Get slot data for hash (detect slot status changes too)
        try:
            slots = app.inventory.get_all_slots()
        except Exception:
            slots = []

        # Check if data changed since last refresh
        data_hash = self._compute_data_hash(merged_inv, slots)
        if self._last_data_hash == data_hash and self._built:
            return  # No change — skip rebuild to avoid animation glitch
        self._last_data_hash = data_hash
        self._built = True

        content.clear_widgets()

        product_colors = self._get_product_colors()
        hardener_map = self._get_hardener_map()

        # Update status bar: total liters
        total_liters = sum(v['liters'] for v in merged_inv.values())
        if total_liters > 0:
            self.ids.item_count.text = f'{total_liters:.0f} L total'
        else:
            total_items = sum(v.get('cans', 0) for v in merged_inv.values())
            self.ids.item_count.text = f'{total_items} item{"s" if total_items != 1 else ""}'

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

        if merged_inv:
            # Sort: base paints first, then hardeners, thinners, primers
            type_order = {'base_paint': 0, 'primer': 1, 'hardener': 2, 'thinner': 3}
            sorted_products = sorted(
                merged_inv.items(),
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
