"""
Paint Now! Screen - Guided Painting Workflow

Multi-step wizard:
1. SELECT_AREA: Choose vessel area from maintenance chart
2. VIEW_LAYERS: See coating layers for the selected area
3. ENTER_M2: Enter square meters to paint (optional)
4. SHOW_QUANTITIES: Calculated paint quantities
5. -> Navigates to Mixing screen with pre-filled data
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


Builder.load_string('''
<PaintNowScreen>:
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
                on_release: root.go_back()

            Label:
                text: 'PAINT NOW!'
                font_size: '20sp'
                bold: True
                color: 0.18, 0.77, 0.71, 1
                size_hint_x: 0.5
                halign: 'center'
                text_size: self.size
                valign: 'middle'

            Label:
                id: step_label
                text: 'Step 1/4'
                font_size: '13sp'
                color: 0.55, 0.60, 0.68, 1
                size_hint_x: 0.3
                halign: 'right'
                text_size: self.size
                valign: 'middle'

        # ---- DYNAMIC CONTENT ----
        BoxLayout:
            id: content_area
            orientation: 'vertical'
            padding: [15, 10, 15, 10]
            spacing: 8
''')


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
            'SELECT_AREA': ('1/4', self._build_select_area),
            'VIEW_LAYERS': ('2/4', self._build_view_layers),
            'ENTER_M2': ('3/4', self._build_enter_m2),
            'SHOW_QUANTITIES': ('4/4', self._build_show_quantities),
        }

        step_text, builder = steps.get(self._step, ('?', lambda c: None))
        self.ids.step_label.text = f'Step {step_text}'
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
            content.add_widget(Widget(size_hint_y=0.2))
            content.add_widget(Label(
                text='No Maintenance Chart',
                font_size='24sp', bold=True,
                color=(0.90, 0.22, 0.27, 1),
                size_hint_y=None, height=45,
            ))
            content.add_widget(Label(
                text='Sync with cloud to download the\nmaintenance chart for this vessel.',
                font_size='16sp',
                color=(0.65, 0.70, 0.78, 1),
                size_hint_y=None, height=60,
                halign='center', text_size=(700, None),
            ))
            content.add_widget(Widget(size_hint_y=1))
            return

        # Title
        vessel_name = chart.get('vessel_name', 'Unknown Vessel')
        content.add_widget(Label(
            text=f'Select Area - {vessel_name}',
            font_size='18sp', bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None, height=35,
            halign='center', text_size=(700, None),
        ))

        # Scrollable area list
        scroll = ScrollView(size_hint_y=1)
        grid = GridLayout(
            cols=1, spacing=8,
            size_hint_y=None, padding=[5, 5],
        )
        grid.bind(minimum_height=grid.setter('height'))

        areas = chart.get('areas', [])
        for i, area in enumerate(areas):
            area_name = area.get('name', f'Area {i+1}')
            layer_count = len(area.get('layers', []))
            notes = area.get('notes', '')

            btn = Button(
                text=f'{area_name}\n{layer_count} layers' + (f' - {notes}' if notes else ''),
                font_size='16sp', bold=True,
                background_normal='',
                background_color=(0.11, 0.22, 0.35, 1),
                color=(1, 1, 1, 1),
                size_hint_y=None, height=70,
                halign='center',
                text_size=(700, None),
                markup=True,
            )
            btn.bind(on_release=lambda x, idx=i: self._select_area(idx))
            grid.add_widget(btn)

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

        # Title
        content.add_widget(Label(
            text=f'{area_name}',
            font_size='20sp', bold=True,
            color=(0.96, 0.63, 0.38, 1),  # Orange
            size_hint_y=None, height=35,
            halign='center', text_size=(700, None),
        ))

        if area.get('notes'):
            content.add_widget(Label(
                text=area['notes'],
                font_size='13sp',
                color=(0.55, 0.60, 0.68, 1),
                size_hint_y=None, height=22,
                halign='center', text_size=(700, None),
            ))

        # Scrollable layer list
        scroll = ScrollView(size_hint_y=1)
        grid = GridLayout(
            cols=1, spacing=6,
            size_hint_y=None, padding=[5, 5],
        )
        grid.bind(minimum_height=grid.setter('height'))

        for i, layer in enumerate(layers):
            layer_num = layer.get('layer_number', i + 1)
            product = layer.get('product', '?')
            color = layer.get('color', '')

            # Layer row with MIX THIS button
            row = BoxLayout(
                orientation='horizontal',
                size_hint_y=None, height=60,
                spacing=8,
            )

            # Layer info (left side)
            info_text = f'[b]Layer {layer_num}:[/b]  {product}'
            if color:
                info_text += f'  [color=e8c468]({color})[/color]'

            info_label = Label(
                text=info_text,
                font_size='15sp',
                color=(0.85, 0.88, 0.95, 1),
                halign='left', text_size=(450, None),
                markup=True,
                size_hint_x=0.65,
            )
            row.add_widget(info_label)

            # MIX THIS button (right side)
            mix_btn = Button(
                text='MIX THIS',
                font_size='14sp', bold=True,
                background_normal='',
                background_color=(0.18, 0.77, 0.71, 1),
                size_hint_x=0.35,
            )
            mix_btn.bind(on_release=lambda x, li=i: self._select_layer(li))
            row.add_widget(mix_btn)

            grid.add_widget(row)

        scroll.add_widget(grid)
        content.add_widget(scroll)

        # Bottom: Go back to areas
        content.add_widget(Widget(size_hint_y=None, height=5))
        back_btn = Button(
            text='< BACK TO AREAS',
            font_size='15sp',
            background_normal='',
            background_color=(0.20, 0.25, 0.35, 1),
            color=(0.7, 0.75, 0.82, 1),
            size_hint_y=None, height=45,
        )
        back_btn.bind(on_release=lambda x: self._go_back_to_areas())
        content.add_widget(back_btn)

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

    def _go_back_to_areas(self):
        self._step = 'SELECT_AREA'
        self._build_ui()

    # ============================================================
    # STEP 3: ENTER M2
    # ============================================================

    def _build_enter_m2(self, content):
        """Ask how many square meters to paint."""
        layer = self._selected_layer
        product_name = layer.get('product', '?')
        color = layer.get('color', '')

        content.add_widget(Label(
            text=f'Product: {product_name}',
            font_size='18sp', bold=True,
            color=(0.18, 0.77, 0.71, 1),
            size_hint_y=None, height=30,
            halign='center', text_size=(700, None),
        ))

        if color:
            content.add_widget(Label(
                text=f'Color: {color}',
                font_size='14sp',
                color=(0.91, 0.77, 0.42, 1),
                size_hint_y=None, height=22,
                halign='center', text_size=(700, None),
            ))

        if self._coverage:
            content.add_widget(Label(
                text=f'Coverage: {self._coverage} m2/L',
                font_size='13sp',
                color=(0.55, 0.60, 0.68, 1),
                size_hint_y=None, height=22,
                halign='center', text_size=(700, None),
            ))

        content.add_widget(Widget(size_hint_y=None, height=5))

        # Question
        content.add_widget(Label(
            text='How many m\u00b2 to paint?',
            font_size='20sp', bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None, height=35,
            halign='center', text_size=(700, None),
        ))

        # Numeric input
        self._m2_input = TextInput(
            hint_text='Enter m\u00b2',
            font_size='32sp',
            multiline=False,
            input_filter='float',
            size_hint_y=None, height=65,
            size_hint_x=0.5,
            pos_hint={'center_x': 0.5},
            background_color=(0.09, 0.14, 0.21, 1),
            foreground_color=(0.18, 0.77, 0.71, 1),
            cursor_color=(0.18, 0.77, 0.71, 1),
            hint_text_color=(0.25, 0.30, 0.38, 1),
            halign='center',
            padding=[12, 10],
        )
        content.add_widget(self._m2_input)

        # Quick-select buttons
        quick_row = BoxLayout(
            spacing=8, size_hint_y=None, height=50,
            padding=[30, 5],
        )
        for m2 in [10, 25, 50, 100]:
            btn = Button(
                text=f'{m2} m\u00b2',
                font_size='16sp', bold=True,
                background_normal='',
                background_color=(0.11, 0.29, 0.40, 1),
            )
            btn.bind(on_release=lambda x, v=m2: self._set_m2(v))
            quick_row.add_widget(btn)
        content.add_widget(quick_row)

        content.add_widget(Widget(size_hint_y=None, height=8))

        # Action buttons
        btn_row = BoxLayout(
            spacing=12, size_hint_y=None, height=55,
            padding=[15, 0],
        )

        calc_btn = Button(
            text='CALCULATE',
            font_size='18sp', bold=True,
            background_normal='',
            background_color=(0.18, 0.77, 0.71, 1),
        )
        calc_btn.bind(on_release=lambda x: self._calculate())
        btn_row.add_widget(calc_btn)

        skip_btn = Button(
            text='SKIP  \u2192  MIX',
            font_size='18sp', bold=True,
            background_normal='',
            background_color=(0.20, 0.25, 0.35, 1),
            color=(0.7, 0.75, 0.82, 1),
        )
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
        """Show calculated paint quantities."""
        m2 = self._m2_value
        layer = self._selected_layer
        product_name = layer.get('product', '?')

        content.add_widget(Widget(size_hint_y=None, height=5))

        content.add_widget(Label(
            text='Paint Calculation',
            font_size='22sp', bold=True,
            color=(0.18, 0.77, 0.71, 1),
            size_hint_y=None, height=35,
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

        # Display
        info_lines = [
            f'[b]Area:[/b]  {self._selected_area.get("name", "?")}',
            f'[b]Product:[/b]  {product_name}',
            f'[b]Surface:[/b]  {m2} m\u00b2',
            f'[b]Coverage:[/b]  {coverage} m\u00b2/L',
            '',
            f'[b][color=2ec4b6]Needed: ~{liters:.1f} L  ({grams:.0f} g)[/color][/b]',
        ]

        content.add_widget(Label(
            text='\n'.join(info_lines),
            font_size='17sp',
            color=(0.85, 0.88, 0.95, 1),
            size_hint_y=None, height=170,
            halign='center', text_size=(700, None),
            markup=True,
        ))

        content.add_widget(Widget(size_hint_y=None, height=10))

        # Store calculated values for mixing
        self._calc_liters = liters
        self._calc_grams = grams

        # START MIXING button
        mix_btn = Button(
            text=f'START MIXING  ({grams:.0f}g base)',
            font_size='20sp', bold=True,
            background_normal='',
            background_color=(0.18, 0.77, 0.71, 1),
            size_hint=(0.85, None), height=65,
            pos_hint={'center_x': 0.5},
        )
        mix_btn.bind(on_release=lambda x: self._go_to_mixing())
        content.add_widget(mix_btn)

        content.add_widget(Widget(size_hint_y=None, height=8))

        # Recalculate button
        recalc_btn = Button(
            text='RECALCULATE',
            font_size='15sp',
            background_normal='',
            background_color=(0.20, 0.25, 0.35, 1),
            color=(0.7, 0.75, 0.82, 1),
            size_hint=(0.5, None), height=42,
            pos_hint={'center_x': 0.5},
        )
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

        app.paint_now_context = context
        app.go_screen('mixing')
