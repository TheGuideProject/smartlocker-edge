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

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.lang import Builder
from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle, Rectangle, Line, Ellipse


Builder.load_string('''
<PaintNowScreen>:
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
                on_release: root.go_back()

            Label:
                text: 'PAINT NOW!'
                font_size: '18sp'
                bold: True
                color: 0.00, 0.82, 0.73, 1
                size_hint_x: 0.5
                halign: 'center'
                text_size: self.size
                valign: 'middle'

            Label:
                id: step_label
                text: 'Step 1/4'
                font_size: '12sp'
                color: 0.38, 0.42, 0.50, 1
                size_hint_x: 0.3
                halign: 'right'
                text_size: self.size
                valign: 'middle'

        # ---- STEP PROGRESS INDICATOR ----
        BoxLayout:
            id: progress_bar_area
            size_hint_y: None
            height: '28dp'
            padding: [60, 4, 60, 4]

        # ---- DYNAMIC CONTENT ----
        BoxLayout:
            id: content_area
            orientation: 'vertical'
            padding: [12, 6, 12, 8]
            spacing: 6
''')


class StepProgressBar(BoxLayout):
    """Visual 4-step progress indicator with dots and lines."""

    def __init__(self, current_step=1, total_steps=4, **kwargs):
        super().__init__(**kwargs)
        self.current_step = current_step
        self.total_steps = total_steps
        self.bind(pos=self._draw, size=self._draw)
        Clock.schedule_once(lambda dt: self._draw(), 0)

    def _draw(self, *args):
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0:
            return

        w = self.width
        h = self.height
        cx = self.x
        cy = self.y + h / 2

        step_spacing = w / (self.total_steps - 1) if self.total_steps > 1 else w
        dot_r = 5

        with self.canvas:
            # Draw connecting line (background)
            Color(0.18, 0.20, 0.26, 1)
            Line(
                points=[cx, cy, cx + w, cy],
                width=1.5
            )

            # Draw active connecting line
            if self.current_step > 1:
                active_w = step_spacing * (self.current_step - 1)
                Color(0.00, 0.82, 0.73, 1)
                Line(
                    points=[cx, cy, cx + active_w, cy],
                    width=1.5
                )

            # Draw dots
            for i in range(self.total_steps):
                px = cx + i * step_spacing
                if i < self.current_step:
                    # Active/completed dot
                    Color(0.00, 0.82, 0.73, 1)
                    Ellipse(pos=(px - dot_r, cy - dot_r), size=(dot_r * 2, dot_r * 2))
                else:
                    # Inactive dot
                    Color(0.25, 0.28, 0.34, 1)
                    Ellipse(pos=(px - dot_r, cy - dot_r), size=(dot_r * 2, dot_r * 2))


def _bind_card_bg(widget, color):
    """Add rounded card background to a widget."""
    with widget.canvas.before:
        c = Color(*color)
        rr = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[12])
    widget.bind(pos=lambda w, p: setattr(rr, 'pos', p),
                 size=lambda w, s: setattr(rr, 'size', s))


class PaintNowScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._step = 'SELECT_AREA'
        self._selected_area = None
        self._selected_layer = None
        self._m2_value = None
        self._coverage = None

    def on_enter(self):
        """Reset wizard when entering screen."""
        self._step = 'SELECT_AREA'
        self._selected_area = None
        self._selected_layer = None
        self._m2_value = None
        self._coverage = None
        self._build_ui()

    def go_back(self):
        """Navigate back (within wizard or to home)."""
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

    def _build_ui(self):
        """Rebuild content based on current step."""
        content = self.ids.content_area
        content.clear_widgets()

        steps = {
            'SELECT_AREA': (1, '1/4', self._build_select_area),
            'VIEW_LAYERS': (2, '2/4', self._build_view_layers),
            'ENTER_M2': (3, '3/4', self._build_enter_m2),
            'SHOW_QUANTITIES': (4, '4/4', self._build_show_quantities),
        }

        step_num, step_text, builder = steps.get(self._step, (1, '?', lambda c: None))
        self.ids.step_label.text = f'Step {step_text}'

        # Update progress bar
        prog_area = self.ids.progress_bar_area
        prog_area.clear_widgets()
        prog_area.add_widget(StepProgressBar(current_step=step_num, total_steps=4))

        builder(content)

    # ============================================================
    # STEP 1: SELECT AREA
    # ============================================================

    def _build_select_area(self, content):
        """Show list of vessel areas from maintenance chart."""
        app = App.get_running_app()
        chart = app.maintenance_chart

        if not chart or not chart.get('areas'):
            # No chart available
            content.add_widget(Widget(size_hint_y=0.15))
            content.add_widget(Label(
                text='No Maintenance Chart',
                font_size='24sp', bold=True,
                color=(0.93, 0.27, 0.32, 1),
                size_hint_y=None, height=42,
                halign='center', text_size=(700, None),
            ))
            content.add_widget(Label(
                text='Sync with cloud to download the\nmaintenance chart for this vessel.',
                font_size='15sp',
                color=(0.60, 0.64, 0.72, 1),
                size_hint_y=None, height=50,
                halign='center', text_size=(700, None),
            ))
            content.add_widget(Widget(size_hint_y=1))
            return

        # Title
        vessel_name = chart.get('vessel_name', 'Unknown Vessel')
        content.add_widget(Label(
            text=f'Select Area  --  {vessel_name}',
            font_size='16sp', bold=True,
            color=(0.60, 0.64, 0.72, 1),
            size_hint_y=None, height=28,
            halign='center', text_size=(700, None),
        ))

        # Scrollable area list
        scroll = ScrollView(size_hint_y=1)
        grid = GridLayout(
            cols=1, spacing=8,
            size_hint_y=None, padding=[2, 4],
        )
        grid.bind(minimum_height=grid.setter('height'))

        areas = chart.get('areas', [])
        for i, area in enumerate(areas):
            area_name = area.get('name', f'Area {i+1}')
            layer_count = len(area.get('layers', []))
            notes = area.get('notes', '')

            btn = Button(
                text=f'{area_name}',
                font_size='17sp', bold=True,
                background_normal='',
                background_color=(0, 0, 0, 0),
                color=(0.96, 0.97, 0.98, 1),
                size_hint_y=None, height=72,
                halign='center',
                valign='center',
                text_size=(700, None),
                markup=True,
            )
            _bind_card_bg(btn, (0.10, 0.12, 0.16, 1))
            btn.bind(on_release=lambda x, idx=i: self._select_area(idx))
            grid.add_widget(btn)

            # Sub-info row
            info_text = f'{layer_count} layers'
            info_lbl = Label(
                text=info_text,
                font_size='12sp',
                color=(0.38, 0.42, 0.50, 1),
                size_hint_y=None, height=18,
                halign='center', text_size=(700, None),
            )
            grid.add_widget(info_lbl)

        scroll.add_widget(grid)
        content.add_widget(scroll)

    def _select_area(self, area_index):
        """Area selected, move to view layers."""
        app = App.get_running_app()
        chart = app.maintenance_chart
        areas = chart.get('areas', [])

        if area_index < len(areas):
            self._selected_area = areas[area_index]
            self._step = 'VIEW_LAYERS'
            self._build_ui()

    # ============================================================
    # STEP 2: VIEW LAYERS
    # ============================================================

    def _build_view_layers(self, content):
        """Show the coating layers for the selected area."""
        area = self._selected_area
        area_name = area.get('name', 'Unknown')
        layers = area.get('layers', [])

        # Area title
        content.add_widget(Label(
            text=area_name,
            font_size='18sp', bold=True,
            color=(0.98, 0.65, 0.25, 1),
            size_hint_y=None, height=30,
            halign='center', text_size=(700, None),
        ))

        if area.get('notes'):
            content.add_widget(Label(
                text=area['notes'],
                font_size='12sp',
                color=(0.38, 0.42, 0.50, 1),
                size_hint_y=None, height=18,
                halign='center', text_size=(700, None),
            ))

        content.add_widget(Widget(size_hint_y=None, height=4))

        # Scrollable layer list
        scroll = ScrollView(size_hint_y=1)
        grid = GridLayout(
            cols=1, spacing=8,
            size_hint_y=None, padding=[2, 4],
        )
        grid.bind(minimum_height=grid.setter('height'))

        for i, layer in enumerate(layers):
            layer_num = layer.get('layer_number', i + 1)
            product = layer.get('product', '?')
            color = layer.get('color', '')

            # Layer card
            row = BoxLayout(
                orientation='horizontal',
                size_hint_y=None, height=64,
                spacing=8,
                padding=[0, 0],
            )

            # Layer info (left side) with card bg
            info_box = BoxLayout(orientation='vertical', padding=[12, 8])
            _bind_card_bg(info_box, (0.10, 0.12, 0.16, 1))

            info_text = f'[b]Layer {layer_num}[/b]    {product}'
            if color:
                info_text += f'    [color=fba640]({color})[/color]'

            info_label = Label(
                text=info_text,
                font_size='15sp',
                color=(0.85, 0.88, 0.95, 1),
                halign='left', text_size=(420, None),
                markup=True,
            )
            info_box.add_widget(info_label)
            row.add_widget(info_box)

            # MIX THIS button
            mix_btn = Button(
                text='MIX',
                font_size='15sp', bold=True,
                background_normal='',
                background_color=(0, 0, 0, 0),
                color=(0.02, 0.05, 0.08, 1),
                size_hint_x=0.28,
            )
            _bind_card_bg(mix_btn, (0.00, 0.82, 0.73, 1))
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
            chart = app.maintenance_chart
            product_name = self._selected_layer.get('product', '')
            self._coverage = None

            for p in chart.get('products', []):
                if p.get('name', '').upper() == product_name.upper():
                    self._coverage = p.get('coverage_m2_per_liter')
                    break

            self._step = 'ENTER_M2'
            self._build_ui()

    # ============================================================
    # STEP 3: ENTER M2
    # ============================================================

    def _build_enter_m2(self, content):
        """Ask how many square meters to paint."""
        layer = self._selected_layer
        product_name = layer.get('product', '?')
        color = layer.get('color', '')

        # Product & color badges
        badge_row = BoxLayout(size_hint_y=None, height=28, spacing=8)
        badge_row.add_widget(Label(
            text=product_name,
            font_size='16sp', bold=True,
            color=(0.00, 0.82, 0.73, 1),
            halign='center', text_size=(350, None),
        ))
        if color:
            badge_row.add_widget(Label(
                text=color,
                font_size='14sp', bold=True,
                color=(0.98, 0.65, 0.25, 1),
                halign='center', text_size=(150, None),
            ))
        content.add_widget(badge_row)

        if self._coverage:
            content.add_widget(Label(
                text=f'Coverage: {self._coverage} m\u00b2/L',
                font_size='12sp',
                color=(0.38, 0.42, 0.50, 1),
                size_hint_y=None, height=18,
                halign='center', text_size=(700, None),
            ))

        content.add_widget(Widget(size_hint_y=None, height=6))

        # Question
        content.add_widget(Label(
            text='How many m\u00b2 to paint?',
            font_size='22sp', bold=True,
            color=(0.96, 0.97, 0.98, 1),
            size_hint_y=None, height=34,
            halign='center', text_size=(700, None),
        ))

        content.add_widget(Widget(size_hint_y=None, height=4))

        # Numeric input - large for fat fingers
        input_row = BoxLayout(size_hint_y=None, height=64, padding=[120, 0])
        self._m2_input = TextInput(
            hint_text='m\u00b2',
            font_size='30sp',
            multiline=False,
            input_filter='float',
            background_color=(0.07, 0.09, 0.13, 1),
            foreground_color=(0.00, 0.82, 0.73, 1),
            cursor_color=(0.00, 0.82, 0.73, 1),
            hint_text_color=(0.25, 0.28, 0.34, 1),
            halign='center',
            padding=[12, 12],
        )
        input_row.add_widget(self._m2_input)
        content.add_widget(input_row)

        content.add_widget(Widget(size_hint_y=None, height=6))

        # Quick-select buttons row
        quick_row = BoxLayout(
            spacing=8, size_hint_y=None, height=50,
            padding=[40, 0],
        )
        for m2 in [10, 25, 50, 100]:
            btn = Button(
                text=f'{m2} m\u00b2',
                font_size='15sp', bold=True,
                background_normal='',
                background_color=(0, 0, 0, 0),
                color=(0.96, 0.97, 0.98, 1),
            )
            _bind_card_bg(btn, (0.10, 0.12, 0.16, 1))
            btn.bind(on_release=lambda x, v=m2: self._set_m2(v))
            quick_row.add_widget(btn)
        content.add_widget(quick_row)

        content.add_widget(Widget(size_hint_y=None, height=8))

        # Action buttons row
        btn_row = BoxLayout(
            spacing=10, size_hint_y=None, height=58,
            padding=[12, 0],
        )

        calc_btn = Button(
            text='CALCULATE',
            font_size='18sp', bold=True,
            background_normal='',
            background_color=(0, 0, 0, 0),
            color=(0.02, 0.05, 0.08, 1),
        )
        _bind_card_bg(calc_btn, (0.00, 0.82, 0.73, 1))
        calc_btn.bind(on_release=lambda x: self._calculate())
        btn_row.add_widget(calc_btn)

        skip_btn = Button(
            text='SKIP  >>  MIX',
            font_size='16sp', bold=True,
            background_normal='',
            background_color=(0, 0, 0, 0),
            color=(0.60, 0.64, 0.72, 1),
        )
        _bind_card_bg(skip_btn, (0.13, 0.15, 0.20, 1))
        skip_btn.bind(on_release=lambda x: self._skip_to_mix())
        btn_row.add_widget(skip_btn)

        content.add_widget(btn_row)
        content.add_widget(Widget(size_hint_y=1))

    def _set_m2(self, value):
        """Quick-set m2 value."""
        self._m2_input.text = str(value)

    def _calculate(self):
        """Calculate paint quantities from m2."""
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

    # ============================================================
    # STEP 4: SHOW QUANTITIES
    # ============================================================

    def _build_show_quantities(self, content):
        """Show calculated paint quantities in a results card."""
        m2 = self._m2_value
        layer = self._selected_layer
        product_name = layer.get('product', '?')

        content.add_widget(Widget(size_hint_y=None, height=4))

        content.add_widget(Label(
            text='Paint Calculation',
            font_size='22sp', bold=True,
            color=(0.00, 0.82, 0.73, 1),
            size_hint_y=None, height=34,
            halign='center', text_size=(700, None),
        ))

        # Calculate
        coverage = self._coverage or 6.0  # Default 6 m2/L if unknown
        liters = m2 / coverage

        # Look up product density
        app = App.get_running_app()
        product = app.db.get_product_by_name(product_name)
        density = 1.3  # Default
        if product:
            density = product.get('density_g_per_ml', 1.3)

        grams = liters * density * 1000

        content.add_widget(Widget(size_hint_y=None, height=6))

        # Results card
        results_card = BoxLayout(
            orientation='vertical',
            size_hint_y=None, height=150,
            padding=[16, 12], spacing=4,
        )
        _bind_card_bg(results_card, (0.10, 0.12, 0.16, 1))

        info_lines = [
            f'[b]Area:[/b]  {self._selected_area.get("name", "?")}',
            f'[b]Product:[/b]  {product_name}',
            f'[b]Surface:[/b]  {m2} m\u00b2   |   Coverage: {coverage} m\u00b2/L',
        ]

        for line in info_lines:
            results_card.add_widget(Label(
                text=line,
                font_size='14sp',
                color=(0.75, 0.78, 0.85, 1),
                size_hint_y=None, height=24,
                halign='left', text_size=(700, None),
                markup=True,
            ))

        # Highlight result
        results_card.add_widget(Widget(size_hint_y=None, height=6))
        results_card.add_widget(Label(
            text=f'[b]Needed:  ~{liters:.1f} L  ({grams:.0f} g)[/b]',
            font_size='20sp',
            color=(0.00, 0.82, 0.73, 1),
            size_hint_y=None, height=32,
            halign='center', text_size=(700, None),
            markup=True,
        ))

        content.add_widget(results_card)

        # Store calculated values
        self._calc_liters = liters
        self._calc_grams = grams

        content.add_widget(Widget(size_hint_y=None, height=10))

        # START MIXING button
        mix_btn = Button(
            text=f'START MIXING  ({grams:.0f}g base)',
            font_size='19sp', bold=True,
            background_normal='',
            background_color=(0, 0, 0, 0),
            color=(0.02, 0.05, 0.08, 1),
            size_hint=(0.85, None), height=64,
            pos_hint={'center_x': 0.5},
        )
        _bind_card_bg(mix_btn, (0.00, 0.82, 0.73, 1))
        mix_btn.bind(on_release=lambda x: self._go_to_mixing())
        content.add_widget(mix_btn)

        content.add_widget(Widget(size_hint_y=None, height=6))

        # Recalculate button
        recalc_btn = Button(
            text='RECALCULATE',
            font_size='14sp',
            background_normal='',
            background_color=(0, 0, 0, 0),
            color=(0.60, 0.64, 0.72, 1),
            size_hint=(0.45, None), height=40,
            pos_hint={'center_x': 0.5},
        )
        _bind_card_bg(recalc_btn, (0.13, 0.15, 0.20, 1))
        recalc_btn.bind(on_release=lambda x: self._go_back_to_m2())
        content.add_widget(recalc_btn)

        content.add_widget(Widget(size_hint_y=1))

    def _go_back_to_m2(self):
        self._step = 'ENTER_M2'
        self._build_ui()

    # ============================================================
    # NAVIGATE TO MIXING
    # ============================================================

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
        if self._m2_value and hasattr(self, '_calc_grams'):
            context['target_base_grams'] = self._calc_grams
            context['m2'] = self._m2_value

        # Find recipe for this product
        recipe = app.db.find_recipe_by_product_name(product_name)
        if recipe:
            context['recipe_id'] = recipe['recipe_id']
        else:
            # No recipe in DB — generate a temporary ID so mixing screen
            # can build a fallback recipe from the maintenance chart data
            safe_name = product_name.replace(' ', '_').upper()[:20]
            context['recipe_id'] = f'AUTO-{safe_name}'

        app.paint_now_context = context
        app.go_screen('mixing')
