"""
Chart Viewer Screen - Maintenance Chart v4 (2026 Redesign)

Completely redesigned with DS tokens for maximum readability on 4.3" 800x480 touchscreen:
- Large, high-contrast WHITE text on dark cards
- Clear area headers with colored accent bars
- Simple text-based layer listing
- Clean product rows with readable details
- Color dots for visual paint color reference
- Glove-friendly spacing, optimized for marine use
"""

import logging

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.app import App
from kivy.graphics import Color, RoundedRectangle, Rectangle, Ellipse
from kivy.metrics import dp

from ui.app import DS

logger = logging.getLogger("smartlocker")


# ================================================================
# CONSTANTS
# ================================================================

# Accent colors cycled per area
AREA_ACCENTS = [
    DS.PRIMARY,                    # Teal
    DS.ACCENT,                     # Amber
    DS.SECONDARY,                  # Blue
    (0.93, 0.45, 0.42, 1),        # Coral
    (0.70, 0.50, 0.90, 1),        # Purple
    DS.SUCCESS,                    # Green
    (0.90, 0.60, 0.75, 1),        # Rose
]

# Paint color name -> RGBA
PAINT_COLORS = {
    'red':        (0.90, 0.25, 0.25, 1),
    'dark red':   (0.70, 0.15, 0.15, 1),
    'brown':      (0.60, 0.38, 0.20, 1),
    'green':      (0.20, 0.70, 0.35, 1),
    'dark green': (0.12, 0.48, 0.20, 1),
    'blue':       (0.25, 0.50, 0.85, 1),
    'dark blue':  (0.15, 0.30, 0.60, 1),
    'white':      (0.92, 0.92, 0.94, 1),
    'black':      (0.18, 0.18, 0.20, 1),
    'grey':       (0.55, 0.57, 0.60, 1),
    'gray':       (0.55, 0.57, 0.60, 1),
    'yellow':     (0.95, 0.85, 0.25, 1),
    'orange':     (0.95, 0.60, 0.18, 1),
    'pink':       (0.90, 0.48, 0.58, 1),
    'maroon':     (0.55, 0.15, 0.18, 1),
    'copper':     (0.75, 0.48, 0.22, 1),
    'beige':      (0.85, 0.78, 0.65, 1),
    'cream':      (0.92, 0.89, 0.78, 1),
    'silver':     (0.72, 0.74, 0.78, 1),
    'aluminum':   (0.68, 0.70, 0.74, 1),
    'aluminium':  (0.68, 0.70, 0.74, 1),
}


# ================================================================
# DRAWING HELPERS
# ================================================================

def _bg(widget, color, radius=10):
    """Rounded background that tracks widget size."""
    with widget.canvas.before:
        Color(*color)
        rr = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[radius])
    widget.bind(
        pos=lambda w, p: setattr(rr, 'pos', p),
        size=lambda w, s: setattr(rr, 'size', s),
    )


def _bar(widget, color, w=4):
    """Colored vertical accent bar on left edge."""
    with widget.canvas.after:
        Color(*color)
        bar = RoundedRectangle(
            pos=(widget.x + dp(2), widget.y + dp(4)),
            size=(dp(w), widget.height - dp(8)),
            radius=[dp(2)],
        )

    def _upd(wid, *_):
        bar.pos = (wid.x + dp(2), wid.y + dp(4))
        bar.size = (dp(w), wid.height - dp(8))

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
    if key in PAINT_COLORS:
        return PAINT_COLORS[key]
    first_word = key.split()[0] if key else ''
    return PAINT_COLORS.get(first_word)


def _clean_text(text):
    """Fix common encoding artifacts from PDF parsing."""
    if not text:
        return text
    return (text
            .replace('\u00c3\u0082\u00c2\u00b5', '\u00b5')
            .replace('\u00c2\u00b5', '\u00b5')
            .replace('\u00c3\u0083\u00c2\u00a2\u00e2\u0082\u00ac\u0161\u00c3\u0082', '')
            .replace('\u00c3\u0083\u00c2', '\u00b5')
            .replace('\u00c3\u0082', '')
            .replace('\u00c2', '')
            .replace('\u00c3\u0083', '')
            .replace('\u00c3', '')
            .strip())


# ================================================================
# MAIN SCREEN
# ================================================================

