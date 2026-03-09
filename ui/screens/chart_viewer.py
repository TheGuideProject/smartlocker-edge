"""
Chart Viewer Screen - Maintenance Chart (2026 Modern Redesign)

A premium dark-themed chart viewer for vessel maintenance data:
- Gradient vessel header with ship emoji and IMO badge
- Color-coded area cards with accent bars and layer chips
- Product summary with pill badges and type-coded colors
- Marking color swatches with circular previews
- Smooth scrolling, 48dp+ touch targets, glove-friendly

Design: "Maritime Tech 2026" - dark carbon base, gradient accents,
rounded cards with colored left bars, chip/pill badges for layers
and products, optimized for 800x480 touchscreen.
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.lang import Builder
from kivy.app import App
from kivy.graphics import (
    Color, RoundedRectangle, Rectangle, Ellipse, Line,
)
from kivy.metrics import dp, sp


# ============================================================
# ACCENT PALETTE - cycled per area card
# ============================================================
AREA_ACCENTS = [
    (0.00, 0.82, 0.73, 1),   # Teal
    (0.98, 0.65, 0.25, 1),   # Amber
    (0.33, 0.58, 0.85, 1),   # Blue
    (0.93, 0.45, 0.42, 1),   # Coral
    (0.62, 0.42, 0.85, 1),   # Purple
    (0.20, 0.82, 0.48, 1),   # Green
    (0.85, 0.55, 0.70, 1),   # Rose
]

# Product-type color mapping
PRODUCT_TYPE_COLORS = {
    'base':     (0.00, 0.72, 0.64, 1),
    'hardener': (0.88, 0.58, 0.18, 1),
    'thinner':  (0.28, 0.50, 0.78, 1),
    'default':  (0.45, 0.48, 0.56, 1),
}

# Named color map for paint colors -> RGBA (common marine paint colors)
PAINT_COLOR_MAP = {
    'red':       (0.85, 0.22, 0.22, 1),
    'dark red':  (0.65, 0.12, 0.12, 1),
    'brown':     (0.55, 0.35, 0.18, 1),
    'green':     (0.18, 0.65, 0.30, 1),
    'dark green':(0.10, 0.42, 0.18, 1),
    'blue':      (0.20, 0.45, 0.82, 1),
    'dark blue': (0.12, 0.25, 0.55, 1),
    'white':     (0.90, 0.90, 0.92, 1),
    'black':     (0.15, 0.15, 0.18, 1),
    'grey':      (0.50, 0.52, 0.55, 1),
    'gray':      (0.50, 0.52, 0.55, 1),
    'yellow':    (0.92, 0.82, 0.20, 1),
    'orange':    (0.92, 0.55, 0.15, 1),
    'pink':      (0.88, 0.45, 0.55, 1),
    'maroon':    (0.50, 0.12, 0.15, 1),
    'copper':    (0.72, 0.45, 0.20, 1),
    'beige':     (0.82, 0.76, 0.62, 1),
    'cream':     (0.90, 0.87, 0.75, 1),
    'silver':    (0.70, 0.72, 0.75, 1),
    'aluminum':  (0.65, 0.68, 0.72, 1),
}


# ============================================================
# KV LAYOUT (static structure: status bar + content area)
# ============================================================
Builder.load_string('''
<ChartViewerScreen>:
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
                color: 0.38, 0.42, 0.50, 1
                size_hint_x: 0.25
                halign: 'right'
                text_size: self.size
                valign: 'middle'

        # ---- SCROLLABLE CONTENT ----
        BoxLayout:
            id: content_area
            orientation: 'vertical'
            padding: [0, 0, 0, 0]
''')


# ============================================================
# DRAWING HELPERS
# ============================================================

def _draw_rounded_rect(widget, color, radius=12):
    """Add a rounded-rect background that tracks widget pos/size."""
    with widget.canvas.before:
        c = Color(*color)
        rr = RoundedRectangle(pos=widget.pos, size=widget.size,
                              radius=[radius])
    widget.bind(
        pos=lambda w, p: setattr(rr, 'pos', p),
        size=lambda w, s: setattr(rr, 'size', s),
    )
    return rr


def _draw_gradient_rect(widget, color_top, color_bottom, radius=12):
    """Fake two-tone gradient: top half one color, bottom half another,
    both as rounded rects with overlap to blend visually."""
    with widget.canvas.before:
        # Bottom layer (full card)
        Color(*color_bottom)
        rr_bot = RoundedRectangle(pos=widget.pos, size=widget.size,
                                  radius=[radius])
        # Top overlay (upper ~60%)
        Color(*color_top)
        rr_top = RoundedRectangle(
            pos=(widget.x, widget.y + widget.height * 0.35),
            size=(widget.width, widget.height * 0.65),
            radius=[radius, radius, 0, 0],
        )

    def _update_bot(w, *_):
        rr_bot.pos = w.pos
        rr_bot.size = w.size

    def _update_top(w, *_):
        rr_top.pos = (w.x, w.y + w.height * 0.35)
        rr_top.size = (w.width, w.height * 0.65)

    widget.bind(pos=_update_bot, size=_update_bot)
    widget.bind(pos=_update_top, size=_update_top)


def _draw_accent_bar(widget, color, width=4, radius=6):
    """Draw a colored vertical bar on the left edge of the widget."""
    with widget.canvas.after:
        Color(*color)
        bar = RoundedRectangle(
            pos=(widget.x, widget.y + 4),
            size=(width, widget.height - 8),
            radius=[radius],
        )

    def _update(w, *_):
        bar.pos = (w.x, w.y + 4)
        bar.size = (width, w.height - 8)

    widget.bind(pos=_update, size=_update)


def _draw_circle(widget, color, cx, cy, diameter):
    """Draw a filled circle at absolute coordinates on widget's canvas."""
    with widget.canvas.after:
        Color(*color)
        ell = Ellipse(
            pos=(cx - diameter / 2, cy - diameter / 2),
            size=(diameter, diameter),
        )
    return ell


