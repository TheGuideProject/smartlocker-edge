"""
Inventory Screen - Product Stock Levels (v3.0 Redesign)

Card-based scrollable view of all products with progress bars,
type badges, color dots, and a CHECK SHELVES action button.
Built entirely in Python (no KV strings).
"""

import json as _json

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle, Rectangle, Ellipse
from kivy.metrics import dp

from ui.app import DS


# ---------------------------------------------------------------------------
#  Paint color name -> RGBA (expanded marine palette)
# ---------------------------------------------------------------------------
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

# Type accent colors (for badge + left bar)
TYPE_ACCENTS = {
    'base_paint': DS.PRIMARY,          # teal
    'hardener':   DS.ACCENT,           # amber
    'thinner':    (0.40, 0.65, 0.95, 1),  # blue
    'primer':     (0.70, 0.50, 0.90, 1),  # purple
}

# Type badge text
TYPE_BADGES = {
    'base_paint': 'BASE',
    'hardener':   'HARDENER',
    'thinner':    'THINNER',
    'primer':     'PRIMER',
}


# ---------------------------------------------------------------------------
#  Drawing helpers
# ---------------------------------------------------------------------------

def _card_bg(widget, color=DS.BG_CARD, radius=DS.RADIUS):
    """Rounded background that tracks widget pos/size."""
    with widget.canvas.before:
        Color(*color)
        rr = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[radius])
    widget.bind(
        pos=lambda w, p: setattr(rr, 'pos', p),
        size=lambda w, s: setattr(rr, 'size', s),
    )
    return rr


def _accent_bar(widget, color, width=4):
    """Colored vertical accent bar on left edge of a card."""
    with widget.canvas.after:
        Color(*color)
        bar = RoundedRectangle(
            pos=(widget.x + 2, widget.y + 4),
            size=(width, widget.height - 8),
            radius=[2],
        )

    def _upd(wid, *_):
        bar.pos = (wid.x + 2, wid.y + 4)
        bar.size = (width, wid.height - 8)

    widget.bind(pos=_upd, size=_upd)


def _progress_bar_draw(parent, fill_pct, bar_color, height=8):
    """Draw a rounded progress bar (track + fill) on a widget's canvas."""
    fill_pct = max(0.0, min(100.0, fill_pct))
    with parent.canvas.before:
        Color(0.20, 0.22, 0.28, 1)
        track = RoundedRectangle(pos=parent.pos, size=parent.size, radius=[4])
    with parent.canvas.after:
        Color(*bar_color)
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


def _dot_widget(rgba, size=12):
    """Small colored circle widget."""
    dot = Widget(size_hint=(None, None), size=(dp(size), dp(size)))
    with dot.canvas:
        Color(*rgba)
        ell = Ellipse(pos=dot.pos, size=dot.size)
    dot.bind(
        pos=lambda w, p: setattr(ell, 'pos', p),
        size=lambda w, s: setattr(ell, 'size', s),
    )
    return dot


def _make_label(text='', font_size=DS.FONT_BODY, color=DS.TEXT_PRIMARY,
                bold=False, halign='left', valign='middle',
                size_hint_y=None, height=None, size_hint_x=None,
                markup=False):
    lbl = Label(
        text=text,
        font_size=font_size,
        bold=bold,
        color=color,
        halign=halign,
        valign=valign,
        markup=markup,
    )
    if size_hint_y is not None:
        lbl.size_hint_y = size_hint_y
    if height is not None:
        lbl.height = dp(height)
        lbl.size_hint_y = None
    if size_hint_x is not None:
        lbl.size_hint_x = size_hint_x
    lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
    return lbl


def _hex_to_rgba(hex_str):
    """Convert #RRGGBB to RGBA tuple."""
    if not hex_str or not hex_str.startswith('#'):
        return None
    try:
        h = hex_str.lstrip('#')
        if len(h) == 3:
            h = ''.join(c * 2 for c in h)
        if len(h) != 6:
            return None
        return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0,
                int(h[4:6], 16) / 255.0, 1)
    except (ValueError, IndexError):
        return None


def _resolve_color(name):
    """Get RGBA for a paint color name or hex code."""
    if not name:
        return None
    if name.startswith('#'):
        return _hex_to_rgba(name)

    key = name.strip().lower()
    words = key.split()
    name_only = ' '.join(w for w in words if not w.isdigit()) or key

    # Exact
    if key in PAINT_COLORS:
        return PAINT_COLORS[key]
    # Without numbers
    if name_only in PAINT_COLORS:
        return PAINT_COLORS[name_only]
    # First word
    first = words[0] if words else ''
    if first in PAINT_COLORS:
        return PAINT_COLORS[first]
    # Substring both directions
    for ck, cv in PAINT_COLORS.items():
        if ck in name_only or name_only in ck:
            return cv
    return None


