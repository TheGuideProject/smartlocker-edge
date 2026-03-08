"""
Chart Viewer Screen - Read-Only Maintenance Chart (2026 Redesign)

Shows the synced maintenance chart with:
- Vessel information in a hero header
- All areas and their coating layers in collapsible-style cards
- Product list with coverage info
- Works 100% offline (data from local SQLite)

Design:
- Clean card-based sections with colored accent headers
- Scrollable content with clear visual hierarchy
- Area headers in amber, product headers in teal
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
from kivy.graphics import Color, RoundedRectangle, Rectangle


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
                text: 'MAINTENANCE CHART'
                font_size: '18sp'
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
            padding: [8, 4, 8, 4]
''')


def _make_card_bg(widget, color):
    """Add rounded card background."""
    with widget.canvas.before:
        c = Color(*color)
        rr = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[10])
    widget.bind(pos=lambda w, p: setattr(rr, 'pos', p),
                 size=lambda w, s: setattr(rr, 'size', s))


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
        scroll = ScrollView(size_hint_y=1, do_scroll_x=False)
        grid = GridLayout(
            cols=1, spacing=8,
            size_hint_y=None, padding=[4, 4],
        )
        grid.bind(minimum_height=grid.setter('height'))

        # --- Vessel Header Card ---
        header_card = BoxLayout(
            orientation='vertical',
            size_hint_y=None, height=50,
            padding=[14, 8], spacing=2,
        )
        _make_card_bg(header_card, (0.10, 0.12, 0.16, 1))

        header_card.add_widget(Label(
            text=vessel_name,
            font_size='18sp', bold=True,
            color=(0.33, 0.58, 0.85, 1),
            size_hint_y=None, height=26,
            halign='center', text_size=(750, None),
        ))

        areas = chart.get('areas', [])
        products = chart.get('products', [])

        header_card.add_widget(Label(
            text=f'{len(areas)} areas  |  {len(products)} products',
            font_size='11sp',
            color=(0.38, 0.42, 0.50, 1),
            size_hint_y=None, height=16,
            halign='center', text_size=(750, None),
        ))

        grid.add_widget(header_card)

        # --- Areas & Layers ---
        for i, area in enumerate(areas):
            area_name = area.get('name', f'Area {i+1}')
            layers = area.get('layers', [])
            notes = area.get('notes', '')

            # Area card
            area_height = 32 + len(layers) * 26 + (18 if notes else 0)
            area_card = BoxLayout(
                orientation='vertical',
                size_hint_y=None, height=area_height,
                padding=[12, 6], spacing=2,
            )
            _make_card_bg(area_card, (0.10, 0.12, 0.16, 1))

            # Area header with accent
            area_header = BoxLayout(size_hint_y=None, height=26)
            area_header.add_widget(Label(
                text=f'AREA {i+1}:  {area_name}',
                font_size='14sp', bold=True,
                color=(0.98, 0.65, 0.25, 1),
                halign='left', text_size=(700, None),
                markup=True,
            ))
            area_card.add_widget(area_header)

            if notes:
                area_card.add_widget(Label(
                    text=notes,
                    font_size='11sp',
                    color=(0.38, 0.42, 0.50, 1),
                    size_hint_y=None, height=16,
                    halign='left', text_size=(700, None),
                    padding=[8, 0],
                ))

            # Layer rows
            for layer in layers:
                layer_num = layer.get('layer_number', '?')
                product = layer.get('product', '?')
                color_name = layer.get('color', '')

                layer_text = f'  Layer {layer_num}:  [b]{product}[/b]'
                if color_name:
                    layer_text += f'  [color=fba640]({color_name})[/color]'

                area_card.add_widget(Label(
                    text=layer_text,
                    font_size='13sp',
                    color=(0.75, 0.78, 0.85, 1),
                    size_hint_y=None, height=24,
                    halign='left', text_size=(700, None),
                    markup=True,
                ))

            grid.add_widget(area_card)

        # --- Products Section ---
        if products:
            prod_height = 28 + len(products) * 26
            prod_card = BoxLayout(
                orientation='vertical',
                size_hint_y=None, height=prod_height,
                padding=[12, 6], spacing=2,
            )
            _make_card_bg(prod_card, (0.10, 0.12, 0.16, 1))

            prod_card.add_widget(Label(
                text=f'PRODUCTS ({len(products)})',
                font_size='14sp', bold=True,
                color=(0.00, 0.82, 0.73, 1),
                size_hint_y=None, height=24,
                halign='left', text_size=(700, None),
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

                prod_card.add_widget(Label(
                    text=prod_text,
                    font_size='12sp',
                    color=(0.65, 0.68, 0.76, 1),
                    size_hint_y=None, height=24,
                    halign='left', text_size=(700, None),
                    markup=True,
                ))

            grid.add_widget(prod_card)

        # --- Marking Colors ---
        markings = chart.get('marking_colors', [])
        if markings:
            mark_height = 28 + len(markings) * 22
            mark_card = BoxLayout(
                orientation='vertical',
                size_hint_y=None, height=mark_height,
                padding=[12, 6], spacing=2,
            )
            _make_card_bg(mark_card, (0.10, 0.12, 0.16, 1))

            mark_card.add_widget(Label(
                text=f'MARKING COLORS ({len(markings)})',
                font_size='14sp', bold=True,
                color=(0.98, 0.76, 0.22, 1),
                size_hint_y=None, height=24,
                halign='left', text_size=(700, None),
            ))

            for mc in markings:
                purpose = mc.get('purpose', '?')
                mc_color = mc.get('color', '?')
                mark_card.add_widget(Label(
                    text=f'  {purpose}:  [color=fba640]{mc_color}[/color]',
                    font_size='12sp',
                    color=(0.65, 0.68, 0.76, 1),
                    size_hint_y=None, height=20,
                    halign='left', text_size=(700, None),
                    markup=True,
                ))

            grid.add_widget(mark_card)

        # Bottom padding
        grid.add_widget(Widget(size_hint_y=None, height=16))

        scroll.add_widget(grid)
        content.add_widget(scroll)

    def _build_no_chart(self, content):
        """Show message when no chart is available."""
        content.add_widget(Widget(size_hint_y=0.2))

        content.add_widget(Label(
            text='No Chart Available',
            font_size='24sp', bold=True,
            color=(0.38, 0.42, 0.50, 1),
            size_hint_y=None, height=40,
        ))

        content.add_widget(Label(
            text='Pair this device with the cloud\nand upload a maintenance chart\nfor the vessel.',
            font_size='15sp',
            color=(0.30, 0.33, 0.38, 1),
            size_hint_y=None, height=70,
            halign='center', text_size=(600, None),
        ))

        content.add_widget(Widget(size_hint_y=1))
