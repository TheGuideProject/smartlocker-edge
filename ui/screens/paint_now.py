"""
Paint Now! Screen - Guided Painting Workflow (2026 Redesign)

Multi-step wizard with progress indicator:
1. SELECT_AREA: Choose vessel area from maintenance chart
2. VIEW_LAYERS: See coating layers for the selected area
3. ENTER_M2: Enter square meters to paint (optional)
4. SHOW_QUANTITIES: Calculated paint quantities
5. -> Navigates to Mixing screen with pre-filled data

Design:
- Step progress bar at top (4 dots with connecting line)
- Large, glove-friendly area cards
- Prominent action buttons
- Clear visual hierarchy at each step
"""

import logging

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle, Rectangle, Line, Ellipse
from kivy.metrics import dp

from ui.app import DS

logger = logging.getLogger("smartlocker")


# ================================================================
# HELPERS
# ================================================================

def _card_bg(widget, color, radius=12):
    """Attach a rounded-rectangle background that tracks pos/size."""
    with widget.canvas.before:
        Color(*color)
        rr = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[radius])
    widget.bind(
        pos=lambda w, p: setattr(rr, 'pos', p),
        size=lambda w, s: setattr(rr, 'size', s),
    )


def _accent_bar(widget, color, width=4):
    """Colored vertical accent bar on left edge."""
    with widget.canvas.after:
        Color(*color)
        bar = RoundedRectangle(
            pos=(widget.x + dp(2), widget.y + dp(4)),
            size=(dp(width), widget.height - dp(8)),
            radius=[dp(2)],
        )

    def _upd(wid, *_):
        bar.pos = (wid.x + dp(2), wid.y + dp(4))
        bar.size = (dp(width), wid.height - dp(8))

    widget.bind(pos=_upd, size=_upd)


class StepProgressBar(Widget):
    """Visual 4-step progress indicator with dots and connecting lines."""

    def __init__(self, current_step=1, total_steps=4, **kwargs):
        super().__init__(**kwargs)
        self.current_step = current_step
        self.total_steps = total_steps
        self.size_hint_y = None
        self.height = dp(28)
        self.bind(pos=self._draw, size=self._draw)
        Clock.schedule_once(lambda dt: self._draw(), 0)

    def _draw(self, *args):
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0:
            return

        pad_x = dp(60)
        w = self.width - 2 * pad_x
        h = self.height
        cx = self.x + pad_x
        cy = self.y + h / 2.0

        step_spacing = w / (self.total_steps - 1) if self.total_steps > 1 else w
        dot_r = dp(5)

        with self.canvas:
            # Background connecting line
            Color(*DS.DIVIDER)
            Line(points=[cx, cy, cx + w, cy], width=1.5)

            # Active connecting line
            if self.current_step > 1:
                active_w = step_spacing * (self.current_step - 1)
                Color(*DS.PRIMARY)
                Line(points=[cx, cy, cx + active_w, cy], width=1.5)

            # Dots
            for i in range(self.total_steps):
                px = cx + i * step_spacing
                if i < self.current_step:
                    Color(*DS.PRIMARY)
                else:
                    Color(0.25, 0.28, 0.34, 1)
                Ellipse(pos=(px - dot_r, cy - dot_r), size=(dot_r * 2, dot_r * 2))


# ================================================================
# MAIN SCREEN
# ================================================================

class PaintNowScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._step = 'SELECT_AREA'
        self._selected_area = None
        self._selected_layer = None
        self._m2_value = None
        self._coverage = None
        self._m2_input = None
        self._calc_liters = 0.0
        self._calc_grams = 0.0

    # ================================================================
    # LIFECYCLE
    # ================================================================

    def on_enter(self):
        """Reset wizard when entering screen."""
        self._step = 'SELECT_AREA'
        self._selected_area = None
        self._selected_layer = None
        self._m2_value = None
        self._coverage = None
        self._build_ui()

    def on_leave(self):
        pass

    # ================================================================
    # NAVIGATION
    # ================================================================

    def go_back(self):
        """Navigate back within wizard or to home."""
        if self._step == 'SELECT_AREA':
            App.get_running_app().go_back()
        elif self._step == 'VIEW_LAYERS':
            self._step = 'SELECT_AREA'
            self._build_ui()
        elif self._step == 'ENTER_M2':
            self._step = 'VIEW_LAYERS'
            self._build_ui()
        elif self._step == 'SHOW_QUANTITIES':
            self._step = 'ENTER_M2'
            self._build_ui()

    # ================================================================
    # UI CONSTRUCTION
    # ================================================================

    def _build_ui(self):
        """Rebuild the entire screen based on current step."""
        self.clear_widgets()

        root = BoxLayout(orientation='vertical')
        with root.canvas.before:
            Color(*DS.BG_DARK)
            root_bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(
            pos=lambda w, p: setattr(root_bg, 'pos', p),
            size=lambda w, s: setattr(root_bg, 'size', s),
        )

        steps = {
            'SELECT_AREA': (1, '1/4'),
            'VIEW_LAYERS': (2, '2/4'),
            'ENTER_M2': (3, '3/4'),
            'SHOW_QUANTITIES': (4, '4/4'),
        }
        step_num, step_text = steps.get(self._step, (1, '?'))

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
            on_release=lambda x: self.go_back(),
        )
        _card_bg(back_btn, DS.BG_CARD_HOVER, radius=8)
        status_bar.add_widget(back_btn)

        status_bar.add_widget(Label(
            text='PAINT NOW!', font_size=DS.FONT_H2, bold=True,
            color=DS.PRIMARY, size_hint_x=0.5,
            halign='center', valign='middle', text_size=(dp(300), None),
        ))
        status_bar.add_widget(Label(
            text=f'Step {step_text}', font_size=DS.FONT_SMALL,
            color=DS.TEXT_MUTED, size_hint_x=0.3,
            halign='right', valign='middle', text_size=(dp(200), None),
        ))

        root.add_widget(status_bar)

        # ---- STEP PROGRESS INDICATOR ----
        root.add_widget(StepProgressBar(current_step=step_num, total_steps=4))

        # ---- DYNAMIC CONTENT ----
        content = BoxLayout(
            orientation='vertical',
            padding=[dp(DS.PAD_SCREEN), dp(6), dp(DS.PAD_SCREEN), dp(8)],
            spacing=dp(6),
        )

        builder_map = {
            'SELECT_AREA': self._build_select_area,
            'VIEW_LAYERS': self._build_view_layers,
            'ENTER_M2': self._build_enter_m2,
            'SHOW_QUANTITIES': self._build_show_quantities,
        }
        builder = builder_map.get(self._step, lambda c: None)
        builder(content)

        root.add_widget(content)
        self.add_widget(root)

    # ================================================================
    # STEP 1: SELECT AREA
    # ================================================================

    def _build_select_area(self, content):
        """Show list of vessel areas from maintenance chart."""
        app = App.get_running_app()
        chart = getattr(app, 'maintenance_chart', None)

        if not chart or not chart.get('areas'):
            content.add_widget(Widget(size_hint_y=0.15))
            content.add_widget(Label(
                text='No Maintenance Chart', font_size='24sp', bold=True,
                color=DS.DANGER, size_hint_y=None, height=dp(42),
                halign='center', text_size=(dp(700), None),
            ))
            content.add_widget(Label(
                text='Sync with cloud to download the\nmaintenance chart for this vessel.',
                font_size=DS.FONT_BODY, color=DS.TEXT_SECONDARY,
                size_hint_y=None, height=dp(50),
                halign='center', text_size=(dp(700), None),
            ))
            content.add_widget(Widget(size_hint_y=1))
            return

        vessel_name = chart.get('vessel_name', 'Unknown Vessel')
        content.add_widget(Label(
            text=f'Select Area  --  {vessel_name}',
            font_size='16sp', bold=True, color=DS.TEXT_SECONDARY,
            size_hint_y=None, height=dp(28),
            halign='center', text_size=(dp(700), None),
        ))

        # Scrollable area list
        scroll = ScrollView(
            size_hint_y=1, do_scroll_x=False,
            bar_width=dp(4),
            bar_color=DS.PRIMARY[:3] + (0.5,),
            bar_inactive_color=(0.20, 0.22, 0.28, 0.3),
            scroll_type=['bars', 'content'],
        )
        grid = GridLayout(
            cols=1, spacing=dp(8), size_hint_y=None, padding=[dp(2), dp(4)],
        )
        grid.bind(minimum_height=grid.setter('height'))

        areas = chart.get('areas', [])
        for i, area in enumerate(areas):
            area_name = area.get('name', f'Area {i + 1}')
            layer_count = len(area.get('layers', []))

            card = BoxLayout(
                orientation='vertical', size_hint_y=None, height=dp(72),
                padding=[dp(16), dp(10)], spacing=dp(4),
            )
            _card_bg(card, DS.BG_CARD, radius=DS.RADIUS)

            # Make the card tappable using a transparent button overlay
            btn = Button(
                text='', background_normal='', background_color=(0, 0, 0, 0),
                size_hint=(1, 1),
            )
            btn.bind(on_release=lambda x, idx=i: self._select_area(idx))

            # Area name
            name_lbl = Label(
                text=area_name, font_size=DS.FONT_H3, bold=True,
                color=DS.TEXT_PRIMARY, size_hint_y=0.6,
                halign='center', valign='middle', text_size=(dp(700), None),
            )

            # Layer count
            info_lbl = Label(
                text=f'{layer_count} coating layers',
                font_size=DS.FONT_SMALL, color=DS.TEXT_MUTED,
                size_hint_y=0.4, halign='center', valign='middle',
                text_size=(dp(700), None),
            )

            card.add_widget(name_lbl)
            card.add_widget(info_lbl)

            # Wrap card + button in relative layout
            from kivy.uix.floatlayout import FloatLayout
            wrapper = FloatLayout(size_hint_y=None, height=dp(72))
            card.size_hint = (1, 1)
            btn.size_hint = (1, 1)
            wrapper.add_widget(card)
            wrapper.add_widget(btn)

            grid.add_widget(wrapper)

        scroll.add_widget(grid)
        content.add_widget(scroll)

    def _select_area(self, area_index):
        """Area selected, move to view layers."""
        app = App.get_running_app()
        chart = getattr(app, 'maintenance_chart', None)
        areas = chart.get('areas', []) if chart else []

        if area_index < len(areas):
            self._selected_area = areas[area_index]
            self._step = 'VIEW_LAYERS'
            self._build_ui()

    # ================================================================
    # STEP 2: VIEW LAYERS
    # ================================================================

    def _build_view_layers(self, content):
        """Show the coating layers for the selected area."""
        area = self._selected_area
        area_name = area.get('name', 'Unknown')
        layers = area.get('layers', [])

        # Area title
        content.add_widget(Label(
            text=area_name, font_size=DS.FONT_H2, bold=True,
            color=DS.ACCENT, size_hint_y=None, height=dp(30),
            halign='center', text_size=(dp(700), None),
        ))

        if area.get('notes'):
            content.add_widget(Label(
                text=area['notes'], font_size=DS.FONT_SMALL,
                color=DS.TEXT_MUTED, size_hint_y=None, height=dp(18),
                halign='center', text_size=(dp(700), None),
            ))

        content.add_widget(Widget(size_hint_y=None, height=dp(4)))

        # Scrollable layer list
        scroll = ScrollView(
            size_hint_y=1, do_scroll_x=False,
            bar_width=dp(4),
            bar_color=DS.PRIMARY[:3] + (0.5,),
            bar_inactive_color=(0.20, 0.22, 0.28, 0.3),
            scroll_type=['bars', 'content'],
        )
        grid = GridLayout(
            cols=1, spacing=dp(8), size_hint_y=None, padding=[dp(2), dp(4)],
        )
        grid.bind(minimum_height=grid.setter('height'))

        for i, layer in enumerate(layers):
            layer_num = layer.get('layer_number', i + 1)
            product = layer.get('product', '?')
            color = layer.get('color', '')

            # Layer card row
            row = BoxLayout(
                orientation='horizontal',
                size_hint_y=None, height=dp(64), spacing=dp(8),
            )

            # Info section
            info_box = BoxLayout(
                orientation='vertical', padding=[dp(12), dp(8)],
            )
            _card_bg(info_box, DS.BG_CARD, radius=DS.RADIUS)

            info_text = f'[b]Layer {layer_num}[/b]    {product}'
            if color:
                hex_c = DS.hex_markup(DS.ACCENT)
                info_text += f'    [color={hex_c}]({color})[/color]'

            info_box.add_widget(Label(
                text=info_text, font_size=DS.FONT_BODY,
                color=(0.85, 0.88, 0.95, 1),
                halign='left', text_size=(dp(420), None), markup=True,
            ))
            row.add_widget(info_box)

            # MIX button
            mix_btn = Button(
                text='MIX', font_size=DS.FONT_BODY, bold=True,
                background_normal='', background_color=(0, 0, 0, 0),
                color=(0.02, 0.05, 0.08, 1), size_hint_x=0.28,
            )
            _card_bg(mix_btn, DS.PRIMARY, radius=DS.RADIUS)
            mix_btn.bind(on_release=lambda x, li=i: self._select_layer(li))
            row.add_widget(mix_btn)

            grid.add_widget(row)

        scroll.add_widget(grid)
        content.add_widget(scroll)

    def _select_layer(self, layer_index):
        """Layer selected, move to enter m2."""
        layers = self._selected_area.get('layers', [])
        if layer_index < len(layers):
            self._selected_layer = layers[layer_index]

            # Try to find coverage from chart products
            app = App.get_running_app()
            chart = getattr(app, 'maintenance_chart', None)
            product_name = self._selected_layer.get('product', '')
            self._coverage = None

            if chart:
                for p in chart.get('products', []):
                    if p.get('name', '').upper() == product_name.upper():
                        self._coverage = p.get('coverage_m2_per_liter')
                        break

            self._step = 'ENTER_M2'
            self._build_ui()

    # ================================================================
    # STEP 3: ENTER M2
    # ================================================================

    def _build_enter_m2(self, content):
        """Ask how many square meters to paint."""
        layer = self._selected_layer
        product_name = layer.get('product', '?')
        color = layer.get('color', '')

        # Product & color badges
        badge_row = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(8))
        badge_row.add_widget(Label(
            text=product_name, font_size='16sp', bold=True,
            color=DS.PRIMARY, halign='center', text_size=(dp(350), None),
        ))
        if color:
            badge_row.add_widget(Label(
                text=color, font_size='14sp', bold=True,
                color=DS.ACCENT, halign='center', text_size=(dp(150), None),
            ))
        content.add_widget(badge_row)

        if self._coverage:
            content.add_widget(Label(
                text=f'Coverage: {self._coverage} m\u00b2/L',
                font_size=DS.FONT_SMALL, color=DS.TEXT_MUTED,
                size_hint_y=None, height=dp(18),
                halign='center', text_size=(dp(700), None),
            ))

        content.add_widget(Widget(size_hint_y=None, height=dp(6)))

        # Question
        content.add_widget(Label(
            text='How many m\u00b2 to paint?',
            font_size='22sp', bold=True, color=DS.TEXT_PRIMARY,
            size_hint_y=None, height=dp(34),
            halign='center', text_size=(dp(700), None),
        ))

        content.add_widget(Widget(size_hint_y=None, height=dp(4)))

        # Numeric input
        input_row = BoxLayout(size_hint_y=None, height=dp(64), padding=[dp(120), 0])
        self._m2_input = TextInput(
            hint_text='m\u00b2',
            font_size='30sp', multiline=False,
            input_filter='float', input_type='number',
            background_color=DS.BG_INPUT,
            foreground_color=DS.PRIMARY,
            cursor_color=DS.PRIMARY,
            hint_text_color=(0.25, 0.28, 0.34, 1),
            halign='center', padding=[dp(12), dp(12)],
        )
        input_row.add_widget(self._m2_input)
        content.add_widget(input_row)

        content.add_widget(Widget(size_hint_y=None, height=dp(6)))

        # Quick-select buttons
        quick_row = BoxLayout(
            spacing=dp(8), size_hint_y=None, height=dp(50),
            padding=[dp(40), 0],
        )
        for m2 in [10, 25, 50, 100]:
            btn = Button(
                text=f'{m2} m\u00b2', font_size=DS.FONT_BODY, bold=True,
                background_normal='', background_color=(0, 0, 0, 0),
                color=DS.TEXT_PRIMARY,
            )
            _card_bg(btn, DS.BG_CARD, radius=DS.RADIUS)
            btn.bind(on_release=lambda x, v=m2: self._set_m2(v))
            quick_row.add_widget(btn)
        content.add_widget(quick_row)

        content.add_widget(Widget(size_hint_y=None, height=dp(8)))

        # Action buttons row
        btn_row = BoxLayout(
            spacing=dp(10), size_hint_y=None, height=dp(58),
            padding=[dp(12), 0],
        )

        calc_btn = Button(
            text='CALCULATE', font_size=DS.FONT_H2, bold=True,
            background_normal='', background_color=(0, 0, 0, 0),
            color=(0.02, 0.05, 0.08, 1),
        )
        _card_bg(calc_btn, DS.PRIMARY, radius=DS.RADIUS)
        calc_btn.bind(on_release=lambda x: self._calculate())
        btn_row.add_widget(calc_btn)

        skip_btn = Button(
            text='SKIP >> MIX', font_size='16sp', bold=True,
            background_normal='', background_color=(0, 0, 0, 0),
            color=DS.TEXT_SECONDARY,
        )
        _card_bg(skip_btn, DS.BG_CARD_HOVER, radius=DS.RADIUS)
        skip_btn.bind(on_release=lambda x: self._skip_to_mix())
        btn_row.add_widget(skip_btn)

        content.add_widget(btn_row)
        content.add_widget(Widget(size_hint_y=1))

    def _set_m2(self, value):
        """Quick-set m2 value."""
        if self._m2_input:
            self._m2_input.text = str(value)

    def _calculate(self):
        """Calculate paint quantities from m2."""
        if not self._m2_input:
            return
        try:
            m2 = float(self._m2_input.text)
            if m2 <= 0:
                return
        except (ValueError, TypeError):
            return

        self._m2_value = m2
        self._step = 'SHOW_QUANTITIES'
        self._build_ui()

    def _skip_to_mix(self):
        """Skip m2 calculation, go directly to mixing."""
        self._m2_value = None
        self._go_to_mixing()

    # ================================================================
    # STEP 4: SHOW QUANTITIES
    # ================================================================

    def _build_show_quantities(self, content):
        """Show calculated paint quantities in a results card."""
        m2 = self._m2_value
        layer = self._selected_layer
        product_name = layer.get('product', '?')

        content.add_widget(Widget(size_hint_y=None, height=dp(4)))

        content.add_widget(Label(
            text='Paint Calculation', font_size='22sp', bold=True,
            color=DS.PRIMARY, size_hint_y=None, height=dp(34),
            halign='center', text_size=(dp(700), None),
        ))

        # Calculate
        coverage = self._coverage or 6.0
        liters = m2 / coverage

        # Look up product density
        app = App.get_running_app()
        density = 1.3  # default
        try:
            product = app.db.get_product_by_name(product_name)
            if product:
                density = product.get('density_g_per_ml', 1.3)
        except Exception:
            pass

        grams = liters * density * 1000

        content.add_widget(Widget(size_hint_y=None, height=dp(6)))

        # Results card
        results_card = BoxLayout(
            orientation='vertical',
            size_hint_y=None, height=dp(150),
            padding=[dp(16), dp(12)], spacing=dp(4),
        )
        _card_bg(results_card, DS.BG_CARD, radius=DS.RADIUS)

        info_lines = [
            f'[b]Area:[/b]  {self._selected_area.get("name", "?")}',
            f'[b]Product:[/b]  {product_name}',
            f'[b]Surface:[/b]  {m2} m\u00b2   |   Coverage: {coverage} m\u00b2/L',
        ]

        for line in info_lines:
            results_card.add_widget(Label(
                text=line, font_size='14sp',
                color=(0.75, 0.78, 0.85, 1),
                size_hint_y=None, height=dp(24),
                halign='left', text_size=(dp(700), None), markup=True,
            ))

        # Highlight result
        results_card.add_widget(Widget(size_hint_y=None, height=dp(6)))
        results_card.add_widget(Label(
            text=f'[b]Needed:  ~{liters:.1f} L  ({grams:.0f} g)[/b]',
            font_size=DS.FONT_H2, color=DS.PRIMARY,
            size_hint_y=None, height=dp(32),
            halign='center', text_size=(dp(700), None), markup=True,
        ))

        content.add_widget(results_card)

        # Store calculated values
        self._calc_liters = liters
        self._calc_grams = grams

        content.add_widget(Widget(size_hint_y=None, height=dp(10)))

        # START MIXING button
        mix_btn = Button(
            text=f'START MIXING  ({grams:.0f}g base)',
            font_size='19sp', bold=True,
            background_normal='', background_color=(0, 0, 0, 0),
            color=(0.02, 0.05, 0.08, 1),
            size_hint=(0.85, None), height=dp(DS.BTN_HEIGHT_LG),
            pos_hint={'center_x': 0.5},
        )
        _card_bg(mix_btn, DS.PRIMARY, radius=DS.RADIUS)
        mix_btn.bind(on_release=lambda x: self._go_to_mixing())
        content.add_widget(mix_btn)

        content.add_widget(Widget(size_hint_y=None, height=dp(6)))

        # Recalculate button
        recalc_btn = Button(
            text='RECALCULATE', font_size='14sp',
            background_normal='', background_color=(0, 0, 0, 0),
            color=DS.TEXT_SECONDARY,
            size_hint=(0.45, None), height=dp(DS.BTN_HEIGHT_SM),
            pos_hint={'center_x': 0.5},
        )
        _card_bg(recalc_btn, DS.BG_CARD_HOVER, radius=DS.RADIUS)
        recalc_btn.bind(on_release=lambda x: self._go_back_to_m2())
        content.add_widget(recalc_btn)

        content.add_widget(Widget(size_hint_y=1))

    def _go_back_to_m2(self):
        self._step = 'ENTER_M2'
        self._build_ui()

    # ================================================================
    # NAVIGATE TO MIXING
    # ================================================================

    def _go_to_mixing(self):
        """Set paint_now_context and navigate to mixing screen."""
        app = App.get_running_app()
        layer = self._selected_layer
        product_name = layer.get('product', '') if layer else ''

        context = {
            'area_name': self._selected_area.get('name', '') if self._selected_area else '',
            'product_name': product_name,
            'layer': layer,
            'color': layer.get('color', '') if layer else '',
        }

        # Add calculated weight if available
        if self._m2_value and hasattr(self, '_calc_grams') and self._calc_grams > 0:
            context['target_base_grams'] = self._calc_grams
            context['m2'] = self._m2_value

        # Find recipe for this product
        try:
            recipe = app.db.find_recipe_by_product_name(product_name)
            if recipe:
                context['recipe_id'] = recipe['recipe_id']
            else:
                safe_name = product_name.replace(' ', '_').upper()[:20]
                context['recipe_id'] = f'AUTO-{safe_name}'
        except Exception:
            safe_name = product_name.replace(' ', '_').upper()[:20]
            context['recipe_id'] = f'AUTO-{safe_name}'

        app.paint_now_context = context
        app.go_screen('mixing')