def _draw_divider(widget, color=(0.18, 0.20, 0.26, 1), pad_x=12):
    """Add a subtle horizontal divider at the bottom of a widget."""
    with widget.canvas.after:
        Color(*color)
        line_rect = Rectangle(
            pos=(widget.x + pad_x, widget.y),
            size=(widget.width - 2 * pad_x, 1),
        )

    def _update(w, *_):
        line_rect.pos = (w.x + pad_x, w.y)
        line_rect.size = (w.width - 2 * pad_x, 1)

    widget.bind(pos=_update, size=_update)


def _color_for_name(name):
    """Resolve a paint color name to an RGBA tuple."""
    if not name:
        return PRODUCT_TYPE_COLORS['default']
    key = name.strip().lower()
    return PAINT_COLOR_MAP.get(key, PRODUCT_TYPE_COLORS['default'])


def _text_color_for_bg(bg_color):
    """Return white or dark text depending on background luminance."""
    r, g, b = bg_color[0], bg_color[1], bg_color[2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    if lum > 0.55:
        return (0.08, 0.09, 0.12, 1)
    return (0.96, 0.97, 0.98, 1)


# ============================================================
# CUSTOM WIDGETS
# ============================================================

class PillBadge(Label):
    """A rounded pill-shaped label with colored background."""

    def __init__(self, text='', bg_color=(0.15, 0.18, 0.24, 1),
                 text_color=None, font_size='12sp', height=26,
                 padding_x=14, **kwargs):
        if text_color is None:
            text_color = _text_color_for_bg(bg_color)
        super().__init__(
            text=text,
            font_size=font_size,
            bold=True,
            color=text_color,
            size_hint=(None, None),
            height=height,
            halign='center',
            valign='middle',
            padding=[padding_x, 2],
            **kwargs,
        )
        self.bg_color = bg_color
        self.bind(texture_size=self._update_width)
        self.bind(size=self._draw, pos=self._draw)

    def _update_width(self, *_):
        self.width = self.texture_size[0] + 28
        self.text_size = (self.width, self.height)

    def _draw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.bg_color)
            RoundedRectangle(pos=self.pos, size=self.size,
                             radius=[self.height / 2])