# ---------------------------------------------------------------------------
#  InventoryScreen
# ---------------------------------------------------------------------------

class InventoryScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._refresh_event = None
        self._last_data_hash = None
        self._built = False
        self._content_area = None
        self._count_label = None
        self._build_ui()

    # ── UI skeleton ───────────────────────────────────────

    def _build_ui(self):
        root = BoxLayout(orientation='vertical')

        with root.canvas.before:
            Color(*DS.BG_DARK)
            bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(
            pos=lambda w, p: setattr(bg, 'pos', p),
            size=lambda w, s: setattr(bg, 'size', s),
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
            acc = Rectangle(pos=status_bar.pos, size=(status_bar.width, 1))
        status_bar.bind(
            pos=lambda w, p: (setattr(sb_rect, 'pos', p), setattr(acc, 'pos', p)),
            size=lambda w, s: (setattr(sb_rect, 'size', s), setattr(acc, 'size', (s[0], 1))),
        )

        back_btn = Button(
            text='<', font_size='22sp', bold=True,
            size_hint=(None, None), size=(dp(50), dp(36)),
            background_normal='', background_color=DS.BG_CARD_HOVER,
            color=DS.TEXT_SECONDARY,
        )
        back_btn.bind(on_release=lambda x: App.get_running_app().go_back())
        status_bar.add_widget(back_btn)

        title = _make_label('INVENTORY', font_size='18sp', bold=True,
                            color=DS.TEXT_PRIMARY, halign='center')
        title.size_hint_x = 0.5
        status_bar.add_widget(title)

        count_lbl = _make_label('-- items', font_size=DS.FONT_SMALL,
                                color=DS.TEXT_MUTED, halign='right')
        count_lbl.size_hint_x = 0.3
        self._count_label = count_lbl
        status_bar.add_widget(count_lbl)

        root.add_widget(status_bar)

        # ---- DYNAMIC CONTENT AREA ----
        content = BoxLayout(orientation='vertical')
        self._content_area = content
        root.add_widget(content)

        self.add_widget(root)

    # ── Lifecycle ──────────────────────────────────────────

    def on_enter(self):
        self._built = False
        self._last_data_hash = None
        self._refresh_event = Clock.schedule_interval(self._refresh, 2.0)
        self._refresh(0)

    def on_leave(self):
        if self._refresh_event:
            self._refresh_event.cancel()
            self._refresh_event = None

    # ── Data helpers ───────────────────────────────────────

    def _get_product_colors(self):
        """Extract product -> colors mapping from DB and maintenance chart."""
        app = App.get_running_app()
        colors = {}

        # Maintenance chart colors (string names)
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

        # DB-stored product colors override
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

        # Vessel stock colors
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
        """From chart products, find which bases have hardeners."""
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
        product_inv = {}
        for slot in slots:
            if slot.status.value == 'occupied' and slot.current_tag_id:
                try:
                    product = app.db.get_product_for_tag(slot.current_tag_id)
                except Exception:
                    product = None
                if product:
                    name = product.get('name', 'Unknown')
                    entry = product_inv.setdefault(name, {
                        'cans': 0,
                        'weight_current_g': 0,
                        'weight_full_g': 0,
                        'density': product.get('density_g_per_ml', 1.0),
                        'type': product.get('product_type', 'base_paint'),
                    })
                    entry['cans'] += 1
                    entry['weight_current_g'] += slot.weight_current_g
                    placed = slot.weight_when_placed_g if slot.weight_when_placed_g > 0 else slot.weight_current_g
                    entry['weight_full_g'] += placed
        return product_inv

    def _get_vessel_stock(self):
        app = App.get_running_app()
        try:
            return app.db.get_vessel_stock()
        except Exception:
            return []

    def _build_merged_inventory(self):
        """Merge vessel stock (primary) with RFID slot data (enrichment)."""
        vessel_stock = self._get_vessel_stock()
        rfid_inv = self._get_current_inventory()
        merged = {}

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

        for name, rfid_data in rfid_inv.items():
            if name in merged:
                merged[name]['cans'] = rfid_data['cans']
            else:
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

    # ── Card builders ─────────────────────────────────────

    def _build_product_card(self, name, info, product_colors, hardener_map):
        """Build a single product card widget."""
        ptype = info.get('type', 'base_paint')
        accent = TYPE_ACCENTS.get(ptype, (0.50, 0.55, 0.64, 1))
        badge_text = TYPE_BADGES.get(ptype, 'PRODUCT')
        cans = info.get('cans', 0)
        liters = info.get('liters', 0)
        fill_pct = info.get('fill_pct', 0)

        has_colors = name in product_colors and product_colors[name]
        has_hardener = name in hardener_map

        # Calculate dynamic height
        card_height = 80
        if has_colors:
            card_height += 26
        if has_hardener:
            card_height += 22

        card = BoxLayout(
            orientation='vertical',
            size_hint_y=None, height=dp(card_height),
            padding=[dp(14), dp(8), dp(10), dp(8)],
            spacing=dp(3),
        )
        _card_bg(card, (0.11, 0.13, 0.17, 1), radius=10)
        _accent_bar(card, accent)

        # ── Row 1: Name + badge + cans + liters ──
        row1 = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(8))

        name_lbl = _make_label(name, DS.FONT_BODY, DS.TEXT_PRIMARY,
                               bold=True, size_hint_x=0.44)
        row1.add_widget(name_lbl)

        # Type badge with tinted background
        badge_container = BoxLayout(size_hint_x=0.22)
        badge_lbl = _make_label(badge_text, DS.FONT_SMALL, accent,
                                halign='center', bold=True)
        badge_container.add_widget(badge_lbl)
        row1.add_widget(badge_container)

        # Can count
        count_text = f'x{cans}' if cans > 0 else ''
        count_lbl = _make_label(count_text, DS.FONT_BODY, DS.TEXT_PRIMARY,
                                bold=True, halign='center', size_hint_x=0.12)
        row1.add_widget(count_lbl)

        # Liters
        liters_lbl = _make_label(f'{liters:.1f} L', DS.FONT_SMALL,
                                 DS.TEXT_MUTED, halign='right', size_hint_x=0.22)
        row1.add_widget(liters_lbl)

        card.add_widget(row1)

        # ── Row 2: Progress bar + percentage ──
        bar_row = BoxLayout(
            size_hint_y=None, height=dp(16),
            spacing=dp(8), padding=[dp(4), dp(2), dp(4), dp(2)],
        )

        bar_widget = Widget(size_hint_x=0.78, size_hint_y=None, height=dp(8))
        if fill_pct > 50:
            bar_color = DS.PRIMARY      # teal
        elif fill_pct > 25:
            bar_color = DS.WARNING      # yellow
        else:
            bar_color = DS.DANGER       # red
        _progress_bar_draw(bar_widget, fill_pct, bar_color)
        bar_row.add_widget(bar_widget)

        pct_lbl = _make_label(f'{fill_pct:.0f}%', DS.FONT_SMALL,
                              DS.TEXT_MUTED, halign='right', size_hint_x=0.22)
        bar_row.add_widget(pct_lbl)
        card.add_widget(bar_row)

        # ── Row 3: Color dots (if any) ──
        if has_colors:
            color_row = BoxLayout(
                size_hint_y=None, height=dp(22),
                spacing=dp(6), padding=[dp(2), 0, 0, 0],
            )

            clabel = Label(
                text='Colors:', font_size=DS.FONT_SMALL,
                color=DS.TEXT_MUTED,
                size_hint=(None, 1), width=dp(48),
                halign='left', valign='middle',
            )
            clabel.bind(size=lambda w, s: setattr(w, 'text_size', s))
            color_row.add_widget(clabel)

            for cinfo in product_colors[name][:5]:
                if isinstance(cinfo, dict):
                    cname = cinfo.get('name', '')
                    chex = cinfo.get('hex', '')
                    rgba = _hex_to_rgba(chex) if chex else _resolve_color(cname)
                else:
                    cname = str(cinfo)
                    rgba = _resolve_color(cname)

                if rgba:
                    color_row.add_widget(_dot_widget(rgba, size=12))

                display = cname.capitalize() if cname else ''
                if display:
                    ctxt = Label(
                        text=display, font_size=DS.FONT_SMALL,
                        color=DS.TEXT_SECONDARY,
                        size_hint=(None, 1), halign='left', valign='middle',
                    )
                    ctxt.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0] + 4))
                    ctxt.bind(size=lambda w, s: setattr(w, 'text_size', s))
                    color_row.add_widget(ctxt)

            color_row.add_widget(Widget())  # spacer
            card.add_widget(color_row)

        # ── Row 4: Hardener info ──
        if has_hardener:
            hinfo = hardener_map[name]
            ratio_text = (f'2-component  |  Mix ratio '
                          f'{hinfo.get("base_ratio", 0)}:{hinfo.get("hardener_ratio", 0)}')
            hlabel = _make_label(ratio_text, DS.FONT_SMALL,
                                 (*DS.ACCENT[:3], 0.85), size_hint_y=None, height=18)
            card.add_widget(hlabel)

        return card

    def _build_empty_card(self):
        card = BoxLayout(
            orientation='vertical',
            size_hint_y=None, height=dp(80),
            padding=[dp(20), dp(15)],
        )
        _card_bg(card, (0.11, 0.13, 0.17, 1), radius=10)

        lbl = _make_label(
            'No products in inventory.\nAdd stock via cloud or place cans on slots.',
            DS.FONT_BODY, DS.TEXT_MUTED, halign='center', valign='middle',
        )
        card.add_widget(lbl)
        return card

    # ── Refresh ────────────────────────────────────────────

    def _compute_hash(self, merged, slots=None):
        parts = []
        for name in sorted(merged.keys()):
            i = merged[name]
            parts.append(f"{name}:{i.get('liters',0):.1f}:{i.get('fill_pct',0):.0f}:{i.get('cans',0)}")
        if slots:
            for s in slots:
                parts.append(f"s:{s.status.value}")
        return "|".join(parts)

    def _refresh(self, dt):
        """Rebuild the product list only when data changes."""
        app = App.get_running_app()
        content = self._content_area

        merged = self._build_merged_inventory()

        try:
            slots = app.inventory.get_all_slots()
        except Exception:
            slots = []

        data_hash = self._compute_hash(merged, slots)
        if self._last_data_hash == data_hash and self._built:
            return
        self._last_data_hash = data_hash
        self._built = True

        content.clear_widgets()

        product_colors = self._get_product_colors()
        hardener_map = self._get_hardener_map()

        # Update counter in status bar
        total_liters = sum(v['liters'] for v in merged.values())
        if total_liters > 0:
            self._count_label.text = f'{total_liters:.0f} L total'
        else:
            total_items = sum(v.get('cans', 0) for v in merged.values())
            self._count_label.text = f'{total_items} item{"s" if total_items != 1 else ""}'

        # ── ScrollView with product cards ──
        scroll = ScrollView(do_scroll_x=False)
        product_list = GridLayout(
            cols=1,
            size_hint_y=None,
            spacing=dp(6),
            padding=[dp(DS.PAD_SCREEN), dp(6), dp(DS.PAD_SCREEN), dp(6)],
        )
        product_list.bind(minimum_height=product_list.setter('height'))

        if merged:
            type_order = {'base_paint': 0, 'primer': 1, 'hardener': 2, 'thinner': 3}
            sorted_products = sorted(
                merged.items(),
                key=lambda x: (type_order.get(x[1]['type'], 9), x[0]),
            )
            for name, info in sorted_products:
                card = self._build_product_card(name, info, product_colors, hardener_map)
                product_list.add_widget(card)
        else:
            product_list.add_widget(self._build_empty_card())

        scroll.add_widget(product_list)
        content.add_widget(scroll)

        # ── CHECK SHELVES button ──
        btn_box = BoxLayout(
            size_hint_y=None, height=dp(74),
            padding=[dp(DS.PAD_SCREEN), dp(5), dp(DS.PAD_SCREEN), dp(5)],
        )
        check_btn = Button(
            text='CHECK SHELVES',
            font_size='18sp',
            bold=True,
            size_hint=(1, 1),
            background_normal='',
            background_color=(0, 0, 0, 0),
            color=(0.02, 0.05, 0.08, 1),
        )
        # Rounded teal background
        with check_btn.canvas.before:
            Color(*DS.PRIMARY)
            rr = RoundedRectangle(pos=check_btn.pos, size=check_btn.size,
                                  radius=[DS.RADIUS])
        check_btn.bind(
            pos=lambda w, p: setattr(rr, 'pos', p),
            size=lambda w, s: setattr(rr, 'size', s),
        )
        check_btn.bind(on_release=lambda x: app.go_screen('shelf_map'))
        btn_box.add_widget(check_btn)
        content.add_widget(btn_box)