class ChartViewerScreen(Screen):

    def on_enter(self):
        self.clear_widgets()
        self._build_ui()

    def on_leave(self):
        pass

    def _build_ui(self):
        root = BoxLayout(orientation='vertical')
        with root.canvas.before:
            Color(*DS.BG_DARK)
            root_bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(
            pos=lambda w, p: setattr(root_bg, 'pos', p),
            size=lambda w, s: setattr(root_bg, 'size', s),
        )

        # ---- STATUS BAR ----
        status_bar = BoxLayout(
            size_hint_y=None, height=dp(DS.STATUS_BAR_H),
            padding=[dp(12), dp(4)], spacing=dp(8),
        )
        with status_bar.canvas.before:
            Color(*DS.BG_STATUS_BAR)
            sb_bg = Rectangle(pos=status_bar.pos, size=status_bar.size)
            Color(*(DS.PRIMARY[:3] + (0.25,)))
            sb_line = Rectangle(pos=status_bar.pos, size=(status_bar.width, 1))
        status_bar.bind(
            pos=lambda w, p: (setattr(sb_bg, 'pos', p), setattr(sb_line, 'pos', p)),
            size=lambda w, s: (setattr(sb_bg, 'size', s), setattr(sb_line, 'size', (s[0], 1))),
        )

        # Back button
        back_btn = Button(
            text='<', font_size='22sp', bold=True,
            size_hint=(None, None), size=(dp(50), dp(36)),
            background_normal='', background_color=(0, 0, 0, 0),
            color=DS.TEXT_SECONDARY,
            on_release=lambda x: App.get_running_app().go_back(),
        )
        _bg(back_btn, DS.BG_CARD_HOVER, radius=8)
        status_bar.add_widget(back_btn)

        status_bar.add_widget(Label(
            text='MAINTENANCE CHART', font_size='16sp', bold=True,
            color=DS.TEXT_PRIMARY, size_hint_x=0.55,
            halign='center', valign='middle', text_size=(dp(350), None),
        ))

        self._vessel_label = Label(
            text='', font_size=DS.FONT_TINY,
            color=DS.TEXT_MUTED, size_hint_x=0.25,
            halign='right', valign='middle', text_size=(dp(180), None),
        )
        status_bar.add_widget(self._vessel_label)
        root.add_widget(status_bar)

        # ---- CONTENT ----
        content = BoxLayout(orientation='vertical')

        app = App.get_running_app()
        # Reload chart from DB
        try:
            app.maintenance_chart = app.db.get_maintenance_chart()
        except Exception:
            pass
        chart = getattr(app, 'maintenance_chart', None)

        if not chart:
            self._build_empty_state(content)
        else:
            self._build_chart_content(content, chart)

        root.add_widget(content)
        self.add_widget(root)

    # ================================================================
    # CHART CONTENT
    # ================================================================

    def _build_chart_content(self, content, chart):
        vessel = chart.get('vessel_name', 'Unknown Vessel')
        imo = chart.get('imo_number', '')
        self._vessel_label.text = f'IMO {imo}' if imo else ''

        areas = chart.get('areas', [])
        products = chart.get('products', [])
        markings = chart.get('marking_colors', [])

        scroll = ScrollView(
            size_hint=(1, 1), do_scroll_x=False,
            bar_width=dp(4),
            bar_color=DS.PRIMARY[:3] + (0.5,),
            bar_inactive_color=(0.20, 0.22, 0.28, 0.3),
            scroll_type=['bars', 'content'],
        )

        col = GridLayout(
            cols=1, spacing=dp(8), size_hint_y=None,
            padding=[dp(8), dp(6), dp(8), dp(20)],
        )
        col.bind(minimum_height=col.setter('height'))

        # Vessel header card
        col.add_widget(self._vessel_header(vessel, imo, len(areas), len(products)))

        # Area cards
        for i, area in enumerate(areas):
            accent = AREA_ACCENTS[i % len(AREA_ACCENTS)]
            col.add_widget(self._area_card(area, accent))

        # Products section
        if products:
            col.add_widget(self._products_section(products))

        # Marking colors section
        if markings:
            col.add_widget(self._markings_section(markings))

        col.add_widget(Widget(size_hint_y=None, height=dp(12)))
        scroll.add_widget(col)
        content.add_widget(scroll)

    # ================================================================
    # VESSEL HEADER
    # ================================================================

    def _vessel_header(self, name, imo, n_areas, n_products):
        card = BoxLayout(
            orientation='vertical', size_hint_y=None, height=dp(68),
            padding=[dp(16), dp(10), dp(16), dp(8)], spacing=dp(4),
        )
        _bg(card, (0.10, 0.13, 0.18, 1), radius=DS.RADIUS)

        card.add_widget(Label(
            text=name, font_size=DS.FONT_H2, bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None, height=dp(30),
            halign='left', valign='middle', text_size=(dp(700), dp(30)),
        ))

        stats = f'IMO {imo}   \u2022   {n_areas} areas   \u2022   {n_products} products'
        card.add_widget(Label(
            text=stats, font_size=DS.FONT_SMALL,
            color=(0.55, 0.62, 0.72, 1),
            size_hint_y=None, height=dp(20),
            halign='left', valign='middle', text_size=(dp(700), dp(20)),
        ))

        return card

    # ================================================================
    # AREA CARD
    # ================================================================

    def _area_card(self, area, accent):
        name = area.get('name', 'Unknown Area')
        layers = area.get('layers', [])
        notes = area.get('notes', '')

        header_h = dp(34)
        notes_h = dp(20) if notes else 0
        layers_h = dp(32) * len(layers)
        total = header_h + notes_h + layers_h + dp(14)

        card = BoxLayout(
            orientation='vertical', size_hint_y=None, height=total,
            padding=[dp(14), dp(6), dp(10), dp(6)], spacing=dp(2),
        )
        _bg(card, (0.11, 0.13, 0.17, 1), radius=10)
        _bar(card, accent, w=4)

        # Area name
        card.add_widget(Label(
            text=name, font_size=DS.FONT_BODY, bold=True,
            color=accent, size_hint_y=None, height=dp(26),
            halign='left', valign='middle', text_size=(dp(700), dp(26)),
            padding=[dp(10), 0],
        ))

        # Notes
        if notes:
            card.add_widget(Label(
                text=_clean_text(notes), font_size=DS.FONT_TINY,
                color=(0.50, 0.54, 0.62, 1),
                size_hint_y=None, height=dp(16),
                halign='left', valign='middle', text_size=(dp(700), dp(16)),
                padding=[dp(10), 0],
                shorten=True, shorten_from='right',
            ))

        # Layer rows
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

        # Layer number circle
        circle_size = dp(22)
        muted = (accent[0] * 0.65, accent[1] * 0.65, accent[2] * 0.65, 1)
        num_container = Widget(
            size_hint=(None, None), size=(circle_size, circle_size),
        )
        with num_container.canvas:
            Color(*muted)
            circle_ell = Ellipse(pos=num_container.pos, size=num_container.size)
        num_container.bind(
            pos=lambda w, p: setattr(circle_ell, 'pos', p),
            size=lambda w, s: setattr(circle_ell, 'size', s),
        )
        num_label = Label(
            text=str(num), font_size=DS.FONT_TINY, bold=True,
            color=(1, 1, 1, 1),
            size_hint=(None, None), size=(circle_size, circle_size),
            halign='center', valign='middle',
        )
        num_label.text_size = (circle_size, circle_size)
        num_container.add_widget(num_label)
        num_container.bind(pos=lambda w, p: setattr(num_label, 'pos', p))
        row.add_widget(num_container)

        # Product name
        row.add_widget(Label(
            text=product, font_size='14sp', bold=True,
            color=(0.93, 0.95, 0.97, 1),
            halign='left', valign='middle',
            text_size=(dp(420), dp(28)),
            shorten=True, shorten_from='right',
        ))

        # Color indicator
        if color_name:
            paint_rgba = _resolve_color(color_name)
            color_box = BoxLayout(
                size_hint=(None, None), size=(dp(130), dp(24)),
                spacing=dp(5), padding=[dp(2), dp(3), 0, dp(3)],
            )
            if paint_rgba:
                color_box.add_widget(_dot_widget(paint_rgba, size=14))
            color_box.add_widget(Label(
                text=color_name, font_size=DS.FONT_SMALL,
                color=(0.62, 0.66, 0.74, 1),
                halign='left', valign='middle',
                text_size=(dp(105), dp(20)),
                shorten=True, shorten_from='right',
            ))
            row.add_widget(color_box)

        return row

    # ================================================================
    # PRODUCTS SECTION
    # ================================================================

    def _products_section(self, products):
        row_h = dp(48)
        header_h = dp(34)
        total = header_h + (row_h + dp(4)) * len(products) + dp(8)

        section = BoxLayout(
            orientation='vertical', size_hint_y=None, height=total,
            spacing=dp(4),
        )

        section.add_widget(Label(
            text=f'PRODUCTS  ({len(products)})',
            font_size=DS.FONT_BODY, bold=True, color=DS.PRIMARY,
            size_hint_y=None, height=dp(28),
            halign='left', valign='middle', text_size=(dp(700), dp(28)),
            padding=[dp(4), 0],
        ))

        for p in products:
            section.add_widget(self._product_row(p))

        return section

    def _product_row(self, product):
        """Single product info row."""
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
            bar_color = DS.SECONDARY
        elif 'hardener' in lower or 'hrd' in lower:
            bar_color = DS.ACCENT
        else:
            bar_color = DS.PRIMARY
        _bar(card, bar_color, w=3)

        # Product name
        card.add_widget(Label(
            text=name, font_size='14sp', bold=True,
            color=(0.93, 0.95, 0.97, 1),
            size_hint_y=None, height=dp(20),
            halign='left', valign='middle', text_size=(dp(700), dp(20)),
            padding=[dp(6), 0],
        ))

        # Details line
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
                font_size=DS.FONT_TINY, color=(0.50, 0.55, 0.64, 1),
                size_hint_y=None, height=dp(14),
                halign='left', valign='middle', text_size=(dp(700), dp(14)),
                padding=[dp(6), 0],
                shorten=True, shorten_from='right',
            ))
        else:
            card.add_widget(Widget(size_hint_y=None, height=dp(4)))

        return card

    # ================================================================
    # MARKING COLORS SECTION
    # ================================================================

    def _markings_section(self, markings):
        header_h = dp(34)
        row_h = dp(36)
        total = header_h + (row_h + dp(4)) * len(markings) + dp(8)

        section = BoxLayout(
            orientation='vertical', size_hint_y=None, height=total,
            spacing=dp(4),
        )

        section.add_widget(Label(
            text=f'MARKING COLORS  ({len(markings)})',
            font_size=DS.FONT_BODY, bold=True, color=DS.WARNING,
            size_hint_y=None, height=dp(28),
            halign='left', valign='middle', text_size=(dp(700), dp(28)),
            padding=[dp(4), 0],
        ))

        for mc in markings:
            purpose = mc.get('purpose', '?')
            mc_color_name = mc.get('color', '?')
            paint_rgba = _resolve_color(mc_color_name)

            row = BoxLayout(
                size_hint_y=None, height=dp(32),
                padding=[dp(14), dp(4), dp(10), dp(4)], spacing=dp(10),
            )
            _bg(row, (0.11, 0.13, 0.17, 1), radius=8)

            if paint_rgba:
                row.add_widget(_dot_widget(paint_rgba, size=18))
            else:
                row.add_widget(Widget(size_hint=(None, None), size=(dp(18), dp(18))))

            row.add_widget(Label(
                text=purpose, font_size=DS.FONT_SMALL, bold=True,
                color=(0.93, 0.95, 0.97, 1),
                halign='left', valign='middle', text_size=(dp(350), dp(28)),
            ))

            row.add_widget(Label(
                text=mc_color_name, font_size=DS.FONT_SMALL,
                color=(0.58, 0.62, 0.70, 1),
                size_hint_x=None, width=dp(160),
                halign='right', valign='middle', text_size=(dp(160), dp(28)),
            ))

            section.add_widget(row)

        return section

    # ================================================================
    # EMPTY STATE
    # ================================================================

    def _build_empty_state(self, content):
        content.add_widget(Widget(size_hint_y=0.2))

        card = BoxLayout(
            orientation='vertical',
            size_hint=(0.8, None), height=dp(160),
            pos_hint={'center_x': 0.5},
            padding=[dp(24), dp(20)], spacing=dp(10),
        )
        _bg(card, (0.11, 0.13, 0.17, 1), radius=14)

        card.add_widget(Label(
            text='No Chart Available',
            font_size=DS.FONT_H2, bold=True,
            color=(0.60, 0.63, 0.70, 1),
            size_hint_y=None, height=dp(28),
            halign='center', text_size=(dp(400), None),
        ))
        card.add_widget(Widget(size_hint_y=None, height=dp(8)))
        card.add_widget(Label(
            text='Pair with cloud and upload\na maintenance chart.',
            font_size='14sp', color=(0.42, 0.46, 0.54, 1),
            size_hint_y=None, height=dp(40),
            halign='center', text_size=(dp(400), None),
        ))

        content.add_widget(card)
        content.add_widget(Widget(size_hint_y=1))