class CircleBadge(Widget):
    """Small numbered circle badge (for layer numbers)."""

    def __init__(self, number=1, color=(0.00, 0.82, 0.73, 1),
                 diameter=24, **kwargs):
        super().__init__(
            size_hint=(None, None),
            size=(diameter, diameter),
            **kwargs,
        )
        self.badge_color = color
        self.number = number
        self.diameter = diameter
        self.bind(pos=self._draw, size=self._draw)

        # Number label
        self._label = Label(
            text=str(number),
            font_size='11sp',
            bold=True,
            color=_text_color_for_bg(color),
            size_hint=(None, None),
            size=(diameter, diameter),
            halign='center',
            valign='middle',
        )
        self._label.text_size = (diameter, diameter)
        self.add_widget(self._label)

    def _draw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.badge_color)
            Ellipse(pos=self.pos, size=self.size)
        self._label.pos = self.pos
        self._label.size = self.size


class ColorSwatch(BoxLayout):
    """Circular color swatch with label underneath."""

    def __init__(self, color_name='', swatch_color=(0.5, 0.5, 0.5, 1),
                 **kwargs):
        super().__init__(
            orientation='vertical',
            size_hint=(None, None),
            size=(72, 64),
            spacing=4,
            **kwargs,
        )
        self.swatch_color = swatch_color

        # Circle swatch
        self._circle_widget = Widget(size_hint=(None, None), size=(36, 36))
        self._circle_widget.bind(pos=self._draw_circle, size=self._draw_circle)
        self.add_widget(Widget(size_hint_y=None, height=2))  # top spacer

        circle_row = BoxLayout(size_hint_y=None, height=36)
        circle_row.add_widget(Widget())  # left spacer
        circle_row.add_widget(self._circle_widget)
        circle_row.add_widget(Widget())  # right spacer
        self.add_widget(circle_row)

        # Name label
        self.add_widget(Label(
            text=color_name,
            font_size='10sp',
            color=(0.70, 0.73, 0.78, 1),
            size_hint_y=None, height=18,
            halign='center',
            text_size=(70, None),
            shorten=True,
            shorten_from='right',
        ))

    def _draw_circle(self, *_):
        w = self._circle_widget
        self._circle_widget.canvas.before.clear()
        with w.canvas.before:
            # Outer ring (subtle)
            Color(*(c * 0.6 if i < 3 else c
                     for i, c in enumerate(self.swatch_color)))
            Ellipse(pos=(w.x - 2, w.y - 2),
                    size=(w.width + 4, w.height + 4))
            # Inner fill
            Color(*self.swatch_color)
            Ellipse(pos=w.pos, size=w.size)


# ============================================================
# MAIN SCREEN
# ============================================================

