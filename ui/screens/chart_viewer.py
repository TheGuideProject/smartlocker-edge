"""
Chart Viewer Screen - Read-Only Maintenance Chart Display

Shows the synced maintenance chart with:
- Vessel information
- All areas and their coating layers
- Product list with coverage info
- Works 100% offline (data from local SQLite)
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.lang import Builder
from kivy.app import App


Builder.load_string('''
<ChartViewerScreen>:
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
                on_release: app.go_back()

            Label:
                text: 'MAINTENANCE CHART'
                font_size: '20sp'
                bold: True
                size_hint_x: 0.6
                halign: 'center'
                text_size: self.size
                valign: 'middle'

            Label:
                id: vessel_label
                text: ''
                font_size: '12sp'
                color: 0.55, 0.60, 0.68, 1
                size_hint_x: 0.2
                halign: 'right'
                text_size: self.size
                valign: 'middle'

        # ---- SCROLLABLE CONTENT ----
        BoxLayout:
            id: content_area
            orientation: 'vertical'
            padding: [10, 5, 10, 5]
''')


class ChartViewerScreen(Screen):

    def on_enter(self):
        """Build chart view from local data."""
        content = self.ids.content_area
        content.clear_widgets()

        app = App.get_running_app()

        # Reload from DB in case it was updated
        app.maintenance_chart = app.db.get_maintenance_chart()
        chart = app.maintenance_chart

        if not chart:
            self._build_no_chart(content)
            return

        vessel_name = chart.get('vessel_name', 'Unknown')
        imo = chart.get('imo_number', '')
        self.ids.vessel_label.text = f'IMO {imo}' if imo else ''

        # Build scrollable content
        scroll = ScrollView(size_hint_y=1)
        grid = GridLayout(
            cols=1, spacing=10,
            size_hint_y=None, padding=[5, 5],
        )
        grid.bind(minimum_height=grid.setter('height'))

        # --- Vessel Header ---
        grid.add_widget(Label(
            text=f'{vessel_name}',
            font_size='20sp', bold=True,
            color=(0.37, 0.66, 0.83, 1),
            size_hint_y=None, height=35,
            halign='center', text_size=(750, None),
        ))

        areas = chart.get('areas', [])
        products = chart.get('products', [])

        grid.add_widget(Label(
            text=f'{len(areas)} areas  |  {len(products)} products',
            font_size='13sp',
            color=(0.55, 0.60, 0.68, 1),
            size_hint_y=None, height=22,
            halign='center', text_size=(750, None),
        ))

        # --- Areas & Layers ---
        for i, area in enumerate(areas):
            area_name = area.get('name', f'Area {i+1}')
            layers = area.get('layers', [])
            notes = area.get('notes', '')

            # Area header
            grid.add_widget(self._make_section_header(
                f'AREA {i+1}: {area_name}',
                color=(0.96, 0.63, 0.38, 1),
            ))

            if notes:
                grid.add_widget(Label(
                    text=notes,
                    font_size='12sp',
                    color=(0.45, 0.50, 0.58, 1),
                    size_hint_y=None, height=20,
                    halign='left', text_size=(750, None),
                    padding=[10, 0],
                ))

            # Layer rows
            for layer in layers:
                layer_num = layer.get('layer_number', '?')
                product = layer.get('product', '?')
                color = layer.get('color', '')

                layer_text = f'  Layer {layer_num}:  [b]{product}[/b]'
                if color:
                    layer_text += f'  [color=e8c468]({color})[/color]'

                grid.add_widget(Label(
                    text=layer_text,
                    font_size='14sp',
                    color=(0.80, 0.83, 0.90, 1),
                    size_hint_y=None, height=28,
                    halign='left', text_size=(750, None),
                    markup=True,
                ))

        # --- Products ---
        if products:
            grid.add_widget(Widget(size_hint_y=None, height=8))
            grid.add_widget(self._make_section_header(
                f'PRODUCTS ({len(products)})',
                color=(0.18, 0.77, 0.71, 1),
            ))

            for p in products:
                name = p.get('name', '?')
                thinner = p.get('thinner', '')
                components = p.get('components', 1)
                coverage = p.get('coverage_m2_per_liter', '')
                ratio_base = p.get('base_ratio', '')
                ratio_hard = p.get('hardener_ratio', '')

                prod_text = f'  [b]{name}[/b]'
                details = []
                if components > 1 and ratio_base:
                    details.append(f'{ratio_base}:{ratio_hard}')
                if thinner:
                    details.append(f'Thinner: {thinner}')
                if coverage:
                    details.append(f'{coverage} m\u00b2/L')

                if details:
                    prod_text += f'  ({", ".join(details)})'

                grid.add_widget(Label(
                    text=prod_text,
                    font_size='13sp',
                    color=(0.75, 0.80, 0.88, 1),
                    size_hint_y=None, height=28,
                    halign='left', text_size=(750, None),
                    markup=True,
                ))

        # --- Marking Colors ---
        markings = chart.get('marking_colors', [])
        if markings:
            grid.add_widget(Widget(size_hint_y=None, height=8))
            grid.add_widget(self._make_section_header(
                f'MARKING COLORS ({len(markings)})',
                color=(0.91, 0.77, 0.42, 1),
            ))

            for mc in markings:
                purpose = mc.get('purpose', '?')
                color = mc.get('color', '?')
                grid.add_widget(Label(
                    text=f'  {purpose}:  [color=e8c468]{color}[/color]',
                    font_size='13sp',
                    color=(0.75, 0.80, 0.88, 1),
                    size_hint_y=None, height=25,
                    halign='left', text_size=(750, None),
                    markup=True,
                ))

        # Bottom padding
        grid.add_widget(Widget(size_hint_y=None, height=20))

        scroll.add_widget(grid)
        content.add_widget(scroll)

    def _build_no_chart(self, content):
        """Show message when no chart is available."""
        content.add_widget(Widget(size_hint_y=0.25))

        content.add_widget(Label(
            text='No Chart Available',
            font_size='26sp', bold=True,
            color=(0.55, 0.60, 0.68, 1),
            size_hint_y=None, height=45,
        ))

        content.add_widget(Label(
            text='Pair this device with the cloud\nand upload a maintenance chart\nfor the vessel.',
            font_size='16sp',
            color=(0.45, 0.50, 0.58, 1),
            size_hint_y=None, height=80,
            halign='center', text_size=(700, None),
        ))

        content.add_widget(Widget(size_hint_y=1))

    def _make_section_header(self, text, color=(1, 1, 1, 1)):
        """Create a styled section header label."""
        return Label(
            text=text,
            font_size='15sp', bold=True,
            color=color,
            size_hint_y=None, height=30,
            halign='left', text_size=(750, None),
        )
