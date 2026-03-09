"""
Virtual Keyboard - Touchscreen input for SmartLocker.

Two modes:
- NUMERIC: 0-9, backspace, enter (for pairing codes)
- ALPHA: Full QWERTY with shift (for admin screens)

Designed for 800x480 touchscreen with large keys (60dp) for gloved hands.
Dark theme matching the SmartLocker design system.

Usage:
    from ui.widgets.virtual_keyboard import VirtualKeyboard

    kb = VirtualKeyboard(mode='numeric')
    kb.bind_to(some_text_input)
    layout.add_widget(kb)

    # Switch modes at runtime
    kb.mode = 'alpha'

    # Show/hide
    kb.show()
    kb.hide()
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.lang import Builder
from kivy.properties import (
    ObjectProperty, StringProperty, BooleanProperty, NumericProperty,
)
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.animation import Animation


# ============================================================
# KV STYLING
# ============================================================

Builder.load_string('''
<KeyButton>:
    background_normal: ''
    background_color: 0, 0, 0, 0
    color: 0.96, 0.97, 0.98, 1
    font_size: '20sp'
    bold: True
    size_hint_y: None
    height: '52dp'
    canvas.before:
        Color:
            rgba: self._key_bg
        RoundedRectangle:
            pos: self.x + 2, self.y + 2
            size: self.width - 4, self.height - 4
            radius: [8]

<SpecialKeyButton>:
    background_normal: ''
    background_color: 0, 0, 0, 0
    color: 0.96, 0.97, 0.98, 1
    font_size: '16sp'
    bold: True
    size_hint_y: None
    height: '52dp'
    canvas.before:
        Color:
            rgba: self._key_bg
        RoundedRectangle:
            pos: self.x + 2, self.y + 2
            size: self.width - 4, self.height - 4
            radius: [8]

<VirtualKeyboard>:
    orientation: 'vertical'
    size_hint_y: None
    padding: [4, 4]
    spacing: 2
    canvas.before:
        Color:
            rgba: 0.05, 0.06, 0.09, 1
        Rectangle:
            pos: self.pos
            size: self.size
        # Top border accent
        Color:
            rgba: 0.18, 0.20, 0.26, 1
        Rectangle:
            pos: self.x, self.y + self.height - 1
            size: self.width, 1
''')


# ============================================================
# KEY BUTTON CLASSES
# ============================================================

class KeyButton(Button):
    """Standard keyboard key with dark rounded background."""
    _key_bg = [0.13, 0.15, 0.20, 1]  # BG_CARD_HOVER

    def on_press(self):
        self._key_bg = [0.20, 0.23, 0.30, 1]  # Lighter on press

    def on_release(self):
        self._key_bg = [0.13, 0.15, 0.20, 1]  # Reset


class SpecialKeyButton(Button):
    """Special key (shift, backspace, enter, space) with distinct color."""
    _key_bg = [0.10, 0.12, 0.16, 1]  # Slightly darker than normal keys

    def on_press(self):
        self._key_bg = [0.18, 0.20, 0.26, 1]

    def on_release(self):
        self._key_bg = [0.10, 0.12, 0.16, 1]


# ============================================================
# VIRTUAL KEYBOARD
# ============================================================

class VirtualKeyboard(BoxLayout):
    """
    Virtual keyboard widget for touchscreen input.

    Properties:
        target_input: TextInput widget to type into
        mode: 'numeric' or 'alpha'
        shift_active: Whether shift is currently on
    """

    target_input = ObjectProperty(None, allownone=True)
    mode = StringProperty('numeric')
    shift_active = BooleanProperty(False)

    # Keyboard heights
    NUMERIC_HEIGHT = 220   # 4 rows * 52dp + padding
    ALPHA_HEIGHT = 230     # 4 rows * 52dp + padding

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint_y = None
        self._visible = True
        self._build_keyboard()
        # Rebuild when mode changes
        self.bind(mode=self._on_mode_change)

    def bind_to(self, text_input):
        """Bind keyboard output to a TextInput widget."""
        self.target_input = text_input

    def unbind_from(self):
        """Unbind from current TextInput."""
        self.target_input = None

    def show(self):
        """Show the keyboard with slide-up animation."""
        if self._visible:
            return
        self._visible = True
        target_h = self.NUMERIC_HEIGHT if self.mode == 'numeric' else self.ALPHA_HEIGHT
        anim = Animation(height=target_h, opacity=1, duration=0.15)
        anim.start(self)

    def hide(self):
        """Hide the keyboard with slide-down animation."""
        if not self._visible:
            return
        self._visible = False
        anim = Animation(height=0, opacity=0, duration=0.15)
        anim.start(self)

    def _on_mode_change(self, instance, value):
        """Rebuild keyboard when mode changes."""
        self._build_keyboard()

    def _build_keyboard(self):
        """Build the keyboard layout based on current mode."""
        self.clear_widgets()
        if self.mode == 'numeric':
            self.height = self.NUMERIC_HEIGHT
            self._build_numeric()
        else:
            self.height = self.ALPHA_HEIGHT
            self._build_alpha()

    # ============================================================
    # NUMERIC KEYBOARD
    # ============================================================

    def _build_numeric(self):
        """
        Build numeric keypad:
        [1] [2] [3]
        [4] [5] [6]
        [7] [8] [9]
        [<-] [0] [OK]
        """
        rows = [
            ['1', '2', '3'],
            ['4', '5', '6'],
            ['7', '8', '9'],
        ]

        for row_keys in rows:
            row = BoxLayout(
                orientation='horizontal',
                spacing=2,
                size_hint_y=None,
                height=52,
                padding=[60, 0],  # Center the narrow numeric pad
            )
            for key in row_keys:
                btn = KeyButton(text=key, font_size='24sp')
                btn.bind(on_release=lambda b, k=key: self._on_key(k))
                row.add_widget(btn)
            self.add_widget(row)

        # Bottom row: backspace, 0, enter
        bottom = BoxLayout(
            orientation='horizontal',
            spacing=2,
            size_hint_y=None,
            height=52,
            padding=[60, 0],
        )

        # Backspace
        bksp = SpecialKeyButton(text='<-', font_size='20sp')
        bksp._key_bg = [0.20, 0.10, 0.10, 1]  # Reddish tint
        bksp.color = [0.93, 0.27, 0.32, 1]  # Red text
        bksp.bind(on_release=lambda b: self._on_key('BKSP'))
        bottom.add_widget(bksp)

        # Zero
        zero = KeyButton(text='0', font_size='24sp')
        zero.bind(on_release=lambda b: self._on_key('0'))
        bottom.add_widget(zero)

        # Enter/OK
        enter = SpecialKeyButton(text='OK', font_size='20sp')
        enter._key_bg = [0.00, 0.55, 0.49, 1]  # Teal dimmed
        enter.color = [0.00, 0.82, 0.73, 1]  # Bright teal text
        enter.bind(on_release=lambda b: self._on_key('ENTER'))
        bottom.add_widget(enter)

        self.add_widget(bottom)

    # ============================================================
    # ALPHA KEYBOARD (QWERTY)
    # ============================================================

    def _build_alpha(self):
        """
        Build QWERTY keyboard:
        [Q][W][E][R][T][Y][U][I][O][P]
          [A][S][D][F][G][H][J][K][L]
        [SHIFT][Z][X][C][V][B][N][M][<-]
        [123][SPACE][OK]
        """
        qwerty_rows = [
            list('QWERTYUIOP'),
            list('ASDFGHJKL'),
            list('ZXCVBNM'),
        ]

        # Row 1: QWERTYUIOP
        row1 = BoxLayout(
            orientation='horizontal',
            spacing=1,
            size_hint_y=None,
            height=52,
            padding=[2, 0],
        )
        for key in qwerty_rows[0]:
            display = key if self.shift_active else key.lower()
            btn = KeyButton(text=display, font_size='18sp')
            btn.bind(on_release=lambda b, k=key: self._on_key(k))
            row1.add_widget(btn)
        self.add_widget(row1)

        # Row 2: ASDFGHJKL (with side padding for centering)
        row2 = BoxLayout(
            orientation='horizontal',
            spacing=1,
            size_hint_y=None,
            height=52,
            padding=[20, 0],
        )
        for key in qwerty_rows[1]:
            display = key if self.shift_active else key.lower()
            btn = KeyButton(text=display, font_size='18sp')
            btn.bind(on_release=lambda b, k=key: self._on_key(k))
            row2.add_widget(btn)
        self.add_widget(row2)

        # Row 3: SHIFT + ZXCVBNM + BACKSPACE
        row3 = BoxLayout(
            orientation='horizontal',
            spacing=1,
            size_hint_y=None,
            height=52,
            padding=[2, 0],
        )

        # Shift button
        shift_bg = [0.00, 0.55, 0.49, 1] if self.shift_active else [0.10, 0.12, 0.16, 1]
        shift_btn = SpecialKeyButton(
            text='SHIFT',
            font_size='13sp',
            size_hint_x=1.3,
        )
        shift_btn._key_bg = shift_bg
        if self.shift_active:
            shift_btn.color = [0.00, 0.82, 0.73, 1]
        shift_btn.bind(on_release=lambda b: self._on_key('SHIFT'))
        row3.add_widget(shift_btn)

        for key in qwerty_rows[2]:
            display = key if self.shift_active else key.lower()
            btn = KeyButton(text=display, font_size='18sp')
            btn.bind(on_release=lambda b, k=key: self._on_key(k))
            row3.add_widget(btn)

        # Backspace
        bksp = SpecialKeyButton(text='<-', font_size='18sp', size_hint_x=1.3)
        bksp._key_bg = [0.20, 0.10, 0.10, 1]
        bksp.color = [0.93, 0.27, 0.32, 1]
        bksp.bind(on_release=lambda b: self._on_key('BKSP'))
        row3.add_widget(bksp)

        self.add_widget(row3)

        # Row 4: 123 + SPACE + OK
        row4 = BoxLayout(
            orientation='horizontal',
            spacing=2,
            size_hint_y=None,
            height=52,
            padding=[2, 0],
        )

        # Toggle to numeric
        num_btn = SpecialKeyButton(text='123', font_size='16sp', size_hint_x=0.15)
        num_btn.bind(on_release=lambda b: self._on_key('TOGGLE'))
        row4.add_widget(num_btn)

        # Space bar
        space = SpecialKeyButton(text='SPACE', font_size='16sp', size_hint_x=0.6)
        space._key_bg = [0.13, 0.15, 0.20, 1]
        space.bind(on_release=lambda b: self._on_key('SPACE'))
        row4.add_widget(space)

        # Enter/OK
        enter = SpecialKeyButton(text='OK', font_size='18sp', size_hint_x=0.25)
        enter._key_bg = [0.00, 0.55, 0.49, 1]
        enter.color = [0.00, 0.82, 0.73, 1]
        enter.bind(on_release=lambda b: self._on_key('ENTER'))
        row4.add_widget(enter)

        self.add_widget(row4)

    # ============================================================
    # KEY HANDLER
    # ============================================================

    def _on_key(self, key):
        """Handle a key press."""
        if key == 'BKSP':
            if self.target_input and self.target_input.text:
                self.target_input.text = self.target_input.text[:-1]
        elif key == 'ENTER':
            if self.target_input:
                self.target_input.dispatch('on_text_validate')
        elif key == 'SHIFT':
            self.shift_active = not self.shift_active
            self._build_keyboard()
        elif key == 'SPACE':
            if self.target_input:
                self.target_input.text += ' '
        elif key == 'TOGGLE':
            # Toggle between numeric and alpha
            self.mode = 'numeric' if self.mode == 'alpha' else 'alpha'
        else:
            if self.target_input:
                char = key.upper() if self.shift_active else key.lower()
                self.target_input.text += char
                # Auto-disable shift after one character (like phone keyboard)
                if self.shift_active:
                    self.shift_active = False
                    self._build_keyboard()