class ChartViewerScreen(Screen):

    def on_enter(self):
        """Build the entire chart view from local data."""
        content = self.ids.content_area
        content.clear_widgets()

        app = App.get_running_app()

        # Reload from DB
        app.maintenance_chart = app.db.get_maintenance_chart()
        chart = app.maintenance_chart

        if not chart:
            self._build_no_chart(content)
            return

        vessel_name = chart.get('vessel_name', 'Unknown Vessel')
        imo = chart.get('imo_number', '')
        self.ids.vessel_label.text = f'IMO {imo}' if imo else ''

        areas = chart.get('areas', [])
        products = chart.get('products', [])
        markings = chart.get('marking_colors', [])

        # --- Main scroll view ---
        scroll = ScrollView(
            size_hint=(1, 1),
            do_scroll_x=False,
            bar_width=dp(3),
            bar_color=(0.00, 0.82, 0.73, 0.4),
            bar_inactive_color=(0.20, 0.22, 0.28, 0.3),
            scroll_type=['bars', 'content'],
        )

        main_grid = GridLayout(
            cols=1,
            spacing=dp(10),
            size_hint_y=None,
            padding=[dp(10), dp(8), dp(10), dp(16)],
        )
        main_grid.bind(minimum_height=main_grid.setter('height'))

        # ========================================
        # 1. VESSEL HEADER CARD
        # ========================================
        header = self._build_vessel_header(vessel_name, imo, areas, products)
        main_grid.add_widget(header)

        # ========================================
        # 2. AREA CARDS
        # ========================================
        for i, area in enumerate(areas):
            accent = AREA_ACCENTS[i % len(AREA_ACCENTS)]
            area_card = self._build_area_card(i, area, accent)
            main_grid.add_widget(area_card)

        # ========================================
        # 3. PRODUCTS SECTION
        # ========================================
        if products:
            prod_section = self._build_products_section(products)
            main_grid.add_widget(prod_section)

        # ========================================
        # 4. MARKING COLORS SECTION
        # ========================================
        if markings:
            mark_section = self._build_markings_section(markings)
            main_grid.add_widget(mark_section)

        # Bottom spacer
        main_grid.add_widget(Widget(size_hint_y=None, height=dp(12)))

        scroll.add_widget(main_grid)
        content.add_widget(scroll)

    # --------------------------------------------------------
    # VESSEL HEADER
    # --------------------------------------------------------
    def _build_vessel_header(self, vessel_name, imo, areas, products):
        """Hero card with vessel name, IMO, and summary stats."""
        card = BoxLayout(
            orientation='vertical',
            size_hint_y=None, height=dp(88),
            padding=[dp(18), dp(12), dp(18), dp(10)],
            spacing=dp(4),
        )
        # Gradient background: dark navy -> dark teal
        _draw_gradient_rect(
            card,
            color_top=(0.06, 0.10, 0.18, 1),
            color_bottom=(0.04, 0.12, 0.14, 1),
            radius=12,
        )

        # Top row: ship emoji + vessel name
        name_row = BoxLayout(size_hint_y=None, height=dp(32))
        name_row.add_widget(Label(
            text='\U0001F6A2',
            font_size='24sp',
            size_hint_x=None, width=dp(36),
            valign='middle', halign='center',
            text_size=(dp(36), dp(32)),
        ))
        name_row.add_widget(Label(
            text=vessel_name,
            font_size='22sp',
            bold=True,
            color=(0.85, 0.92, 0.98, 1),
            halign='left',
            valign='middle',
            text_size=(dp(600), dp(32)),
            shorten=True,
            shorten_from='right',
        ))
        card.add_widget(name_row)

        # IMO row
        if imo:
            imo_row = BoxLayout(size_hint_y=None, height=dp(18),
                                padding=[dp(38), 0, 0, 0])
            imo_row.add_widget(Label(
                text=f'IMO {imo}',
                font_size='12sp',
                color=(0.40, 0.52, 0.62, 1),
                halign='left',
                valign='middle',
                text_size=(dp(300), dp(18)),
            ))
            card.add_widget(imo_row)
        else:
            card.add_widget(Widget(size_hint_y=None, height=dp(4)))

        # Stats row: areas count | products count
        stats_row = BoxLayout(size_hint_y=None, height=dp(20),
                              padding=[dp(38), 0, 0, 0], spacing=dp(8))
        stats_row.add_widget(PillBadge(
            text=f'\U0001F4CB {len(areas)} areas',
            bg_color=(0.00, 0.82, 0.73, 0.18),
            text_color=(0.00, 0.82, 0.73, 1),
            font_size='11sp',
            height=dp(20),
            padding_x=10,
        ))
        stats_row.add_widget(PillBadge(
            text=f'\U0001F3A8 {len(products)} products',
            bg_color=(0.98, 0.65, 0.25, 0.18),
            text_color=(0.98, 0.65, 0.25, 1),
            font_size='11sp',
            height=dp(20),
            padding_x=10,
        ))
        stats_row.add_widget(Widget())  # fill remaining
        card.add_widget(stats_row)

        return card

    # --------------------------------------------------------
    # AREA CARD
    # --------------------------------------------------------
    def _build_area_card(self, index, area, accent_color):
        """A card for one maintenance area with layer rows inside."""
        area_name = area.get('name', f'Area {index + 1}')
        layers = area.get('layers', [])
        notes = area.get('notes', '')

        # Calculate dynamic height
        header_h = dp(38)
        notes_h = dp(20) if notes else 0
        layer_h = dp(36) * len(layers)
        pad_h = dp(16)
        total_h = header_h + notes_h + layer_h + pad_h

        card = BoxLayout(
            orientation='vertical',
            size_hint_y=None, height=total_h,
            padding=[dp(16), dp(8), dp(12), dp(8)],
            spacing=dp(2),
        )

        # Card background
        _draw_rounded_rect(card, (0.10, 0.12, 0.16, 1), radius=12)

        # Colored left accent bar
        _draw_accent_bar(card, accent_color, width=dp(4), radius=3)

        # ---- Area header row ----
        header_row = BoxLayout(
            size_hint_y=None, height=dp(30),
            spacing=dp(8),
        )
        header_row.add_widget(Label(
            text=area_name,
            font_size='17sp',
            bold=True,
            color=accent_color,
            halign='left',
            valign='middle',
            text_size=(dp(500), dp(30)),
            shorten=True,
            shorten_from='right',
        ))

        # Layer count pill
        header_row.add_widget(PillBadge(
            text=f'{len(layers)} layers',
            bg_color=(accent_color[0], accent_color[1],
                      accent_color[2], 0.18),
            text_color=accent_color,
            font_size='10sp',
            height=dp(20),
            padding_x=8,
        ))
        header_row.add_widget(Widget(size_hint_x=None, width=dp(4)))
        card.add_widget(header_row)

        # ---- Notes ----
        if notes:
            card.add_widget(Label(
                text=notes,
                font_size='11sp',
                color=(0.45, 0.50, 0.58, 1),
                size_hint_y=None, height=dp(16),
                halign='left',
                valign='middle',
                text_size=(dp(680), dp(16)),
                padding=[dp(4), 0],
                shorten=True,
                shorten_from='right',
            ))

        # ---- Layer rows ----
        for li, layer in enumerate(layers):
            layer_row = self._build_layer_row(layer, accent_color)
            card.add_widget(layer_row)

            # Divider between layers (not after last)
            if li < len(layers) - 1:
                divider = Widget(size_hint_y=None, height=dp(1))
                _draw_rounded_rect(divider, (0.16, 0.18, 0.24, 0.6),
                                   radius=0)
                card.add_widget(divider)

        return card

    def _build_layer_row(self, layer, accent_color):
        """A single layer row: circle badge + product pill + coat type."""
        layer_num = layer.get('layer_number', '?')
        product = layer.get('product', 'Unknown')
        color_name = layer.get('color', '')
        coat_type = layer.get('coat_type', '')
        dft = layer.get('dft_microns', '')

        row = BoxLayout(
            size_hint_y=None, height=dp(34),
            spacing=dp(8),
            padding=[dp(4), dp(3), dp(4), dp(3)],
        )

        # Circle badge with layer number
        muted_accent = (accent_color[0] * 0.7, accent_color[1] * 0.7,
                        accent_color[2] * 0.7, 1)
        row.add_widget(CircleBadge(
            number=layer_num,
            color=muted_accent,
            diameter=dp(22),
        ))

        # Product pill - use paint color if available
        if color_name:
            pill_bg = _color_for_name(color_name)
        else:
            pill_bg = (0.16, 0.19, 0.26, 1)
        pill_text = _text_color_for_bg(pill_bg)

        row.add_widget(PillBadge(
            text=product,
            bg_color=pill_bg,
            text_color=pill_text,
            font_size='12sp',
            height=dp(24),
            padding_x=10,
        ))

        # Coat info (muted text)
        info_parts = []
        if color_name:
            info_parts.append(color_name)
        if coat_type:
            info_parts.append(coat_type)
        if dft:
            info_parts.append(f'{dft}\u00b5m')

        if info_parts:
            row.add_widget(Label(
                text=' \u00b7 '.join(info_parts),
                font_size='11sp',
                color=(0.48, 0.52, 0.60, 1),
                halign='left',
                valign='middle',
                text_size=(dp(250), dp(28)),
                shorten=True,
                shorten_from='right',
            ))
        else:
            row.add_widget(Widget())

        return row

    # --------------------------------------------------------
    # PRODUCTS SECTION
    # --------------------------------------------------------
    def _build_products_section(self, products):
        """Grid of product info cards."""
        # Section header + product cards
        num_products = len(products)
        card_height = dp(68)
        # Two columns, so rows = ceil(n / 2)
        num_rows = (num_products + 1) // 2
        grid_height = num_rows * (card_height + dp(8))
        section_height = dp(38) + grid_height + dp(8)

        section = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=section_height,
            spacing=dp(6),
        )

        # Section header
        header_row = BoxLayout(size_hint_y=None, height=dp(28),
                               padding=[dp(4), 0])
        header_row.add_widget(Label(
            text='\U0001F3A8  PRODUCTS',
            font_size='15sp',
            bold=True,
            color=(0.00, 0.82, 0.73, 1),
            halign='left',
            valign='middle',
            text_size=(dp(300), dp(28)),
        ))
        header_row.add_widget(PillBadge(
            text=str(num_products),
            bg_color=(0.00, 0.82, 0.73, 0.18),
            text_color=(0.00, 0.82, 0.73, 1),
            font_size='11sp',
            height=dp(20),
            padding_x=8,
        ))
        header_row.add_widget(Widget())
        section.add_widget(header_row)

        # Product cards in a 2-column grid
        grid = GridLayout(
            cols=2,
            spacing=dp(8),
            size_hint_y=None,
            height=grid_height,
        )

        for p in products:
            pcard = self._build_product_card(p)
            grid.add_widget(pcard)

        # Pad grid if odd number
        if num_products % 2 == 1:
            grid.add_widget(Widget())

        section.add_widget(grid)
        return section

    def _build_product_card(self, product):
        """A single product info card."""
        name = product.get('name', '?')
        thinner = product.get('thinner', '')
        components = product.get('components', 1)
        coverage = product.get('coverage_m2_per_liter', '')
        ratio_base = product.get('base_ratio', '')
        ratio_hard = product.get('hardener_ratio', '')
        prod_type = product.get('type', 'default').lower()

        # Determine type color
        if 'hardener' in name.lower() or prod_type == 'hardener':
            type_color = PRODUCT_TYPE_COLORS['hardener']
        elif 'thinner' in name.lower() or prod_type == 'thinner':
            type_color = PRODUCT_TYPE_COLORS['thinner']
        else:
            type_color = PRODUCT_TYPE_COLORS['base']

        card = BoxLayout(
            orientation='vertical',
            size_hint_y=None, height=dp(68),
            padding=[dp(10), dp(8), dp(10), dp(6)],
            spacing=dp(3),
        )
        _draw_rounded_rect(card, (0.10, 0.12, 0.16, 1), radius=10)
        _draw_accent_bar(card, type_color, width=dp(3), radius=2)

        # Product name (bold, truncated)
        card.add_widget(Label(
            text=name,
            font_size='13sp',
            bold=True,
            color=(0.88, 0.90, 0.94, 1),
            size_hint_y=None, height=dp(20),
            halign='left',
            valign='middle',
            text_size=(dp(330), dp(20)),
            shorten=True,
            shorten_from='right',
        ))

        # Details row: ratio, coverage, thinner
        details_row = BoxLayout(
            size_hint_y=None, height=dp(18),
            spacing=dp(6),
        )

        if components > 1 and ratio_base:
            details_row.add_widget(PillBadge(
                text=f'{ratio_base}:{ratio_hard}',
                bg_color=(0.18, 0.20, 0.28, 1),
                text_color=(0.65, 0.68, 0.76, 1),
                font_size='10sp',
                height=dp(16),
                padding_x=6,
            ))

        if coverage:
            details_row.add_widget(PillBadge(
                text=f'{coverage} m\u00b2/L',
                bg_color=(0.18, 0.20, 0.28, 1),
                text_color=(0.65, 0.68, 0.76, 1),
                font_size='10sp',
                height=dp(16),
                padding_x=6,
            ))

        details_row.add_widget(Widget())  # fill
        card.add_widget(details_row)

        # Thinner row
        if thinner:
            card.add_widget(Label(
                text=f'Thinner: {thinner}',
                font_size='10sp',
                color=(0.42, 0.46, 0.54, 1),
                size_hint_y=None, height=dp(14),
                halign='left',
                valign='middle',
                text_size=(dp(330), dp(14)),
                shorten=True,
                shorten_from='right',
            ))
        else:
            card.add_widget(Widget(size_hint_y=None, height=dp(4)))

        return card

    # --------------------------------------------------------
    # MARKING COLORS SECTION
    # --------------------------------------------------------
    def _build_markings_section(self, markings):
        """Horizontal row of color swatches."""
        section_height = dp(110)

        section = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=section_height,
            spacing=dp(6),
        )

        # Section header
        header_row = BoxLayout(size_hint_y=None, height=dp(28),
                               padding=[dp(4), 0])
        header_row.add_widget(Label(
            text='\U0001F3AF  MARKING COLORS',
            font_size='15sp',
            bold=True,
            color=(0.98, 0.76, 0.22, 1),
            halign='left',
            valign='middle',
            text_size=(dp(300), dp(28)),
        ))
        header_row.add_widget(Widget())
        section.add_widget(header_row)

        # Card background for swatch area
        swatch_card = BoxLayout(
            size_hint_y=None,
            height=dp(72),
            padding=[dp(12), dp(6)],
            spacing=dp(8),
        )
        _draw_rounded_rect(swatch_card, (0.10, 0.12, 0.16, 1), radius=10)

        for mc in markings:
            purpose = mc.get('purpose', '?')
            mc_color_name = mc.get('color', '?')
            swatch_rgba = _color_for_name(mc_color_name)

            swatch_card.add_widget(ColorSwatch(
                color_name=f'{purpose}\n{mc_color_name}',
                swatch_color=swatch_rgba,
            ))

        swatch_card.add_widget(Widget())  # fill remaining space
        section.add_widget(swatch_card)

        return section

    # --------------------------------------------------------
    # EMPTY STATE
    # --------------------------------------------------------
    def _build_no_chart(self, content):
        """Show a friendly empty state when no chart is synced."""
        content.add_widget(Widget(size_hint_y=0.15))

        # Empty state card
        empty_card = BoxLayout(
            orientation='vertical',
            size_hint=(0.8, None),
            height=dp(180),
            pos_hint={'center_x': 0.5},
            padding=[dp(24), dp(20)],
            spacing=dp(12),
        )
        _draw_rounded_rect(empty_card, (0.10, 0.12, 0.16, 1), radius=16)

        empty_card.add_widget(Label(
            text='\U0001F4CB',
            font_size='42sp',
            size_hint_y=None, height=dp(50),
            halign='center',
        ))

        empty_card.add_widget(Label(
            text='No Chart Available',
            font_size='22sp',
            bold=True,
            color=(0.55, 0.58, 0.65, 1),
            size_hint_y=None, height=dp(30),
            halign='center',
            text_size=(dp(500), None),
        ))

        empty_card.add_widget(Label(
            text='Pair this device with the cloud\nand upload a maintenance chart\nfor the vessel.',
            font_size='14sp',
            color=(0.38, 0.42, 0.50, 1),
            size_hint_y=None, height=dp(52),
            halign='center',
            text_size=(dp(400), None),
        ))

        content.add_widget(empty_card)
        content.add_widget(Widget(size_hint_y=1))
