"""
Mixing Screen - Step-by-Step Mixing Wizard (2026 Redesign)

Guides the crew through the complete mixing workflow:
1. Start session with recipe (IDLE)
2. Select base amount (SELECT_PRODUCT)
3. View recipe details (SHOW_RECIPE)
4. Pick base can - LED guidance (PICK_BASE)
5. Weigh base on mixing scale - live gauge (WEIGH_BASE)
6. Pick hardener can (PICK_HARDENER)
7. Weigh hardener - ratio monitoring (WEIGH_HARDENER)
8. Confirm mix - in-spec/out-of-spec (CONFIRM_MIX)
9. Optional thinner (ADD_THINNER)
10. Pot-life countdown (POT_LIFE_ACTIVE)
11. Return cans to shelf (RETURN_CANS)
12. Session complete (SESSION_COMPLETE)

In TEST mode, each step has "Simulate" buttons to advance without real sensors.
Refresh loop: 300ms during active mixing.
"""

import time
import logging

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.progressbar import ProgressBar
from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.metrics import dp

from ui.app import DS
from core.models import MixingState, MixingRecipe, ApplicationMethod

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


def _make_btn(text, color_bg, color_text, font_size=DS.FONT_H2,
              height=DS.BTN_HEIGHT_LG, size_hint=(None, None),
              size_hint_x=None, width=None, bold=True):
    """Create a styled button with rounded card background."""
    kw = {
        'text': text,
        'font_size': font_size,
        'bold': bold,
        'background_normal': '',
        'background_color': (0, 0, 0, 0),
        'color': color_text,
        'size_hint_y': None,
        'height': dp(height),
    }
    if size_hint_x is not None:
        kw['size_hint_x'] = size_hint_x
    elif width is not None:
        kw['size_hint_x'] = None
        kw['width'] = dp(width)
    btn = Button(**kw)
    _card_bg(btn, color_bg, radius=DS.RADIUS)
    return btn


# ================================================================
# MAIN SCREEN
# ================================================================

class MixingScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._refresh_event = None
        self._last_state = None
        # Thinner weighing sub-state
        self._thinner_weighing = False
        self._thinner_method = None
        self._thinner_target_g = 0.0
        # Widget references for live updates
        self._weight_value_label = None
        self._weight_progress = None
        self._weight_zone_label = None
        self._thinner_weight_value_label = None
        self._thinner_weight_progress = None
        self._thinner_weight_zone_label = None
        self._pot_life_label = None
        self._pot_life_status = None
        self._pot_life_progress = None

    # ================================================================
    # LIFECYCLE
    # ================================================================

    def on_enter(self):
        """Start refreshing when screen is shown."""
        self._last_state = None
        self._refresh_event = Clock.schedule_interval(self._refresh, 0.3)
        self._refresh(0)

    def on_leave(self):
        """Stop refresh loop."""
        if self._refresh_event:
            self._refresh_event.cancel()
            self._refresh_event = None

    # ================================================================
    # REFRESH LOOP
    # ================================================================

    def _refresh(self, dt):
        """Update display based on current mixing state."""
        app = App.get_running_app()
        engine = app.mixing

        state = engine.current_state

        # Only rebuild UI if state changed
        if state != self._last_state:
            self._last_state = state
            # Reset thinner sub-state when leaving ADD_THINNER
            if state != MixingState.ADD_THINNER:
                self._thinner_weighing = False
            self._build_state_ui(state)

        # Live updates for weight and timer states
        if state in (MixingState.WEIGH_BASE, MixingState.WEIGH_HARDENER):
            self._update_weight_display()
        elif state == MixingState.ADD_THINNER and self._thinner_weighing:
            self._update_thinner_weight_display()
        elif state == MixingState.POT_LIFE_ACTIVE:
            self._update_pot_life_display()

    # ================================================================
    # UI CONSTRUCTION - FRAME
    # ================================================================

    def _build_state_ui(self, state):
        """Rebuild entire screen for current state."""
        self.clear_widgets()

        # Reset widget references
        self._weight_value_label = None
        self._weight_progress = None
        self._weight_zone_label = None
        self._thinner_weight_value_label = None
        self._thinner_weight_progress = None
        self._thinner_weight_zone_label = None
        self._pot_life_label = None
        self._pot_life_status = None
        self._pot_life_progress = None

        app = App.get_running_app()
        is_test = (getattr(app, 'mode', 'test') == 'test')

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
        _card_bg(back_btn, DS.BG_CARD_HOVER, radius=8)
        status_bar.add_widget(back_btn)

        status_bar.add_widget(Label(
            text='MIXING ASSISTANT', font_size=DS.FONT_H2, bold=True,
            color=DS.TEXT_PRIMARY, size_hint_x=0.5,
            halign='center', valign='middle', text_size=(dp(350), None),
        ))

        # State badge
        state_text = state.value.replace('_', ' ').upper()
        if state == MixingState.IDLE or state in (MixingState.SESSION_COMPLETE, MixingState.ABORTED):
            badge_color = DS.TEXT_MUTED
        else:
            badge_color = DS.PRIMARY

        status_bar.add_widget(Label(
            text=state_text, font_size=DS.FONT_SMALL, bold=True,
            color=badge_color, size_hint_x=0.3,
            halign='right', valign='middle', text_size=(dp(200), None),
        ))

        root.add_widget(status_bar)

        # ---- CONTENT AREA ----
        content = BoxLayout(
            orientation='vertical',
            padding=[dp(20), dp(10), dp(20), dp(15)],
            spacing=dp(10),
        )

        # Dispatch to the correct state builder
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

        root.add_widget(content)
        self.add_widget(root)

    # ================================================================
    # STATE: IDLE
    # ================================================================

    def _build_idle_ui(self, content, is_test):
        """IDLE: Show start button, with Paint Now context info if available."""
        app = App.get_running_app()
        ctx = getattr(app, 'paint_now_context', None)

        content.add_widget(Widget(size_hint_y=0.1))

        if ctx:
            area = ctx.get('area_name', '')
            product = ctx.get('product_name', '')
            color = ctx.get('color', '')
            target_g = ctx.get('target_base_grams')
            m2 = ctx.get('m2')

            content.add_widget(Label(
                text='Ready to Mix', font_size='24sp', bold=True,
                color=DS.PRIMARY, size_hint_y=None, height=dp(40),
            ))

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
                # Context info card
                info_card = BoxLayout(
                    orientation='vertical',
                    size_hint=(0.9, None),
                    height=dp(len(info_lines) * 26 + 16),
                    pos_hint={'center_x': 0.5},
                    padding=[dp(16), dp(8)],
                )
                _card_bg(info_card, DS.BG_CARD, radius=DS.RADIUS)
                info_card.add_widget(Label(
                    text='\n'.join(info_lines),
                    font_size='16sp', color=(0.85, 0.88, 0.95, 1),
                    size_hint_y=None, height=dp(len(info_lines) * 26),
                    halign='center', text_size=(dp(600), None), markup=True,
                ))
                content.add_widget(info_card)

            content.add_widget(Widget(size_hint_y=0.05))

            btn = _make_btn('START MIXING', DS.PRIMARY, (0.02, 0.05, 0.08, 1),
                            font_size='24sp', height=DS.BTN_HEIGHT_LG)
            btn.size_hint_x = 0.7
            btn.pos_hint = {'center_x': 0.5}
            btn.bind(on_release=lambda x: self._start_mix())
            content.add_widget(btn)
        else:
            content.add_widget(Label(
                text='Ready to Mix', font_size='28sp', bold=True,
                color=(1, 1, 1, 1), size_hint_y=None, height=dp(50),
            ))
            content.add_widget(Label(
                text='Tap START to begin a guided mixing session.\n'
                     'The system will show you which cans to pick\n'
                     'and how much to pour.',
                font_size='16sp', color=DS.TEXT_SECONDARY,
                size_hint_y=None, height=dp(80),
                halign='center', text_size=(dp(700), None),
            ))
            content.add_widget(Widget(size_hint_y=0.1))

            btn = _make_btn('START NEW MIX', DS.PRIMARY, (0.02, 0.05, 0.08, 1),
                            font_size='24sp', height=DS.BTN_HEIGHT_LG)
            btn.size_hint_x = 0.7
            btn.pos_hint = {'center_x': 0.5}
            btn.bind(on_release=lambda x: self._start_mix())
            content.add_widget(btn)

        content.add_widget(Widget(size_hint_y=1))

    # ================================================================
    # STATE: SELECT_PRODUCT
    # ================================================================

    def _build_select_product_ui(self, content):
        """SELECT_PRODUCT: Show recipe selection and amount buttons."""
        content.add_widget(Widget(size_hint_y=0.1))

        content.add_widget(Label(
            text='Select Amount', font_size='24sp', bold=True,
            color=(1, 1, 1, 1), size_hint_y=None, height=dp(45),
        ))

        app = App.get_running_app()
        ctx = getattr(app, 'paint_now_context', None)

        # Get recipe name
        recipe_name = 'Mix System'
        if app.mixing.session and app.mixing.session.recipe_id:
            recipes = getattr(app.mixing, '_recipes', {})
            recipe = recipes.get(app.mixing.session.recipe_id)
            if recipe:
                recipe_name = recipe.name

        info_text = f'Recipe: {recipe_name}\n\nHow much BASE do you want to mix?'
        if ctx and ctx.get('product_name'):
            info_text = (
                f'Product: {ctx["product_name"]}\n'
                f'Recipe: {recipe_name}\n\n'
                f'How much BASE do you want to mix?'
            )

        content.add_widget(Label(
            text=info_text, font_size='16sp', color=DS.TEXT_SECONDARY,
            size_hint_y=None, height=dp(100),
            halign='center', text_size=(dp(700), None), markup=True,
        ))

        # Quick-select amount buttons
        amounts_row = BoxLayout(
            spacing=dp(10), size_hint_y=None, height=dp(70),
            padding=[dp(50), 0],
        )
        for amount in [250, 500, 1000, 2000]:
            btn = _make_btn(
                f'{amount}g', DS.BG_CARD, DS.TEXT_PRIMARY,
                font_size=DS.FONT_H2, height=70,
            )
            btn.size_hint_x = 0.25
            btn.bind(on_release=lambda x, a=amount: self._select_amount(a))
            amounts_row.add_widget(btn)
        content.add_widget(amounts_row)

        content.add_widget(Widget(size_hint_y=1))

    # ================================================================
    # STATE: SHOW_RECIPE
    # ================================================================

    def _build_show_recipe_ui(self, content):
        """SHOW_RECIPE: Display calculated amounts."""
        app = App.get_running_app()
        session = app.mixing.session
        recipe = app.mixing._recipes.get(session.recipe_id) if session else None

        content.add_widget(Widget(size_hint_y=0.05))

        content.add_widget(Label(
            text='Recipe Ready', font_size='24sp', bold=True,
            color=DS.PRIMARY, size_hint_y=None, height=dp(40),
        ))

        # Recipe details card
        ratio_str = f'{recipe.ratio_base:.0f}:{recipe.ratio_hardener:.0f}' if recipe else '4:1'
        pot_life_str = f'{recipe.pot_life_minutes // 60}h' if recipe else '8h'

        info_card = BoxLayout(
            orientation='vertical',
            size_hint=(0.85, None), height=dp(140),
            pos_hint={'center_x': 0.5},
            padding=[dp(20), dp(12)], spacing=dp(6),
        )
        _card_bg(info_card, DS.BG_CARD, radius=DS.RADIUS)

        details = [
            ('Base', f'{session.base_weight_target_g:.0f} g'),
            ('Hardener', f'{session.hardener_weight_target_g:.0f} g'),
            ('Ratio', ratio_str),
            ('Pot Life', pot_life_str),
        ]
        for label_txt, value_txt in details:
            row = BoxLayout(size_hint_y=None, height=dp(26))
            row.add_widget(Label(
                text=label_txt, font_size=DS.FONT_H3, bold=True,
                color=DS.TEXT_SECONDARY, halign='right',
                text_size=(dp(150), None), size_hint_x=0.4,
            ))
            row.add_widget(Label(
                text=value_txt, font_size=DS.FONT_H2, bold=True,
                color=DS.TEXT_PRIMARY, halign='left',
                text_size=(dp(200), None), size_hint_x=0.6,
            ))
            info_card.add_widget(row)

        content.add_widget(info_card)
        content.add_widget(Widget(size_hint_y=0.05))

        btn = _make_btn('CONFIRM  -  PICK BASE CAN', DS.PRIMARY, (0.02, 0.05, 0.08, 1),
                        font_size=DS.FONT_H2, height=DS.BTN_HEIGHT_LG)
        btn.size_hint_x = 0.8
        btn.pos_hint = {'center_x': 0.5}
        btn.bind(on_release=lambda x: self._confirm_recipe())
        content.add_widget(btn)

        content.add_widget(Widget(size_hint_y=1))

    # ================================================================
    # STATE: PICK_BASE / PICK_HARDENER
    # ================================================================

    def _build_pick_can_ui(self, content, can_type, is_test):
        """PICK_BASE or PICK_HARDENER: Show pick instructions with LED guidance."""
        content.add_widget(Widget(size_hint_y=0.1))

        can_color = DS.SECONDARY
        content.add_widget(Label(
            text=f'Pick {can_type} Can', font_size='26sp', bold=True,
            color=can_color, size_hint_y=None, height=dp(45),
        ))

        slot_num = 1 if can_type == 'BASE' else 2
        content.add_widget(Label(
            text=f'Remove the {can_type} can from\n[b]SLOT {slot_num}[/b] (LED is lit green)',
            font_size=DS.FONT_H2, color=(0.75, 0.80, 0.88, 1),
            size_hint_y=None, height=dp(70),
            halign='center', text_size=(dp(700), None), markup=True,
        ))

        content.add_widget(Widget(size_hint_y=0.1))

        if is_test:
            sim_btn = _make_btn(
                f'SIMULATE: Remove {can_type} from Slot {slot_num}',
                DS.ACCENT_DIM, DS.TEXT_PRIMARY,
                font_size=DS.FONT_H3, height=DS.BTN_HEIGHT_LG,
            )
            sim_btn.size_hint_x = 0.8
            sim_btn.pos_hint = {'center_x': 0.5}
            sim_btn.bind(on_release=lambda x: self._simulate_pick(can_type))
            content.add_widget(sim_btn)

        content.add_widget(Label(
            text='Waiting for RFID detection...',
            font_size='14sp', color=DS.TEXT_MUTED,
            size_hint_y=None, height=dp(30),
        ))

        content.add_widget(Widget(size_hint_y=1))

    # ================================================================
    # STATE: WEIGH_BASE / WEIGH_HARDENER
    # ================================================================

    def _build_weigh_ui(self, content, component, is_test):
        """WEIGH_BASE or WEIGH_HARDENER: Live weight gauge."""
        app = App.get_running_app()
        session = app.mixing.session

        target = (session.base_weight_target_g if component == 'BASE'
                  else session.hardener_weight_target_g)

        content.add_widget(Label(
            text=f'Pour {component}', font_size='24sp', bold=True,
            color=DS.SECONDARY, size_hint_y=None, height=dp(40),
        ))

        content.add_widget(Label(
            text=f'Target: {target:.0f} g', font_size=DS.FONT_H2,
            color=DS.TEXT_SECONDARY, size_hint_y=None, height=dp(30),
        ))

        # Large weight display
        self._weight_value_label = Label(
            text='0 g', font_size=DS.FONT_HERO, bold=True,
            color=(1, 1, 1, 1), size_hint_y=None, height=dp(70),
        )
        content.add_widget(self._weight_value_label)

        # Progress bar
        self._weight_progress = ProgressBar(
            max=100, value=0, size_hint_y=None, height=dp(25),
        )
        content.add_widget(self._weight_progress)

        # Zone label
        self._weight_zone_label = Label(
            text='Pouring...', font_size='16sp', bold=True,
            color=DS.TEXT_MUTED, size_hint_y=None, height=dp(30),
        )
        content.add_widget(self._weight_zone_label)

        content.add_widget(Widget(size_hint_y=0.05))

        # Action buttons row
        btn_row = BoxLayout(
            spacing=dp(10), size_hint_y=None, height=dp(60),
            padding=[dp(20), 0],
        )

        if is_test:
            sim_btn = _make_btn(
                f'SIM: Set {target:.0f}g', DS.ACCENT_DIM, DS.TEXT_PRIMARY,
                font_size='16sp', height=60,
            )
            sim_btn.size_hint_x = 0.3
            sim_btn.bind(on_release=lambda x: self._simulate_pour(component))
            btn_row.add_widget(sim_btn)

        if component == 'BASE':
            tare_btn = _make_btn(
                'TARE', DS.BG_CARD_HOVER, DS.TEXT_PRIMARY,
                font_size='16sp', height=60,
            )
            tare_btn.size_hint_x = 0.25
            tare_btn.bind(on_release=lambda x: self._tare())
            btn_row.add_widget(tare_btn)

        confirm_btn = _make_btn(
            'CONFIRM WEIGHT', DS.PRIMARY, (0.02, 0.05, 0.08, 1),
            font_size='16sp', height=60,
        )
        confirm_btn.size_hint_x = 0.45 if is_test else 0.6
        confirm_btn.bind(on_release=lambda x: self._confirm_weight(component))
        btn_row.add_widget(confirm_btn)

        content.add_widget(btn_row)
        content.add_widget(Widget(size_hint_y=1))

    # ================================================================
    # STATE: CONFIRM_MIX
    # ================================================================

    def _build_confirm_mix_ui(self, content):
        """CONFIRM_MIX: Show ratio result and confirm."""
        app = App.get_running_app()
        session = app.mixing.session
        recipe = app.mixing._recipes.get(session.recipe_id) if session else None

        content.add_widget(Widget(size_hint_y=0.05))

        if session.ratio_in_spec:
            content.add_widget(Label(
                text='MIX OK', font_size='36sp', bold=True,
                color=DS.SUCCESS, size_hint_y=None, height=dp(55),
            ))
        else:
            content.add_widget(Label(
                text='OUT OF SPEC', font_size='36sp', bold=True,
                color=DS.DANGER, size_hint_y=None, height=dp(55),
            ))

        # Details card
        target_ratio = f'{recipe.ratio_base:.0f}:{recipe.ratio_hardener:.0f}' if recipe else '4:1'
        tolerance = f'{recipe.tolerance_pct:.0f}' if recipe else '5'

        details_card = BoxLayout(
            orientation='vertical',
            size_hint=(0.85, None), height=dp(120),
            pos_hint={'center_x': 0.5},
            padding=[dp(16), dp(10)], spacing=dp(4),
        )
        _card_bg(details_card, DS.BG_CARD, radius=DS.RADIUS)

        detail_lines = [
            f'[b]Base:[/b]  {session.base_weight_actual_g:.0f} g',
            f'[b]Hardener:[/b]  {session.hardener_weight_actual_g:.0f} g',
            f'[b]Ratio:[/b]  {session.ratio_achieved:.2f}:1  (target {target_ratio})',
            f'[b]Tolerance:[/b]  +/-{tolerance}%',
        ]
        for line in detail_lines:
            details_card.add_widget(Label(
                text=line, font_size=DS.FONT_H3,
                color=(0.75, 0.80, 0.88, 1),
                size_hint_y=None, height=dp(24),
                halign='center', text_size=(dp(600), None), markup=True,
            ))

        content.add_widget(details_card)
        content.add_widget(Widget(size_hint_y=0.05))

        confirm_btn = _make_btn(
            'CONFIRM MIX', DS.PRIMARY, (0.02, 0.05, 0.08, 1),
            font_size='22sp', height=DS.BTN_HEIGHT_LG,
        )
        confirm_btn.size_hint_x = 0.7
        confirm_btn.pos_hint = {'center_x': 0.5}
        confirm_btn.bind(on_release=lambda x: self._confirm_mix())
        content.add_widget(confirm_btn)

        content.add_widget(Widget(size_hint_y=1))

    # ================================================================
    # STATE: ADD_THINNER (method selection)
    # ================================================================

    def _build_thinner_ui(self, content):
        """ADD_THINNER: Application method selection with thinner percentages."""
        app = App.get_running_app()
        session = app.mixing.session
        recipe = app.mixing._recipes.get(session.recipe_id) if session else None

        pct_brush = recipe.thinner_pct_brush if recipe else 5.0
        pct_roller = recipe.thinner_pct_roller if recipe else 5.0
        pct_spray = recipe.thinner_pct_spray if recipe else 10.0

        content.add_widget(Widget(size_hint_y=0.1))

        content.add_widget(Label(
            text='Add Thinner?', font_size='24sp', bold=True,
            color=(1, 1, 1, 1), size_hint_y=None, height=dp(40),
        ))

        content.add_widget(Label(
            text='Select application method for thinner calculation,\nor SKIP if no thinner needed.',
            font_size='16sp', color=DS.TEXT_SECONDARY,
            size_hint_y=None, height=dp(55),
            halign='center', text_size=(dp(700), None),
        ))

        content.add_widget(Widget(size_hint_y=0.05))

        for label_txt, method_key, pct in [
            (f'Brush ({pct_brush:.0f}%)', 'brush', pct_brush),
            (f'Roller ({pct_roller:.0f}%)', 'roller', pct_roller),
            (f'Spray ({pct_spray:.0f}%)', 'spray', pct_spray),
        ]:
            btn = _make_btn(
                label_txt, DS.BG_CARD, DS.TEXT_PRIMARY,
                font_size=DS.FONT_H2, height=DS.BTN_HEIGHT_MD,
            )
            btn.size_hint_x = 0.7
            btn.pos_hint = {'center_x': 0.5}
            btn.bind(on_release=lambda x, m=method_key: self._add_thinner(m))
            content.add_widget(btn)
            content.add_widget(Widget(size_hint_y=None, height=dp(5)))

        content.add_widget(Widget(size_hint_y=0.05))

        skip_btn = _make_btn(
            'SKIP THINNER', DS.BG_CARD_HOVER, DS.TEXT_SECONDARY,
            font_size=DS.FONT_H2, height=DS.BTN_HEIGHT_MD,
        )
        skip_btn.size_hint_x = 0.7
        skip_btn.pos_hint = {'center_x': 0.5}
        skip_btn.bind(on_release=lambda x: self._skip_thinner())
        content.add_widget(skip_btn)

        content.add_widget(Widget(size_hint_y=1))

    # ================================================================
    # STATE: ADD_THINNER (weighing sub-state)
    # ================================================================

    def _build_thinner_weigh_ui(self, content, is_test):
        """ADD_THINNER weighing: Live weight gauge for thinner pouring."""
        target = self._thinner_target_g

        content.add_widget(Label(
            text='Pour THINNER', font_size='24sp', bold=True,
            color=DS.WARNING, size_hint_y=None, height=dp(40),
        ))

        content.add_widget(Label(
            text=f'Target: {target:.0f} g', font_size=DS.FONT_H2,
            color=DS.TEXT_SECONDARY, size_hint_y=None, height=dp(30),
        ))

        self._thinner_weight_value_label = Label(
            text='0 g', font_size=DS.FONT_HERO, bold=True,
            color=(1, 1, 1, 1), size_hint_y=None, height=dp(70),
        )
        content.add_widget(self._thinner_weight_value_label)

        self._thinner_weight_progress = ProgressBar(
            max=100, value=0, size_hint_y=None, height=dp(25),
        )
        content.add_widget(self._thinner_weight_progress)

        self._thinner_weight_zone_label = Label(
            text='Pouring...', font_size='16sp', bold=True,
            color=DS.TEXT_MUTED, size_hint_y=None, height=dp(30),
        )
        content.add_widget(self._thinner_weight_zone_label)

        content.add_widget(Widget(size_hint_y=0.05))

        btn_row = BoxLayout(
            spacing=dp(10), size_hint_y=None, height=dp(60),
            padding=[dp(20), 0],
        )

        if is_test:
            sim_btn = _make_btn(
                f'SIM: Set {target:.0f}g', DS.ACCENT_DIM, DS.TEXT_PRIMARY,
                font_size='16sp', height=60,
            )
            sim_btn.size_hint_x = 0.3
            sim_btn.bind(on_release=lambda x: self._simulate_thinner_pour())
            btn_row.add_widget(sim_btn)

        back_btn = _make_btn(
            'BACK', DS.BG_CARD_HOVER, DS.TEXT_PRIMARY,
            font_size='16sp', height=60,
        )
        back_btn.size_hint_x = 0.25
        back_btn.bind(on_release=lambda x: self._cancel_thinner_weigh())
        btn_row.add_widget(back_btn)

        confirm_btn = _make_btn(
            'CONFIRM WEIGHT', DS.PRIMARY, (0.02, 0.05, 0.08, 1),
            font_size='16sp', height=60,
        )
        confirm_btn.size_hint_x = 0.45
        confirm_btn.bind(on_release=lambda x: self._confirm_thinner_weight())
        btn_row.add_widget(confirm_btn)

        content.add_widget(btn_row)
        content.add_widget(Widget(size_hint_y=1))

    # ================================================================
    # STATE: POT_LIFE_ACTIVE
    # ================================================================

    def _build_pot_life_ui(self, content):
        """POT_LIFE_ACTIVE: Countdown timer."""
        content.add_widget(Widget(size_hint_y=0.05))

        content.add_widget(Label(
            text='Pot-Life Timer', font_size='22sp', bold=True,
            color=DS.PRIMARY, size_hint_y=None, height=dp(35),
        ))

        # Large countdown display
        self._pot_life_label = Label(
            text='08:00:00', font_size='52sp', bold=True,
            color=DS.PRIMARY, size_hint_y=None, height=dp(80),
        )
        content.add_widget(self._pot_life_label)

        self._pot_life_status = Label(
            text='Mix is ready to use', font_size='16sp',
            color=DS.TEXT_SECONDARY, size_hint_y=None, height=dp(30),
        )
        content.add_widget(self._pot_life_status)

        self._pot_life_progress = ProgressBar(
            max=100, value=0, size_hint_y=None, height=dp(20),
        )
        content.add_widget(self._pot_life_progress)

        content.add_widget(Widget(size_hint_y=0.1))

        ret_btn = _make_btn(
            'RETURN CANS TO SHELF', DS.BG_CARD, DS.TEXT_PRIMARY,
            font_size=DS.FONT_H2, height=DS.BTN_HEIGHT_LG,
        )
        ret_btn.size_hint_x = 0.7
        ret_btn.pos_hint = {'center_x': 0.5}
        ret_btn.bind(on_release=lambda x: self._return_cans())
        content.add_widget(ret_btn)

        content.add_widget(Widget(size_hint_y=1))

    # ================================================================
    # STATE: RETURN_CANS
    # ================================================================

    def _build_return_cans_ui(self, content, is_test):
        """RETURN_CANS: Instructions to return cans."""
        content.add_widget(Widget(size_hint_y=0.1))

        content.add_widget(Label(
            text='Return Cans', font_size='26sp', bold=True,
            color=DS.SECONDARY, size_hint_y=None, height=dp(45),
        ))

        content.add_widget(Label(
            text='Return all cans to their original slots.\n'
                 '[b]BASE[/b] to Slot 1\n'
                 '[b]HARDENER[/b] to Slot 2\n\n'
                 'LED indicators show correct positions.',
            font_size=DS.FONT_H2, color=(0.75, 0.80, 0.88, 1),
            size_hint_y=None, height=dp(120),
            halign='center', text_size=(dp(700), None), markup=True,
        ))

        content.add_widget(Widget(size_hint_y=0.05))

        if is_test:
            sim_btn = _make_btn(
                'SIMULATE: Return All Cans', DS.ACCENT_DIM, DS.TEXT_PRIMARY,
                font_size=DS.FONT_H3, height=DS.BTN_HEIGHT_MD,
            )
            sim_btn.size_hint_x = 0.7
            sim_btn.pos_hint = {'center_x': 0.5}

            def _on_simulate_return(btn_instance):
                btn_instance.text = 'Returning cans...'
                btn_instance.disabled = True
                self._simulate_return_cans()

            sim_btn.bind(on_release=_on_simulate_return)
            content.add_widget(sim_btn)
            content.add_widget(Widget(size_hint_y=0.03))

        complete_btn = _make_btn(
            'COMPLETE SESSION', DS.PRIMARY, (0.02, 0.05, 0.08, 1),
            font_size=DS.FONT_H2, height=DS.BTN_HEIGHT_LG,
        )
        complete_btn.size_hint_x = 0.7
        complete_btn.pos_hint = {'center_x': 0.5}
        complete_btn.bind(on_release=lambda x: self._complete_session())
        content.add_widget(complete_btn)

        content.add_widget(Widget(size_hint_y=1))

    # ================================================================
    # STATE: SESSION_COMPLETE
    # ================================================================

    def _build_complete_ui(self, content):
        """SESSION_COMPLETE: Summary."""
        content.add_widget(Widget(size_hint_y=0.1))

        content.add_widget(Label(
            text='Session Complete!', font_size='28sp', bold=True,
            color=DS.SUCCESS, size_hint_y=None, height=dp(50),
        ))

        content.add_widget(Label(
            text='The mixing session has been logged.\nAll data saved to local database.',
            font_size='16sp', color=DS.TEXT_SECONDARY,
            size_hint_y=None, height=dp(60),
            halign='center', text_size=(dp(700), None),
        ))

        content.add_widget(Widget(size_hint_y=0.1))

        btn_row = BoxLayout(
            spacing=dp(15), size_hint_y=None, height=dp(DS.BTN_HEIGHT_LG),
            padding=[dp(40), 0],
        )

        new_btn = _make_btn(
            'NEW MIX', DS.PRIMARY, (0.02, 0.05, 0.08, 1),
            font_size=DS.FONT_H2, height=DS.BTN_HEIGHT_LG,
        )
        new_btn.size_hint_x = 0.5
        new_btn.bind(on_release=lambda x: self._start_mix())
        btn_row.add_widget(new_btn)

        home_btn = _make_btn(
            'HOME', DS.BG_CARD_HOVER, DS.TEXT_SECONDARY,
            font_size=DS.FONT_H2, height=DS.BTN_HEIGHT_LG,
        )
        home_btn.size_hint_x = 0.5
        home_btn.bind(on_release=lambda x: App.get_running_app().go_back())
        btn_row.add_widget(home_btn)

        content.add_widget(btn_row)
        content.add_widget(Widget(size_hint_y=1))

    # ================================================================
    # LIVE UPDATE METHODS
    # ================================================================

    def _update_weight_display(self):
        """Update live weight gauge during pouring."""
        app = App.get_running_app()
        try:
            status = app.mixing.check_weight_target()
        except Exception:
            return

        if not status or not self._weight_value_label:
            return

        current = status['current_g']
        target = status['target_g']
        progress = status['progress_pct']
        zone = status['zone']

        self._weight_value_label.text = f'{current:.0f} g'
        self._weight_progress.value = min(progress, 100)

        zone_config = {
            'pouring': (f'Pouring... ({progress:.0f}%)', DS.TEXT_MUTED, (1, 1, 1, 1)),
            'approaching': (f'Almost there! ({progress:.0f}%)', DS.WARNING, DS.WARNING),
            'in_range': (f'IN RANGE ({progress:.0f}%)', DS.SUCCESS, DS.SUCCESS),
            'over': (f'OVER TARGET ({progress:.0f}%)', DS.DANGER, DS.DANGER),
        }
        zone_text, zone_color, weight_color = zone_config.get(
            zone, (f'{progress:.0f}%', DS.TEXT_MUTED, (1, 1, 1, 1)))

        self._weight_zone_label.text = zone_text
        self._weight_zone_label.color = zone_color
        self._weight_value_label.color = weight_color

    def _update_thinner_weight_display(self):
        """Update live weight gauge during thinner pouring."""
        app = App.get_running_app()
        session = app.mixing.session

        if not session or not self._thinner_weight_value_label:
            return

        try:
            reading = app.weight.read_weight('mixing_scale')
        except Exception:
            return
        if not reading:
            return

        base_plus_hardener = session.base_weight_actual_g + session.hardener_weight_actual_g
        current_thinner = max(0.0, reading.grams - base_plus_hardener)
        target = self._thinner_target_g

        progress_pct = (current_thinner / target * 100) if target > 0 else 0
        tolerance = 5.0

        if progress_pct < 90:
            zone = 'pouring'
        elif progress_pct < (100 - tolerance):
            zone = 'approaching'
        elif progress_pct <= (100 + tolerance):
            zone = 'in_range'
        else:
            zone = 'over'

        self._thinner_weight_value_label.text = f'{current_thinner:.0f} g'
        self._thinner_weight_progress.value = min(progress_pct, 100)

        zone_config = {
            'pouring': (f'Pouring... ({progress_pct:.0f}%)', DS.TEXT_MUTED, (1, 1, 1, 1)),
            'approaching': (f'Almost there! ({progress_pct:.0f}%)', DS.WARNING, DS.WARNING),
            'in_range': (f'IN RANGE ({progress_pct:.0f}%)', DS.SUCCESS, DS.SUCCESS),
            'over': (f'OVER TARGET ({progress_pct:.0f}%)', DS.DANGER, DS.DANGER),
        }
        zone_text, zone_color, weight_color = zone_config.get(
            zone, (f'{progress_pct:.0f}%', DS.TEXT_MUTED, (1, 1, 1, 1)))

        self._thinner_weight_zone_label.text = zone_text
        self._thinner_weight_zone_label.color = zone_color
        self._thinner_weight_value_label.color = weight_color

    def _update_pot_life_display(self):
        """Update pot-life countdown."""
        app = App.get_running_app()
        try:
            status = app.mixing.check_pot_life()
        except Exception:
            return

        if not status or not self._pot_life_label:
            return

        remaining = status['remaining_sec']
        elapsed_pct = status['elapsed_pct']
        expired = status['expired']

        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        seconds = int(remaining % 60)
        self._pot_life_label.text = f'{hours:02d}:{minutes:02d}:{seconds:02d}'

        self._pot_life_progress.value = elapsed_pct

        if expired:
            self._pot_life_label.color = DS.DANGER
            self._pot_life_status.text = 'EXPIRED - Do not use!'
            self._pot_life_status.color = DS.DANGER
        elif elapsed_pct >= 90:
            self._pot_life_label.color = DS.DANGER
            self._pot_life_status.text = 'Almost expired!'
            self._pot_life_status.color = DS.DANGER
        elif elapsed_pct >= 75:
            self._pot_life_label.color = DS.WARNING
            self._pot_life_status.text = 'Use soon'
            self._pot_life_status.color = DS.WARNING
        else:
            self._pot_life_label.color = DS.PRIMARY
            self._pot_life_status.text = 'Mix is ready to use'
            self._pot_life_status.color = DS.TEXT_SECONDARY

    # ================================================================
    # ACTION HANDLERS
    # ================================================================

    def _start_mix(self):
        """Start a new mixing session, using Paint Now context if available."""
        app = App.get_running_app()
        ctx = getattr(app, 'paint_now_context', None)

        recipe_id = 'RCP-001'
        if ctx and ctx.get('recipe_id'):
            recipe_id = ctx['recipe_id']

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
            if ctx and ctx.get('target_base_grams'):
                target_g = ctx['target_base_grams']
                app.mixing.show_recipe(base_amount_g=float(target_g))
            self._last_state = None  # Force UI rebuild
        else:
            self._show_start_error()

    def _build_fallback_recipe(self, ctx, recipe_id):
        """Build a MixingRecipe on-the-fly from maintenance chart product data."""
        app = App.get_running_app()
        product_name = ''
        if ctx:
            product_name = ctx.get('product_name', '')

        ratio_base = 4.0
        ratio_hardener = 1.0
        chart = getattr(app, 'maintenance_chart', None)

        if chart and product_name:
            for p in chart.get('products', []):
                if p.get('name', '').upper() == product_name.upper():
                    ratio_base = float(p.get('base_ratio', 4))
                    ratio_hardener = float(p.get('hardener_ratio', 1))
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
        self.clear_widgets()

        root = BoxLayout(orientation='vertical')
        with root.canvas.before:
            Color(*DS.BG_DARK)
            root_bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(
            pos=lambda w, p: setattr(root_bg, 'pos', p),
            size=lambda w, s: setattr(root_bg, 'size', s),
        )

        content = BoxLayout(
            orientation='vertical',
            padding=[dp(20), dp(10), dp(20), dp(15)],
            spacing=dp(10),
        )

        content.add_widget(Widget(size_hint_y=0.15))

        content.add_widget(Label(
            text='Cannot Start Mixing', font_size='24sp', bold=True,
            color=DS.DANGER, size_hint_y=None, height=dp(45),
        ))

        content.add_widget(Label(
            text='Failed to start mixing session.\n'
                 'A session may already be active, or\n'
                 'required data is missing.\n\n'
                 'Try going back and starting again.',
            font_size='16sp', color=(0.75, 0.80, 0.88, 1),
            size_hint_y=None, height=dp(120),
            halign='center', text_size=(dp(700), None),
        ))

        content.add_widget(Widget(size_hint_y=0.05))

        retry_btn = _make_btn(
            'RETRY', DS.PRIMARY, (0.02, 0.05, 0.08, 1),
            font_size=DS.FONT_H2, height=60,
        )
        retry_btn.size_hint_x = 0.5
        retry_btn.pos_hint = {'center_x': 0.5}
        retry_btn.bind(on_release=lambda x: self._start_mix())
        content.add_widget(retry_btn)

        home_btn = _make_btn(
            'GO HOME', DS.BG_CARD_HOVER, DS.TEXT_SECONDARY,
            font_size=DS.FONT_H2, height=DS.BTN_HEIGHT_MD,
        )
        home_btn.size_hint_x = 0.5
        home_btn.pos_hint = {'center_x': 0.5}
        home_btn.bind(on_release=lambda x: App.get_running_app().go_back())
        content.add_widget(home_btn)

        content.add_widget(Widget(size_hint_y=1))
        root.add_widget(content)
        self.add_widget(root)

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
        """User selected application method -- transition to thinner weighing."""
        app = App.get_running_app()
        session = app.mixing.session
        recipe = app.mixing._recipes.get(session.recipe_id) if session else None

        method_map = {
            'brush': ApplicationMethod.BRUSH,
            'roller': ApplicationMethod.ROLLER,
            'spray': ApplicationMethod.SPRAY,
        }
        self._thinner_method = method_map[method]

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

        self._thinner_weighing = True
        self._last_state = None  # Force UI rebuild

    def _skip_thinner(self):
        """Skip thinner addition."""
        app = App.get_running_app()
        app.mixing.skip_thinner()
        self._thinner_weighing = False
        self._last_state = None

    def _simulate_thinner_pour(self):
        """TEST mode: simulate pouring thinner to target weight."""
        app = App.get_running_app()
        session = app.mixing.session
        if not session:
            return
        total = (session.base_weight_actual_g + session.hardener_weight_actual_g
                 + self._thinner_target_g)
        app.weight.set_weight('mixing_scale', int(total + 1))

    def _confirm_thinner_weight(self):
        """Confirm the current thinner weight reading and finalize."""
        app = App.get_running_app()
        session = app.mixing.session
        if not session:
            return

        try:
            reading = app.weight.read_weight('mixing_scale')
            base_plus_hardener = session.base_weight_actual_g + session.hardener_weight_actual_g
            actual_thinner = max(0.0, reading.grams - base_plus_hardener)
        except Exception:
            actual_thinner = 0.0

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
        app = App.get_running_app()
        app.rfid.add_tag('shelf1_slot1', 'TAG-BASE-001')
        app.rfid.add_tag('shelf1_slot2', 'TAG-HARD-001')
        app.weight.set_weight('shelf1', 13800)
        app.inventory.poll()
        Clock.schedule_once(lambda dt: self._complete_session(), 1.0)

    def _complete_session(self):
        """Complete the mixing session."""
        app = App.get_running_app()
        app.mixing.complete_session()
        app.inventory.active_session = False
        app.paint_now_context = None  # Clear Paint Now context
        self._last_state = None
