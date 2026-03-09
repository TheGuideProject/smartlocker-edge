"""
Chart Viewer Screen — Maintenance Chart v3 (Clarity Focus)

Completely redesigned for maximum readability on 4.3" 800×480 touchscreen:
- Large, high-contrast WHITE text on dark cards
- Clear area headers with colored accent bars
- Simple text-based layer listing (no invisible pills)
- Clean product rows with readable details
- Color dots for visual paint color reference
- Glove-friendly spacing, optimized for marine use
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.lang import Builder
from kivy.app import App
from kivy.graphics import Color, RoundedRectangle, Ellipse
from kivy.metrics import dp


# ── Accent colors cycled per area ──
AREA_ACCENTS = [
    (0.00, 0.82, 0.73, 1),   # Teal
    (0.98, 0.65, 0.25, 1),   # Amber
    (0.40, 0.65, 0.95, 1),   # Blue
    (0.93, 0.45, 0.42, 1),   # Coral
    (0.70, 0.50, 0.90, 1),   # Purple
    (0.30, 0.85, 0.55, 1),   # Green
    (0.90, 0.60, 0.75, 1),   # Rose
]

# ── Paint color name → RGBA ──
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


# ── KV Layout ──
Builder.load_string('''
<ChartViewerScreen>:
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: 0.08, 0.09, 0.12, 1
            Rectangle:
                pos: self.pos
                size: self.size

        StatusBar:
            BackButton:
                on_release: app.go_back()
            Label:
                text: '\\U0001F6A2  MAINTENANCE CHART'
                font_size: '16sp'
                bold: True
                color: 0.96, 0.97, 0.98, 1
                size_hint_x: 0.55
                halign: 'center'
                text_size: self.size
                valign: 'middle'
            Label:
                id: vessel_label
                text: ''
                font_size: '11sp'
                color: 0.50, 0.55, 0.62, 1
                size_hint_x: 0.25
                halign: 'right'
                text_size: self.size
                valign: 'middle'

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


def _dot_widget(color_rgba, size=16):
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
    # Try exact match first
    if key in PAINT_COLORS:
        return PAINT_COLORS[key]
    # Try first word (e.g. "RED 6188" → "red")
    first_word = key.split()[0] if key else ''
    return PAINT_COLORS.get(first_word)


def _clean_text(text):
    """Fix common encoding artifacts from PDF parsing."""
    if not text:
        return text
    return (text
            .replace('Ãƒâ€šÃ‚', '')
            .replace('ÃƒÂ', 'µ')
            .replace('Ã‚µ', 'µ')
            .replace('Â', '')
            .replace('Ãƒ', '')
            .replace('Ã', '')
            .replace('Â', '')
            .replace('\u00c3\u0082\u00c2\u00b5', 'µ')
            .replace('\u00c2\u00b5', 'µ')
            .strip())


# ── MAIN SCREEN ──

class ChartViewerScreen(Screen):

    def on_enter(self):
        content = self.ids.content_area
        content.clear_widgets()

        app = App.get_running_app()
        app.maintenance_chart = app.db.get_maintenance_chart()
        chart = app.maintenance_chart

        if not chart:
            self._empty_state(content)
            return

        vessel = chart.get('vessel_name', 'Unknown Vessel')
        imo = chart.get('imo_number', '')
        self.ids.vessel_label.text = f'IMO {imo}' if imo else ''

        areas = chart.get('areas', [])
        products = chart.get('products', [])
        markings = chart.get('marking_colors', [])

        # ── Scrollable content ──
        scroll = ScrollView(
            size_hint=(1, 1),
            do_scroll_x=False,
            bar_width=dp(4),
            bar_color=(0.00, 0.82, 0.73, 0.5),
            bar_inactive_color=(0.20, 0.22, 0.28, 0.3),
            scroll_type=['bars', 'content'],
        )

        col = GridLayout(
            cols=1, spacing=dp(8), size_hint_y=None,
            padding=[dp(8), dp(6), dp(8), dp(20)],
        )
        col.bind(minimum_height=col.setter('height'))

        # ▸ Vessel header
        col.add_widget(self._vessel_header(
            vessel, imo, len(areas), len(products)))

        # ▸ Area cards
        for i, area in enumerate(areas):
            accent = AREA_ACCENTS[i % len(AREA_ACCENTS)]
            col.add_widget(self._area_card(area, accent))

        # ▸ Products
        if products:
            col.add_widget(self._products_section(products))

        # ▸ Marking colors
        if markings:
            col.add_widget(self._markings_section(markings))

        col.add_widget(Widget(size_hint_y=None, height=dp(12)))
        scroll.add_widget(col)
        content.add_widget(scroll)

    # ════════════════════════════════════════════════
    # VESSEL HEADER
    # ════════════════════════════════════════════════
    def _vessel_header(self, name, imo, n_areas, n_products):
        card = BoxLayout(
            orientation='vertical', size_hint_y=None, height=dp(68),
            padding=[dp(16), dp(10), dp(16), dp(8)], spacing=dp(4),
        )
        _bg(card, (0.10, 0.13, 0.18, 1), radius=12)

        # Vessel name — BIG WHITE
        card.add_widget(Label(
            text=f'\U0001F6A2  {name}',
            font_size='20sp', bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None, height=dp(30),
            halign='left', valign='middle',
            text_size=(dp(700), dp(30)),
        ))

        # Stats line
        stats = f'IMO {imo}   \u2022   {n_areas} areas   \u2022   {n_products} products'
        card.add_widget(Label(
            text=stats,
            font_size='13sp',
            color=(0.55, 0.62, 0.72, 1),
            size_hint_y=None, height=dp(20),
            halign='left', valign='middle',
            text_size=(dp(700), dp(20)),
        ))

        return card

    # ════════════════════════════════════════════════
    # AREA CARD
    # ════════════════════════════════════════════════
    def _area_card(self, area, accent):
        name = area.get('name', 'Unknown Area')
        layers = area.get('layers', [])
        notes = area.get('notes', '')

        # Dynamic height
        header_h = dp(34)
        notes_h = dp(20) if notes else 0
        layers_h = dp(32) * len(layers)
        total = header_h + notes_h + layers_h + dp(14)

        card = BoxLayout(
            orientation='vertical', size_hint_y=None, height=total,
            padding=[dp(14), dp(6), dp(10), dp(6)], spacing=dp(2),
        )
        _bg(card, (0.11, 0.13, 0.17, 1), radius=10)
        _bar(card, accent, w=dp(4))

        # ── Area name — LARGE, COLORED, READABLE ──
        card.add_widget(Label(
            text=name,
            font_size='15sp', bold=True,
            color=accent,
            size_hint_y=None, height=dp(26),
            halign='left', valign='middle',
            text_size=(dp(700), dp(26)),
            padding=[dp(10), 0],
        ))

        # ── Notes (DFT info) ──
        if notes:
            card.add_widget(Label(
                text=_clean_text(notes),
                font_size='11sp',
                color=(0.50, 0.54, 0.62, 1),
                size_hint_y=None, height=dp(16),
                halign='left', valign='middle',
                text_size=(dp(700), dp(16)),
                padding=[dp(10), 0],
                shorten=True, shorten_from='right',
            ))

        # ── Layer rows ──
        for layer in layers:
            card.add_widget(self._layer_row(layer, accent))

        return card

    def _layer_row(self, layer, accent):
        """Single layer: number circle + product name + color dot/name."""
        num = layer.get('layer_number', '?')
        product = layer.get('product', 'Unknown')
        color_name = layer.get('color', '')

        row = BoxLayout(
            size_hint_y=None, height=dp(28),
            spacing=dp(8), padding=[dp(10), dp(2), dp(6), dp(2)],
        )

        # ▸ Layer number circle
        circle_size = dp(22)
        muted = (accent[0] * 0.65, accent[1] * 0.65, accent[2] * 0.65, 1)
        num_container = Widget(
            size_hint=(None, None), size=(circle_size, circle_size),
        )
        with num_container.canvas:
            Color(*muted)
            circle_ell = Ellipse(pos=num_container.pos,
                                 size=num_container.size)
        num_container.bind(
            pos=lambda w, p: setattr(circle_ell, 'pos', p),
            size=lambda w, s: setattr(circle_ell, 'size', s),
        )
        num_label = Label(
            text=str(num), font_size='11sp', bold=True,
            color=(1, 1, 1, 1),
            size_hint=(None, None), size=(circle_size, circle_size),
            halign='center', valign='middle',
        )
        num_label.text_size = (circle_size, circle_size)
        num_container.add_widget(num_label)
        num_container.bind(
            pos=lambda w, p: setattr(num_label, 'pos', p))
        row.add_widget(num_container)

        # ▸ Product name — BIG, WHITE, BOLD
        row.add_widget(Label(
            text=product,
            font_size='14sp', bold=True,
            color=(0.93, 0.95, 0.97, 1),
            halign='left', valign='middle',
            text_size=(dp(420), dp(28)),
            shorten=True, shorten_from='right',
        ))

        # ▸ Color indicator (dot + text)
        if color_name:
            paint_rgba = _resolve_color(color_name)

            color_box = BoxLayout(
                size_hint=(None, None),
                size=(dp(130), dp(24)),
                spacing=dp(5),
                padding=[dp(2), dp(3), 0, dp(3)],
            )

            if paint_rgba:
                color_box.add_widget(_dot_widget(paint_rgba, size=14))

            color_box.add_widget(Label(
                text=color_name,
                font_size='12sp',
                color=(0.62, 0.66, 0.74, 1),
                halign='left', valign='middle',
                text_size=(dp(105), dp(20)),
                shorten=True, shorten_from='right',
            ))
            row.add_widget(color_box)

        return row

    # ════════════════════════════════════════════════
    # PRODUCTS SECTION
    # ════════════════════════════════════════════════
    def _products_section(self, products):
        row_h = dp(48)
        header_h = dp(34)
        total = header_h + (row_h + dp(4)) * len(products) + dp(8)

        section = BoxLayout(
            orientation='vertical', size_hint_y=None, height=total,
            spacing=dp(4),
        )

        # Section header
        section.add_widget(Label(
            text=f'\U0001F3A8  PRODUCTS  ({len(products)})',
            font_size='15sp', bold=True,
            color=(0.00, 0.82, 0.73, 1),
            size_hint_y=None, height=dp(28),
            halign='left', valign='middle',
            text_size=(dp(700), dp(28)),
            padding=[dp(4), 0],
        ))

        for p in products:
            section.add_widget(self._product_row(p))

        return section

    def _product_row(self, product):
        """Single product info row: name + details underneath."""
        name = product.get('name', '?')
        thinner = product.get('thinner', '')
        components = product.get('components', 1)
        base_r = product.get('base_ratio', '')
        hard_r = product.get('hardener_ratio', '')
        coverage = product.get('coverage_m2_per_liter', '')

        card = BoxLayout(
            orientation='vertical', size_hint_y=None, height=dp(44),
            padding=[dp(14), dp(6), dp(10), dp(4)], spacing=dp(2),
        )
        _bg(card, (0.11, 0.13, 0.17, 1), radius=8)

        # Product type color bar
        lower = name.lower()
        if 'thinner' in lower:
            bar_color = (0.30, 0.52, 0.80, 1)
        elif 'hardener' in lower or 'hrd' in lower:
            bar_color = (0.90, 0.60, 0.20, 1)
        else:
            bar_color = (0.00, 0.72, 0.64, 1)
        _bar(card, bar_color, w=dp(3))

        # Product name — WHITE BOLD
        card.add_widget(Label(
            text=name,
            font_size='14sp', bold=True,
            color=(0.93, 0.95, 0.97, 1),
            size_hint_y=None, height=dp(20),
            halign='left', valign='middle',
            text_size=(dp(700), dp(20)),
            padding=[dp(6), 0],
        ))

        # Details line (mix ratio, coverage, thinner)
        parts = []
        if components > 1 and base_r:
            parts.append(f'Mix {base_r}:{hard_r}')
        if coverage:
            parts.append(f'{coverage} m\u00b2/L')
        if thinner:
            parts.append(f'Thinner: {thinner}')

        if parts:
            card.add_widget(Label(
                text='   \u2022   '.join(parts),
                font_size='11sp',
                color=(0.50, 0.55, 0.64, 1),
                size_hint_y=None, height=dp(14),
                halign='left', valign='middle',
                text_size=(dp(700), dp(14)),
                padding=[dp(6), 0],
                shorten=True, shorten_from='right',
            ))
        else:
            card.add_widget(Widget(size_hint_y=None, height=dp(4)))

        return card

    # ════════════════════════════════════════════════
    # MARKING COLORS SECTION
    # ════════════════════════════════════════════════
    def _markings_section(self, markings):
        header_h = dp(34)
        row_h = dp(36)
        total = header_h + (row_h + dp(4)) * len(markings) + dp(8)

        section = BoxLayout(
            orientation='vertical', size_hint_y=None, height=total,
            spacing=dp(4),
        )

        section.add_widget(Label(
            text=f'\U0001F3AF  MARKING COLORS  ({len(markings)})',
            font_size='15sp', bold=True,
            color=(0.98, 0.76, 0.22, 1),
            size_hint_y=None, height=dp(28),
            halign='left', valign='middle',
            text_size=(dp(700), dp(28)),
            padding=[dp(4), 0],
        ))

        for mc in markings:
            purpose = mc.get('purpose', '?')
            mc_color_name = mc.get('color', '?')
            paint_rgba = _resolve_color(mc_color_name)

            row = BoxLayout(
                size_hint_y=None, height=dp(32),
                padding=[dp(14), dp(4), dp(10), dp(4)],
                spacing=dp(10),
            )
            _bg(row, (0.11, 0.13, 0.17, 1), radius=8)

            # Color dot
            if paint_rgba:
                row.add_widget(_dot_widget(paint_rgba, size=18))
            else:
                row.add_widget(
                    Widget(size_hint=(None, None), size=(dp(18), dp(18))))

            # Purpose — WHITE BOLD
            row.add_widget(Label(
                text=purpose,
                font_size='13sp', bold=True,
                color=(0.93, 0.95, 0.97, 1),
                halign='left', valign='middle',
                text_size=(dp(350), dp(28)),
            ))

            # Color name — muted right side
            row.add_widget(Label(
                text=mc_color_name,
                font_size='12sp',
                color=(0.58, 0.62, 0.70, 1),
                size_hint_x=None, width=dp(160),
                halign='right', valign='middle',
                text_size=(dp(160), dp(28)),
            ))

            section.add_widget(row)

        return section

    # ════════════════════════════════════════════════
    # EMPTY STATE
    # ════════════════════════════════════════════════
    def _empty_state(self, content):
        content.add_widget(Widget(size_hint_y=0.2))

        card = BoxLayout(
            orientation='vertical',
            size_hint=(0.8, None), height=dp(160),
            pos_hint={'center_x': 0.5},
            padding=[dp(24), dp(20)], spacing=dp(10),
        )
        _bg(card, (0.11, 0.13, 0.17, 1), radius=14)

        card.add_widget(Label(
            text='\U0001F4CB',
            font_size='40sp',
            size_hint_y=None, height=dp(48),
            halign='center',
        ))
        card.add_widget(Label(
            text='No Chart Available',
            font_size='20sp', bold=True,
            color=(0.60, 0.63, 0.70, 1),
            size_hint_y=None, height=dp(28),
            halign='center', text_size=(dp(400), None),
        ))
        card.add_widget(Label(
            text='Pair with cloud and upload\na maintenance chart.',
            font_size='14sp',
            color=(0.42, 0.46, 0.54, 1),
            size_hint_y=None, height=dp(40),
            halign='center', text_size=(dp(400), None),
        ))

        content.add_widget(card)
        content.add_widget(Widget(size_hint_y=1))
