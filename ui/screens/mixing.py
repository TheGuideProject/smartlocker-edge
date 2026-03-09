"""
Mixing Screen - Step-by-Step Mixing Wizard

Guides the crew through the complete mixing workflow:
1. Start session with recipe
2. Pick base can (LED guidance)
3. Weigh base on mixing scale (live gauge)
4. Pick hardener can
5. Weigh hardener (ratio monitoring)
6. Confirm mix (in-spec / out-of-spec)
7. Optional thinner
8. Pot-life countdown
9. Return cans to shelf
10. Session complete

In TEST mode, each step has "Simulate" buttons to advance without real sensors.
"""

import time

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.progressbar import ProgressBar
from kivy.lang import Builder
from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, RoundedRectangle

from core.models import MixingState, MixingRecipe


Builder.load_string('''
<MixingScreen>:
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
                text: 'MIXING ASSISTANT'
                font_size: '20sp'
                bold: True
                size_hint_x: 0.5
                halign: 'center'
                text_size: self.size
                valign: 'middle'

            Label:
                id: state_badge
                text: 'IDLE'
                font_size: '13sp'
                bold: True
                color: 0.55, 0.60, 0.68, 1
                size_hint_x: 0.3
                halign: 'right'
                text_size: self.size
                valign: 'middle'

        # ---- MAIN CONTENT (dynamic) ----
        BoxLayout:
            id: content_area
            orientation: 'vertical'
            padding: [20, 10, 20, 15]
            spacing: 10
''')


class MixingScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._refresh_event = None
        self._last_state = None
        # Thinner weighing sub-state
        self._thinner_weighing = False
        self._thinner_method = None
        self._thinner_target_g = 0.0

    def on_enter(self):
        """Start refreshing when screen is shown."""
        self._refresh_event = Clock.schedule_interval(self._refresh, 0.3)
        self._refresh(0)

    def on_leave(self):
        if self._refresh_event:
            self._refresh_event.cancel()

    def _refresh(self, dt):
        """Update display based on current mixing state."""
        app = App.get_running_app()
        state = app.mixing.current_state

        # Update state badge
        state_text = state.value.replace('_', ' ').upper()
        self.ids.state_badge.text = state_text

        # Color the badge
        if state == MixingState.IDLE:
            self.ids.state_badge.color = (0.55, 0.60, 0.68, 1)
        elif state in (MixingState.SESSION_COMPLETE, MixingState.ABORTED):
            self.ids.state_badge.color = (0.55, 0.60, 0.68, 1)
        else:
            self.ids.state_badge.color = (0.18, 0.77, 0.71, 1)

        # Only rebuild UI if state changed
        if state != self._last_state:
            self._last_state = state
            # Reset thinner weighing sub-state when leaving ADD_THINNER
            if state != MixingState.ADD_THINNER:
                self._thinner_weighing = False
            self._build_state_ui(state)

        # Live updates for weight states
        if state in (MixingState.WEIGH_BASE, MixingState.WEIGH_HARDENER):
            self._update_weight_display()
        elif state == MixingState.ADD_THINNER and self._thinner_weighing:
            self._update_thinner_weight_display()
        elif state == MixingState.POT_LIFE_ACTIVE:
            self._update_pot_life_display()

    def _build_state_ui(self, state):
        """Rebuild the content area for the current state."""
        content = self.ids.content_area
        content.clear_widgets()

        app = App.get_running_app()
        is_test = app.mode == 'test'

        if state == MixingState.IDLE:
            self._build_idle_ui(content, is_test)
        elif state == MixingState.SELECT_PRODUCT:
            self._build_select_product_ui(content)
        elif state == MixingState.SHOW_RECIPE:
            self._build_show_recipe_ui(content)
        elif state == MixingState.PICK_BASE:
            self._build_pick_can_ui(content, 'BASE', is_test)
        elif state == MixingState.WEIGH_BASE:
            self._build_weigh_ui(content, 'BASE', is_test)
        elif state == MixingState.PICK_HARDENER:
            self._build_pick_can_ui(content, 'HARDENER', is_test)
        elif state == MixingState.WEIGH_HARDENER:
            self._build_weigh_ui(content, 'HARDENER', is_test)
        elif state == MixingState.CONFIRM_MIX:
            self._build_confirm_mix_ui(content)
        elif state == MixingState.ADD_THINNER:
            if self._thinner_weighing:
                self._build_thinner_weigh_ui(content, is_test)
            else:
                self._build_thinner_ui(content)
        elif state == MixingState.POT_LIFE_ACTIVE:
            self._build_pot_life_ui(content)
        elif state == MixingState.RETURN_CANS:
            self._build_return_cans_ui(content, is_test)
        elif state == MixingState.SESSION_COMPLETE:
            self._build_complete_ui(content)
        elif state == MixingState.ABORTED:
            self._build_idle_ui(content, is_test)

    # ============================================================
    # STATE UI BUILDERS
    # ============================================================

    def _build_idle_ui(self, content, is_test):
        """IDLE: Show start button, with Paint Now context info if available."""
        app = App.get_running_app()
        ctx = app.paint_now_context

        content.add_widget(Widget(size_hint_y=0.1))

        if ctx:
            # Coming from Paint Now — show context info
            area = ctx.get('area_name', '')
            product = ctx.get('product_name', '')
            color = ctx.get('color', '')
            target_g = ctx.get('target_base_grams')
            m2 = ctx.get('m2')

            title = Label(
                text='Ready to Mix',
                font_size='24sp', bold=True,
                color=(0.18, 0.77, 0.71, 1),
                size_hint_y=None, height=40,
            )
            content.add_widget(title)

            info_lines = []
            if area:
                info_lines.append(f'[b]Area:[/b] {area}')
            if product:
                info_lines.append(f'[b]Product:[/b] {product}')
            if color:
                info_lines.append(f'[b]Color:[/b] {color}')
            if m2:
                info_lines.append(f'[b]Surface:[/b] {m2} m\u00b2')
            if target_g:
                info_lines.append(f'[b]Target base:[/b] {target_g:.0f} g')

            if info_lines:
                content.add_widget(Label(
                    text='\n'.join(info_lines),
                    font_size='16sp',
                    color=(0.85, 0.88, 0.95, 1),
                    size_hint_y=None, height=len(info_lines) * 26 + 10,
                    halign='center', text_size=(700, None),
                    markup=True,
                ))

            content.add_widget(Widget(size_hint_y=0.05))

            btn = Button(
                text='START MIXING',
                font_size='24sp', bold=True,
                background_normal='',
                background_color=(0.18, 0.77, 0.71, 1),
                size_hint=(0.7, None), height=75,
                pos_hint={'center_x': 0.5},
            )
            btn.bind(on_release=lambda x: self._start_mix())
            content.add_widget(btn)
        else:
            # Standard entry (no Paint Now context)
            title = Label(
                text='Ready to Mix',
                font_size='28sp', bold=True,
                color=(1, 1, 1, 1),
                size_hint_y=None, height=50,
            )
            content.add_widget(title)

            subtitle = Label(
                text='Tap START to begin a guided mixing session.\nThe system will show you which cans to pick and\nhow much to pour.',
                font_size='16sp',
                color=(0.65, 0.70, 0.78, 1),
                size_hint_y=None, height=80,
                halign='center', text_size=(700, None),
            )
            content.add_widget(subtitle)

            content.add_widget(Widget(size_hint_y=0.1))

            btn = Button(
                text='START NEW MIX',
                font_size='24sp', bold=True,
                background_normal='',
                background_color=(0.18, 0.77, 0.71, 1),
                size_hint=(0.7, None), height=80,
                pos_hint={'center_x': 0.5},
            )
            btn.bind(on_release=lambda x: self._start_mix())
            content.add_widget(btn)

        content.add_widget(Widget(size_hint_y=1))

    def _build_select_product_ui(self, content):
        """SELECT_PRODUCT: Show recipe selection and amount buttons."""
        content.add_widget(Widget(size_hint_y=0.1))

        title = Label(
            text='Select Amount',
            font_size='24sp', bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None, height=45,
        )
        content.add_widget(title)

        app = App.get_running_app()
        ctx = app.paint_now_context

        # Get recipe name from context or default
        recipe_name = 'SIGMACOVER 280 System'
        if app.mixing.session and app.mixing.session.recipe_id:
            # Try to get name from loaded recipes
            recipes = getattr(app.mixing, '_recipes', {})
            recipe = recipes.get(app.mixing.session.recipe_id)
            if recipe:
                recipe_name = recipe.name

        info_text = f'Recipe: {recipe_name}\nRatio: 4:1 (Base:Hardener)\n\nHow much BASE do you want to mix?'
        if ctx and ctx.get('product_name'):
            info_text = f'Product: {ctx["product_name"]}\nRecipe: {recipe_name}\n\nHow much BASE do you want to mix?'

        info = Label(
            text=info_text,
            font_size='16sp',
            color=(0.65, 0.70, 0.78, 1),
            size_hint_y=None, height=100,
            halign='center', text_size=(700, None),
            markup=True,
        )
        content.add_widget(info)

        # Quick-select amount buttons
        amounts_row = BoxLayout(
            spacing=10, size_hint_y=None, height=70,
            padding=[50, 0],
        )
        for amount in [250, 500, 1000, 2000]:
            btn = Button(
                text=f'{amount}g',
                font_size='20sp', bold=True,
                background_normal='',
                background_color=(0.11, 0.29, 0.40, 1),
            )
            btn.bind(on_release=lambda x, a=amount: self._select_amount(a))
            amounts_row.add_widget(btn)
        content.add_widget(amounts_row)

        content.add_widget(Widget(size_hint_y=1))

    def _build_show_recipe_ui(self, content):
        """SHOW_RECIPE: Display calculated amounts."""
        app = App.get_running_app()
        session = app.mixing.session

        content.add_widget(Widget(size_hint_y=0.05))

        title = Label(
            text='Recipe Ready',
            font_size='24sp', bold=True,
            color=(0.18, 0.77, 0.71, 1),
            size_hint_y=None, height=40,
        )
        content.add_widget(title)

        info_text = (
            f'[b]Base:[/b]  {session.base_weight_target_g:.0f} g\n'
            f'[b]Hardener:[/b]  {session.hardener_weight_target_g:.0f} g\n'
            f'[b]Ratio:[/b]  4:1\n'
            f'[b]Pot Life:[/b]  8 hours'
        )
        info = Label(
            text=info_text,
            font_size='20sp',
            color=(0.85, 0.88, 0.95, 1),
            size_hint_y=None, height=140,
            markup=True,
            halign='center', text_size=(700, None),
        )
        content.add_widget(info)

        content.add_widget(Widget(size_hint_y=0.05))

        btn = Button(
            text='CONFIRM  -  PICK BASE CAN',
            font_size='20sp', bold=True,
            background_normal='',
            background_color=(0.18, 0.77, 0.71, 1),
            size_hint=(0.8, None), height=70,
            pos_hint={'center_x': 0.5},
        )
        btn.bind(on_release=lambda x: self._confirm_recipe())
        content.add_widget(btn)

        content.add_widget(Widget(size_hint_y=1))

    def _build_pick_can_ui(self, content, can_type, is_test):
        """PICK_BASE or PICK_HARDENER: Show pick instructions."""
        content.add_widget(Widget(size_hint_y=0.1))

        slot_num = 1 if can_type == 'BASE' else 2
        title = Label(
            text=f'Pick {can_type} Can',
            font_size='26sp', bold=True,
            color=(0.37, 0.66, 0.83, 1),
            size_hint_y=None, height=45,
        )
        content.add_widget(title)

        instruction = Label(
            text=f'Remove the {can_type} can from\n[b]SLOT {slot_num}[/b] (LED is lit green)',
            font_size='18sp',
            color=(0.75, 0.80, 0.88, 1),
            size_hint_y=None, height=70,
            halign='center', text_size=(700, None),
            markup=True,
        )
        content.add_widget(instruction)

        content.add_widget(Widget(size_hint_y=0.1))

        if is_test:
            # Simulate button for TEST mode
            sim_btn = Button(
                text=f'SIMULATE: Remove {can_type} from Slot {slot_num}',
                font_size='17sp', bold=True,
                background_normal='',
                background_color=(0.40, 0.28, 0.10, 1),
                size_hint=(0.8, None), height=65,
                pos_hint={'center_x': 0.5},
            )
            sim_btn.bind(on_release=lambda x: self._simulate_pick(can_type))
            content.add_widget(sim_btn)

        # Waiting indicator
        waiting = Label(
            text='Waiting for RFID detection...',
            font_size='14sp',
            color=(0.55, 0.60, 0.68, 1),
            size_hint_y=None, height=30,
        )
        content.add_widget(waiting)

        content.add_widget(Widget(size_hint_y=1))

    def _build_weigh_ui(self, content, component, is_test):
        """WEIGH_BASE or WEIGH_HARDENER: Live weight gauge."""
        app = App.get_running_app()
        session = app.mixing.session

        if component == 'BASE':
            target = session.base_weight_target_g
        else:
            target = session.hardener_weight_target_g

        title = Label(
            text=f'Pour {component}',
            font_size='24sp', bold=True,
            color=(0.37, 0.66, 0.83, 1),
            size_hint_y=None, height=40,
        )
        content.add_widget(title)

        # Target info
        target_label = Label(
            text=f'Target: {target:.0f} g',
            font_size='18sp',
            color=(0.65, 0.70, 0.78, 1),
            size_hint_y=None, height=30,
        )
        content.add_widget(target_label)

        # Weight display (large number)
        self._weight_value_label = Label(
            text='0 g',
            font_size='48sp', bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None, height=70,
        )
        content.add_widget(self._weight_value_label)

        # Progress bar
        self._weight_progress = ProgressBar(
            max=100, value=0,
            size_hint_y=None, height=25,
        )
        content.add_widget(self._weight_progress)

        # Zone label
        self._weight_zone_label = Label(
            text='Pouring...',
            font_size='16sp', bold=True,
            color=(0.55, 0.60, 0.68, 1),
            size_hint_y=None, height=30,
        )
        content.add_widget(self._weight_zone_label)

        content.add_widget(Widget(size_hint_y=0.05))

        # Action buttons row
        btn_row = BoxLayout(
            spacing=10, size_hint_y=None, height=60,
            padding=[20, 0],
        )

        if is_test:
            # Simulate weight in TEST mode
            sim_btn = Button(
                text=f'SIM: Set {target:.0f}g',
                font_size='16sp', bold=True,
                background_normal='',
                background_color=(0.40, 0.28, 0.10, 1),
            )
            sim_btn.bind(on_release=lambda x: self._simulate_pour(component))
            btn_row.add_widget(sim_btn)

        # Tare button (only for base)
        if component == 'BASE':
            tare_btn = Button(
                text='TARE',
                font_size='16sp', bold=True,
                background_normal='',
                background_color=(0.20, 0.25, 0.35, 1),
            )
            tare_btn.bind(on_release=lambda x: self._tare())
            btn_row.add_widget(tare_btn)

        # Confirm button
        confirm_btn = Button(
            text='CONFIRM WEIGHT',
            font_size='16sp', bold=True,
            background_normal='',
            background_color=(0.18, 0.77, 0.71, 1),
        )
        confirm_btn.bind(on_release=lambda x: self._confirm_weight(component))
        btn_row.add_widget(confirm_btn)

        content.add_widget(btn_row)
        content.add_widget(Widget(size_hint_y=1))

    def _build_confirm_mix_ui(self, content):
        """CONFIRM_MIX: Show ratio result and confirm."""
        app = App.get_running_app()
        session = app.mixing.session

        content.add_widget(Widget(size_hint_y=0.05))

        # In-spec or out-of-spec
        if session.ratio_in_spec:
            title = Label(
                text='MIX OK',
                font_size='36sp', bold=True,
                color=(0.18, 0.77, 0.71, 1),
                size_hint_y=None, height=55,
            )
        else:
            title = Label(
                text='OUT OF SPEC',
                font_size='36sp', bold=True,
                color=(0.90, 0.22, 0.27, 1),
                size_hint_y=None, height=55,
            )
        content.add_widget(title)

        # Details
        details = (
            f'Base: {session.base_weight_actual_g:.0f} g\n'
            f'Hardener: {session.hardener_weight_actual_g:.0f} g\n'
            f'Ratio: {session.ratio_achieved:.2f}:1  (target 4.0:1)\n'
            f'Tolerance: +/-5%'
        )
        info = Label(
            text=details,
            font_size='18sp',
            color=(0.75, 0.80, 0.88, 1),
            size_hint_y=None, height=120,
            halign='center', text_size=(700, None),
        )
        content.add_widget(info)

        content.add_widget(Widget(size_hint_y=0.05))

        # Confirm button
        confirm_btn = Button(
            text='CONFIRM MIX',
            font_size='22sp', bold=True,
            background_normal='',
            background_color=(0.18, 0.77, 0.71, 1),
            size_hint=(0.7, None), height=65,
            pos_hint={'center_x': 0.5},
        )
        confirm_btn.bind(on_release=lambda x: self._confirm_mix())
        content.add_widget(confirm_btn)

        content.add_widget(Widget(size_hint_y=1))

    def _build_thinner_ui(self, content):
        """ADD_THINNER: Application method selection with thinner percentages from recipe."""
        app = App.get_running_app()
        session = app.mixing.session
        recipe = app.mixing._recipes.get(session.recipe_id) if session else None

        # Get thinner percentages from recipe (defaults if no recipe)
        pct_brush = recipe.thinner_pct_brush if recipe else 5.0
        pct_roller = recipe.thinner_pct_roller if recipe else 5.0
        pct_spray = recipe.thinner_pct_spray if recipe else 10.0

        content.add_widget(Widget(size_hint_y=0.1))

        title = Label(
            text='Add Thinner?',
            font_size='24sp', bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None, height=40,
        )
        content.add_widget(title)

        info = Label(
            text='Select application method for thinner calculation,\nor SKIP if no thinner needed.',
            font_size='16sp',
            color=(0.65, 0.70, 0.78, 1),
            size_hint_y=None, height=55,
            halign='center', text_size=(700, None),
        )
        content.add_widget(info)

        content.add_widget(Widget(size_hint_y=0.05))

        # Method buttons with actual percentages from recipe
        for label, method_key, pct in [
            (f'Brush ({pct_brush:.0f}%)', 'brush', pct_brush),
            (f'Roller ({pct_roller:.0f}%)', 'roller', pct_roller),
            (f'Spray ({pct_spray:.0f}%)', 'spray', pct_spray),
        ]:
            btn = Button(
                text=label,
                font_size='18sp', bold=True,
                background_normal='',
                background_color=(0.11, 0.29, 0.40, 1),
                size_hint=(0.7, None), height=55,
                pos_hint={'center_x': 0.5},
            )
            btn.bind(on_release=lambda x, m=method_key: self._add_thinner(m))
            content.add_widget(btn)
            content.add_widget(Widget(size_hint_y=None, height=5))

        content.add_widget(Widget(size_hint_y=0.05))

        skip_btn = Button(
            text='SKIP THINNER',
            font_size='18sp', bold=True,
            background_normal='',
            background_color=(0.20, 0.25, 0.35, 1),
            size_hint=(0.7, None), height=55,
            pos_hint={'center_x': 0.5},
        )
        skip_btn.bind(on_release=lambda x: self._skip_thinner())
        content.add_widget(skip_btn)

        content.add_widget(Widget(size_hint_y=1))

    def _build_thinner_weigh_ui(self, content, is_test):
        """ADD_THINNER (weighing sub-state): Live weight gauge for thinner pouring."""
        target = self._thinner_target_g

        title = Label(
            text='Pour THINNER',
            font_size='24sp', bold=True,
            color=(0.91, 0.77, 0.42, 1),
            size_hint_y=None, height=40,
        )
        content.add_widget(title)

        # Target info
        target_label = Label(
            text=f'Target: {target:.0f} g',
            font_size='18sp',
            color=(0.65, 0.70, 0.78, 1),
            size_hint_y=None, height=30,
        )
        content.add_widget(target_label)

        # Weight display (large number)
        self._thinner_weight_value_label = Label(
            text='0 g',
            font_size='48sp', bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None, height=70,
        )
        content.add_widget(self._thinner_weight_value_label)

        # Progress bar
        self._thinner_weight_progress = ProgressBar(
            max=100, value=0,
            size_hint_y=None, height=25,
        )
        content.add_widget(self._thinner_weight_progress)

        # Zone label
        self._thinner_weight_zone_label = Label(
            text='Pouring...',
            font_size='16sp', bold=True,
            color=(0.55, 0.60, 0.68, 1),
            size_hint_y=None, height=30,
        )
        content.add_widget(self._thinner_weight_zone_label)

        content.add_widget(Widget(size_hint_y=0.05))

        # Action buttons row
        btn_row = BoxLayout(
            spacing=10, size_hint_y=None, height=60,
            padding=[20, 0],
        )

        if is_test:
            # Simulate thinner weight in TEST mode
            sim_btn = Button(
                text=f'SIM: Set {target:.0f}g',
                font_size='16sp', bold=True,
                background_normal='',
                background_color=(0.40, 0.28, 0.10, 1),
            )
            sim_btn.bind(on_release=lambda x: self._simulate_thinner_pour())
            btn_row.add_widget(sim_btn)

        # Back button to change method
        back_btn = Button(
            text='BACK',
            font_size='16sp', bold=True,
            background_normal='',
            background_color=(0.20, 0.25, 0.35, 1),
        )
        back_btn.bind(on_release=lambda x: self._cancel_thinner_weigh())
        btn_row.add_widget(back_btn)

        # Confirm button
        confirm_btn = Button(
            text='CONFIRM WEIGHT',
            font_size='16sp', bold=True,
            background_normal='',
            background_color=(0.18, 0.77, 0.71, 1),
        )
        confirm_btn.bind(on_release=lambda x: self._confirm_thinner_weight())
        btn_row.add_widget(confirm_btn)

        content.add_widget(btn_row)
        content.add_widget(Widget(size_hint_y=1))

    def _build_pot_life_ui(self, content):
        """POT_LIFE_ACTIVE: Countdown timer."""
        content.add_widget(Widget(size_hint_y=0.05))

        title = Label(
            text='Pot-Life Timer',
            font_size='22sp', bold=True,
            color=(0.18, 0.77, 0.71, 1),
            size_hint_y=None, height=35,
        )
        content.add_widget(title)

        # Large countdown display
        self._pot_life_label = Label(
            text='08:00:00',
            font_size='52sp', bold=True,
            color=(0.18, 0.77, 0.71, 1),
            size_hint_y=None, height=80,
        )
        content.add_widget(self._pot_life_label)

        self._pot_life_status = Label(
            text='Mix is ready to use',
            font_size='16sp',
            color=(0.65, 0.70, 0.78, 1),
            size_hint_y=None, height=30,
        )
        content.add_widget(self._pot_life_status)

        # Progress bar
        self._pot_life_progress = ProgressBar(
            max=100, value=0,
            size_hint_y=None, height=20,
        )
        content.add_widget(self._pot_life_progress)

        content.add_widget(Widget(size_hint_y=0.1))

        # Return cans button
        ret_btn = Button(
            text='RETURN CANS TO SHELF',
            font_size='20sp', bold=True,
            background_normal='',
            background_color=(0.11, 0.29, 0.40, 1),
            size_hint=(0.7, None), height=65,
            pos_hint={'center_x': 0.5},
        )
        ret_btn.bind(on_release=lambda x: self._return_cans())
        content.add_widget(ret_btn)

        content.add_widget(Widget(size_hint_y=1))

    def _build_return_cans_ui(self, content, is_test):
        """RETURN_CANS: Instructions to return cans."""
        content.add_widget(Widget(size_hint_y=0.1))

        title = Label(
            text='Return Cans',
            font_size='26sp', bold=True,
            color=(0.37, 0.66, 0.83, 1),
            size_hint_y=None, height=45,
        )
        content.add_widget(title)

        instruction = Label(
            text='Return all cans to their original slots.\n[b]BASE[/b] to Slot 1\n[b]HARDENER[/b] to Slot 2\n\nLED indicators show correct positions.',
            font_size='18sp',
            color=(0.75, 0.80, 0.88, 1),
            size_hint_y=None, height=120,
            halign='center', text_size=(700, None),
            markup=True,
        )
        content.add_widget(instruction)

        content.add_widget(Widget(size_hint_y=0.05))

        if is_test:
            sim_btn = Button(
                text='SIMULATE: Return All Cans',
                font_size='17sp', bold=True,
                background_normal='',
                background_color=(0.40, 0.28, 0.10, 1),
                size_hint=(0.7, None), height=55,
                pos_hint={'center_x': 0.5},
            )
            def _on_simulate_return(btn_instance):
                btn_instance.text = '\u2713 Returning cans...'
                btn_instance.disabled = True
                self._simulate_return_cans()
            sim_btn.bind(on_release=_on_simulate_return)
            content.add_widget(sim_btn)

            content.add_widget(Widget(size_hint_y=0.03))

        complete_btn = Button(
            text='COMPLETE SESSION',
            font_size='20sp', bold=True,
            background_normal='',
            background_color=(0.18, 0.77, 0.71, 1),
            size_hint=(0.7, None), height=65,
            pos_hint={'center_x': 0.5},
        )
        complete_btn.bind(on_release=lambda x: self._complete_session())
        content.add_widget(complete_btn)

        content.add_widget(Widget(size_hint_y=1))

    def _build_complete_ui(self, content):
        """SESSION_COMPLETE: Summary."""
        content.add_widget(Widget(size_hint_y=0.1))

        title = Label(
            text='Session Complete!',
            font_size='28sp', bold=True,
            color=(0.18, 0.77, 0.71, 1),
            size_hint_y=None, height=50,
        )
        content.add_widget(title)

        info = Label(
            text='The mixing session has been logged.\nAll data saved to local database.',
            font_size='16sp',
            color=(0.65, 0.70, 0.78, 1),
            size_hint_y=None, height=60,
            halign='center', text_size=(700, None),
        )
        content.add_widget(info)

        content.add_widget(Widget(size_hint_y=0.1))

        # Buttons row
        btn_row = BoxLayout(
            spacing=15, size_hint_y=None, height=65,
            padding=[40, 0],
        )

        new_btn = Button(
            text='NEW MIX',
            font_size='20sp', bold=True,
            background_normal='',
            background_color=(0.18, 0.77, 0.71, 1),
        )
        new_btn.bind(on_release=lambda x: self._start_mix())
        btn_row.add_widget(new_btn)

        home_btn = Button(
            text='HOME',
            font_size='20sp', bold=True,
            background_normal='',
            background_color=(0.20, 0.25, 0.35, 1),
        )
        home_btn.bind(on_release=lambda x: App.get_running_app().go_back())
        btn_row.add_widget(home_btn)

        content.add_widget(btn_row)
        content.add_widget(Widget(size_hint_y=1))

    # ============================================================
    # LIVE UPDATE METHODS
    # ============================================================

    def _update_weight_display(self):
        """Update live weight gauge during pouring."""
        app = App.get_running_app()
        status = app.mixing.check_weight_target()

        if not status or not hasattr(self, '_weight_value_label'):
            return

        current = status['current_g']
        target = status['target_g']
        progress = status['progress_pct']
        zone = status['zone']

        # Update weight number
        self._weight_value_label.text = f'{current:.0f} g'

        # Update progress bar
        self._weight_progress.value = min(progress, 100)

        # Update zone label and colors
        if zone == 'pouring':
            self._weight_zone_label.text = f'Pouring... ({progress:.0f}%)'
            self._weight_zone_label.color = (0.55, 0.60, 0.68, 1)
            self._weight_value_label.color = (1, 1, 1, 1)
        elif zone == 'approaching':
            self._weight_zone_label.text = f'Almost there! ({progress:.0f}%)'
            self._weight_zone_label.color = (0.91, 0.77, 0.42, 1)
            self._weight_value_label.color = (0.91, 0.77, 0.42, 1)
        elif zone == 'in_range':
            self._weight_zone_label.text = f'IN RANGE ({progress:.0f}%)'
            self._weight_zone_label.color = (0.18, 0.77, 0.71, 1)
            self._weight_value_label.color = (0.18, 0.77, 0.71, 1)
        elif zone == 'over':
            self._weight_zone_label.text = f'OVER TARGET ({progress:.0f}%)'
            self._weight_zone_label.color = (0.90, 0.22, 0.27, 1)
            self._weight_value_label.color = (0.90, 0.22, 0.27, 1)

    def _update_thinner_weight_display(self):
        """Update live weight gauge during thinner pouring."""
        app = App.get_running_app()
        session = app.mixing.session

        if not session or not hasattr(self, '_thinner_weight_value_label'):
            return

        reading = app.weight.read_weight('mixing_scale')
        if not reading:
            return

        # Thinner weight = current total - (base + hardener)
        base_plus_hardener = session.base_weight_actual_g + session.hardener_weight_actual_g
        current_thinner = max(0.0, reading.grams - base_plus_hardener)
        target = self._thinner_target_g

        progress_pct = (current_thinner / target * 100) if target > 0 else 0
        tolerance = 5.0  # 5% tolerance for thinner

        # Determine zone
        if progress_pct < 90:
            zone = 'pouring'
        elif progress_pct < (100 - tolerance):
            zone = 'approaching'
        elif progress_pct <= (100 + tolerance):
            zone = 'in_range'
        else:
            zone = 'over'

        # Update weight number
        self._thinner_weight_value_label.text = f'{current_thinner:.0f} g'

        # Update progress bar
        self._thinner_weight_progress.value = min(progress_pct, 100)

        # Update zone label and colors
        if zone == 'pouring':
            self._thinner_weight_zone_label.text = f'Pouring... ({progress_pct:.0f}%)'
            self._thinner_weight_zone_label.color = (0.55, 0.60, 0.68, 1)
            self._thinner_weight_value_label.color = (1, 1, 1, 1)
        elif zone == 'approaching':
            self._thinner_weight_zone_label.text = f'Almost there! ({progress_pct:.0f}%)'
            self._thinner_weight_zone_label.color = (0.91, 0.77, 0.42, 1)
            self._thinner_weight_value_label.color = (0.91, 0.77, 0.42, 1)
        elif zone == 'in_range':
            self._thinner_weight_zone_label.text = f'IN RANGE ({progress_pct:.0f}%)'
            self._thinner_weight_zone_label.color = (0.18, 0.77, 0.71, 1)
            self._thinner_weight_value_label.color = (0.18, 0.77, 0.71, 1)
        elif zone == 'over':
            self._thinner_weight_zone_label.text = f'OVER TARGET ({progress_pct:.0f}%)'
            self._thinner_weight_zone_label.color = (0.90, 0.22, 0.27, 1)
            self._thinner_weight_value_label.color = (0.90, 0.22, 0.27, 1)

    def _update_pot_life_display(self):
        """Update pot-life countdown."""
        app = App.get_running_app()
        status = app.mixing.check_pot_life()

        if not status or not hasattr(self, '_pot_life_label'):
            return

        remaining = status['remaining_sec']
        elapsed_pct = status['elapsed_pct']
        expired = status['expired']

        # Format countdown
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        seconds = int(remaining % 60)
        self._pot_life_label.text = f'{hours:02d}:{minutes:02d}:{seconds:02d}'

        # Progress bar (inverted: shows time elapsed)
        self._pot_life_progress.value = elapsed_pct

        # Colors based on remaining time
        if expired:
            self._pot_life_label.color = (0.90, 0.22, 0.27, 1)
            self._pot_life_status.text = 'EXPIRED - Do not use!'
            self._pot_life_status.color = (0.90, 0.22, 0.27, 1)
        elif elapsed_pct >= 90:
            self._pot_life_label.color = (0.90, 0.22, 0.27, 1)
            self._pot_life_status.text = 'Almost expired!'
            self._pot_life_status.color = (0.90, 0.22, 0.27, 1)
        elif elapsed_pct >= 75:
            self._pot_life_label.color = (0.91, 0.77, 0.42, 1)
            self._pot_life_status.text = 'Use soon'
            self._pot_life_status.color = (0.91, 0.77, 0.42, 1)
        else:
            self._pot_life_label.color = (0.18, 0.77, 0.71, 1)
            self._pot_life_status.text = 'Mix is ready to use'
            self._pot_life_status.color = (0.65, 0.70, 0.78, 1)

    # ============================================================
    # ACTION HANDLERS
    # ============================================================

    def _start_mix(self):
        """Start a new mixing session, using Paint Now context if available."""
        app = App.get_running_app()
        ctx = app.paint_now_context

        # Determine recipe_id from context or default
        recipe_id = 'RCP-001'
        if ctx and ctx.get('recipe_id'):
            recipe_id = ctx['recipe_id']

        # Build a fallback recipe from maintenance chart data if no recipe
        # exists in the DB (e.g. cloud returned 0 recipes but has chart data)
        fallback_recipe = None
        if recipe_id not in app.mixing._recipes:
            fallback_recipe = self._build_fallback_recipe(ctx, recipe_id)

        app.inventory.active_session = True
        success = app.mixing.start_session(
            recipe_id=recipe_id,
            user_name='Crew Member',
            job_id='JOB-001',
            fallback_recipe=fallback_recipe,
        )
        if success:
            # If Paint Now provided a target weight, auto-select that amount
            if ctx and ctx.get('target_base_grams'):
                target_g = ctx['target_base_grams']
                app.mixing.show_recipe(base_amount_g=float(target_g))
            self._last_state = None  # Force UI rebuild
        else:
            # Show error to user instead of failing silently
            self._show_start_error()

    def _build_fallback_recipe(self, ctx, recipe_id):
        """Build a MixingRecipe on-the-fly from maintenance chart product data.

        Uses the paint_now_context and maintenance chart to find ratio info
        for the selected product. Falls back to sensible defaults (4:1 ratio)
        if no chart data is available.
        """
        app = App.get_running_app()
        product_name = ''
        if ctx:
            product_name = ctx.get('product_name', '')

        # Try to find ratio from maintenance chart products
        ratio_base = 4.0
        ratio_hardener = 1.0
        coverage = 6.0
        chart = app.maintenance_chart

        if chart and product_name:
            for p in chart.get('products', []):
                if p.get('name', '').upper() == product_name.upper():
                    ratio_base = float(p.get('base_ratio', 4))
                    ratio_hardener = float(p.get('hardener_ratio', 1))
                    coverage = p.get('coverage_m2_per_liter', 6.0)
                    break

        recipe_name = f'{product_name} System' if product_name else 'Generic Mix'

        return MixingRecipe(
            recipe_id=recipe_id,
            name=recipe_name,
            base_product_id='UNKNOWN-BASE',
            hardener_product_id='UNKNOWN-HARDENER',
            ratio_base=ratio_base,
            ratio_hardener=ratio_hardener,
            tolerance_pct=5.0,
            pot_life_minutes=480,
        )

    def _show_start_error(self):
        """Show a visible error message when mixing session fails to start."""
        content = self.ids.content_area
        content.clear_widgets()

        content.add_widget(Widget(size_hint_y=0.15))

        title = Label(
            text='Cannot Start Mixing',
            font_size='24sp', bold=True,
            color=(0.90, 0.22, 0.27, 1),
            size_hint_y=None, height=45,
        )
        content.add_widget(title)

        msg = Label(
            text='Failed to start mixing session.\n'
                 'A session may already be active, or\n'
                 'required data is missing.\n\n'
                 'Try going back and starting again.',
            font_size='16sp',
            color=(0.75, 0.80, 0.88, 1),
            size_hint_y=None, height=120,
            halign='center', text_size=(700, None),
        )
        content.add_widget(msg)

        content.add_widget(Widget(size_hint_y=0.05))

        retry_btn = Button(
            text='RETRY',
            font_size='20sp', bold=True,
            background_normal='',
            background_color=(0.18, 0.77, 0.71, 1),
            size_hint=(0.5, None), height=60,
            pos_hint={'center_x': 0.5},
        )
        retry_btn.bind(on_release=lambda x: self._start_mix())
        content.add_widget(retry_btn)

        home_btn = Button(
            text='GO HOME',
            font_size='18sp', bold=True,
            background_normal='',
            background_color=(0.20, 0.25, 0.35, 1),
            size_hint=(0.5, None), height=55,
            pos_hint={'center_x': 0.5},
        )
        home_btn.bind(on_release=lambda x: App.get_running_app().go_back())
        content.add_widget(home_btn)

        content.add_widget(Widget(size_hint_y=1))

    def _select_amount(self, grams):
        """Crew selected base amount."""
        app = App.get_running_app()
        app.mixing.show_recipe(base_amount_g=float(grams))
        self._last_state = None

    def _confirm_recipe(self):
        """Crew confirmed recipe, advance to pick base."""
        app = App.get_running_app()
        app.mixing.advance_to_pick_base()
        self._last_state = None

    def _simulate_pick(self, can_type):
        """TEST mode: simulate picking a can."""
        app = App.get_running_app()
        if can_type == 'BASE':
            app.rfid.remove_tag('shelf1_slot1')
            app.inventory.poll()
            app.mixing.confirm_base_picked('TAG-BASE-001')
        else:
            app.rfid.remove_tag('shelf1_slot2')
            app.inventory.poll()
            app.mixing.confirm_hardener_picked('TAG-HARD-001')
        self._last_state = None

    def _tare(self):
        """Tare the mixing scale."""
        app = App.get_running_app()
        app.weight.set_weight('mixing_scale', 200)  # Container weight
        app.mixing.tare_scale()

    def _simulate_pour(self, component):
        """TEST mode: simulate pouring to target weight."""
        app = App.get_running_app()
        session = app.mixing.session
        if component == 'BASE':
            target = session.base_weight_target_g
            app.weight.set_weight('mixing_scale', int(target + 2))
        else:
            # Hardener target on top of base
            total = session.base_weight_actual_g + session.hardener_weight_target_g
            app.weight.set_weight('mixing_scale', int(total + 1))

    def _confirm_weight(self, component):
        """Confirm the current weight reading."""
        app = App.get_running_app()
        if component == 'BASE':
            app.mixing.confirm_base_weighed()
        else:
            app.mixing.confirm_hardener_weighed()
        self._last_state = None

    def _confirm_mix(self):
        """Confirm the mix."""
        app = App.get_running_app()
        app.mixing.confirm_mix()
        self._last_state = None

    def _add_thinner(self, method):
        """User selected application method -- transition to thinner weighing screen."""
        from core.models import ApplicationMethod
        app = App.get_running_app()
        session = app.mixing.session
        recipe = app.mixing._recipes.get(session.recipe_id) if session else None

        method_map = {
            'brush': ApplicationMethod.BRUSH,
            'roller': ApplicationMethod.ROLLER,
            'spray': ApplicationMethod.SPRAY,
        }
        self._thinner_method = method_map[method]

        # Calculate target thinner weight from recipe percentages
        thinner_pct = 0.0
        if recipe:
            thinner_pct = {
                'brush': recipe.thinner_pct_brush,
                'roller': recipe.thinner_pct_roller,
                'spray': recipe.thinner_pct_spray,
            }.get(method, 0.0)

        base_actual = session.base_weight_actual_g if session else 0.0
        hardener_actual = session.hardener_weight_actual_g if session else 0.0
        self._thinner_target_g = (base_actual + hardener_actual) * (thinner_pct / 100.0)

        # Switch to weighing sub-state
        self._thinner_weighing = True
        self._last_state = None  # Force UI rebuild

    def _skip_thinner(self):
        """Skip thinner addition."""
        app = App.get_running_app()
        app.mixing.skip_thinner()
        self._thinner_weighing = False
        self._last_state = None

    def _simulate_thinner_pour(self):
        """TEST mode: simulate pouring thinner to target weight on mixing scale."""
        app = App.get_running_app()
        session = app.mixing.session
        if not session:
            return
        # Total on scale = base + hardener + thinner target
        total = session.base_weight_actual_g + session.hardener_weight_actual_g + self._thinner_target_g
        app.weight.set_weight('mixing_scale', int(total + 1))

    def _confirm_thinner_weight(self):
        """Confirm the current thinner weight reading and finalize."""
        app = App.get_running_app()
        session = app.mixing.session
        if not session:
            return

        # Read actual thinner weight from scale
        reading = app.weight.read_weight('mixing_scale')
        base_plus_hardener = session.base_weight_actual_g + session.hardener_weight_actual_g
        actual_thinner = max(0.0, reading.grams - base_plus_hardener)

        # Call engine with actual weight
        app.mixing.add_thinner(self._thinner_method, thinner_weight_g=actual_thinner)
        self._thinner_weighing = False
        self._last_state = None

    def _cancel_thinner_weigh(self):
        """Go back to method selection from thinner weighing."""
        self._thinner_weighing = False
        self._last_state = None  # Force UI rebuild

    def _return_cans(self):
        """Transition to return cans phase."""
        app = App.get_running_app()
        app.mixing.return_cans_phase()
        self._last_state = None

    def _simulate_return_cans(self):
        """TEST mode: simulate returning all cans."""
        from kivy.clock import Clock
        app = App.get_running_app()
        app.rfid.add_tag('shelf1_slot1', 'TAG-BASE-001')
        app.rfid.add_tag('shelf1_slot2', 'TAG-HARD-001')
        app.weight.set_weight('shelf1', 13800)
        app.inventory.poll()
        # Show visual feedback then complete
        Clock.schedule_once(lambda dt: self._complete_session(), 1.0)

    def _complete_session(self):
        """Complete the mixing session."""
        app = App.get_running_app()
        app.mixing.complete_session()
        app.inventory.active_session = False
        app.paint_now_context = None  # Clear Paint Now context
        self._last_state = None
