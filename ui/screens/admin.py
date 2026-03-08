"""
Admin Screen - Password-protected device configuration (2026 Redesign)

Provides:
- Driver mode toggles (RFID, Weight, LED, Buzzer: fake/real)
- Hardware configuration (I2C, serial, GPIO settings)
- Polling & threshold tuning
- Mixing parameter adjustments
- Security (change admin password)
- Factory reset

Design:
- Card-based scrollable layout with section headers
- Large touch targets for gloved hands
- Color-coded toggle buttons (green=REAL, gray=FAKE)
- Password dialog on entry
"""

import hashlib
import time

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.lang import Builder
from kivy.app import App
from kivy.clock import Clock
from kivy.properties import StringProperty, BooleanProperty, DictProperty

from config import settings


# Default admin password
DEFAULT_ADMIN_PASSWORD = "Smartlocker2026"


Builder.load_string('''
<AdminScreen>:
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
                text: 'ADMIN'
                font_size: '18sp'
                bold: True
                color: 0.96, 0.97, 0.98, 1
                size_hint_x: 0.5
                halign: 'center'
                text_size: self.size
                valign: 'middle'

            Widget:
                size_hint_x: 0.3

        # ---- SCROLLABLE CONTENT ----
        ScrollView:
            id: admin_scroll
            do_scroll_x: False
            bar_color: 0.00, 0.82, 0.73, 0.5
            bar_width: 4
            BoxLayout:
                id: admin_content
                orientation: 'vertical'
                padding: [12, 8, 12, 12]
                spacing: 8
                size_hint_y: None
                height: self.minimum_height

                # ==== SECTION 1: DRIVER MODES ====
                Label:
                    text: 'Driver Modes'
                    font_size: '14sp'
                    bold: True
                    color: 0.00, 0.82, 0.73, 1
                    size_hint_y: None
                    height: '22dp'
                    halign: 'left'
                    text_size: self.size
                    padding: [4, 0]

                BoxLayout:
                    orientation: 'vertical'
                    size_hint_y: None
                    height: self.minimum_height
                    padding: [10, 8]
                    spacing: 6
                    canvas.before:
                        Color:
                            rgba: 0.10, 0.12, 0.16, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10]

                    # RFID toggle
                    BoxLayout:
                        size_hint_y: None
                        height: '48dp'
                        spacing: 8
                        Label:
                            text: 'RFID Reader'
                            font_size: '14sp'
                            color: 0.65, 0.68, 0.76, 1
                            halign: 'left'
                            text_size: self.size
                            valign: 'middle'
                            size_hint_x: 0.5
                        Button:
                            id: toggle_rfid
                            text: 'FAKE'
                            font_size: '15sp'
                            bold: True
                            background_normal: ''
                            background_color: 0.30, 0.33, 0.38, 1
                            color: 0.96, 0.97, 0.98, 1
                            size_hint_x: 0.5
                            on_release: root.toggle_driver('rfid')

                    # Weight toggle
                    BoxLayout:
                        size_hint_y: None
                        height: '48dp'
                        spacing: 8
                        Label:
                            text: 'Weight Sensor'
                            font_size: '14sp'
                            color: 0.65, 0.68, 0.76, 1
                            halign: 'left'
                            text_size: self.size
                            valign: 'middle'
                            size_hint_x: 0.5
                        Button:
                            id: toggle_weight
                            text: 'FAKE'
                            font_size: '15sp'
                            bold: True
                            background_normal: ''
                            background_color: 0.30, 0.33, 0.38, 1
                            color: 0.96, 0.97, 0.98, 1
                            size_hint_x: 0.5
                            on_release: root.toggle_driver('weight')

                    # LED toggle
                    BoxLayout:
                        size_hint_y: None
                        height: '48dp'
                        spacing: 8
                        Label:
                            text: 'LED Strip'
                            font_size: '14sp'
                            color: 0.65, 0.68, 0.76, 1
                            halign: 'left'
                            text_size: self.size
                            valign: 'middle'
                            size_hint_x: 0.5
                        Button:
                            id: toggle_led
                            text: 'FAKE'
                            font_size: '15sp'
                            bold: True
                            background_normal: ''
                            background_color: 0.30, 0.33, 0.38, 1
                            color: 0.96, 0.97, 0.98, 1
                            size_hint_x: 0.5
                            on_release: root.toggle_driver('led')

                    # Buzzer toggle
                    BoxLayout:
                        size_hint_y: None
                        height: '48dp'
                        spacing: 8
                        Label:
                            text: 'Buzzer'
                            font_size: '14sp'
                            color: 0.65, 0.68, 0.76, 1
                            halign: 'left'
                            text_size: self.size
                            valign: 'middle'
                            size_hint_x: 0.5
                        Button:
                            id: toggle_buzzer
                            text: 'FAKE'
                            font_size: '15sp'
                            bold: True
                            background_normal: ''
                            background_color: 0.30, 0.33, 0.38, 1
                            color: 0.96, 0.97, 0.98, 1
                            size_hint_x: 0.5
                            on_release: root.toggle_driver('buzzer')

                # ==== SECTION 2: HARDWARE CONFIG ====
                Label:
                    text: 'Hardware Configuration'
                    font_size: '14sp'
                    bold: True
                    color: 0.00, 0.82, 0.73, 1
                    size_hint_y: None
                    height: '22dp'
                    halign: 'left'
                    text_size: self.size
                    padding: [4, 0]

                BoxLayout:
                    id: hw_config_card
                    orientation: 'vertical'
                    size_hint_y: None
                    height: self.minimum_height
                    padding: [10, 8]
                    spacing: 4
                    canvas.before:
                        Color:
                            rgba: 0.10, 0.12, 0.16, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10]

                    # RFID hardware settings
                    Label:
                        id: rfid_hw_header
                        text: 'RFID (I2C)'
                        font_size: '12sp'
                        bold: True
                        color: 0.98, 0.65, 0.25, 1
                        size_hint_y: None
                        height: '20dp'
                        halign: 'left'
                        text_size: self.size

                    BoxLayout:
                        id: rfid_hw_row
                        size_hint_y: None
                        height: '40dp'
                        spacing: 8
                        Label:
                            text: 'I2C Bus:'
                            font_size: '12sp'
                            color: 0.38, 0.42, 0.50, 1
                            size_hint_x: 0.25
                            halign: 'right'
                            text_size: self.size
                            valign: 'middle'
                        TextInput:
                            id: input_rfid_i2c_bus
                            text: '1'
                            font_size: '14sp'
                            multiline: False
                            size_hint_x: 0.2
                            size_hint_y: None
                            height: '36dp'
                            background_color: 0.07, 0.09, 0.13, 1
                            foreground_color: 0.96, 0.97, 0.98, 1
                            cursor_color: 0.00, 0.82, 0.73, 1
                            padding: [8, 6]
                            input_filter: 'int'
                        Label:
                            text: 'Addr (hex):'
                            font_size: '12sp'
                            color: 0.38, 0.42, 0.50, 1
                            size_hint_x: 0.25
                            halign: 'right'
                            text_size: self.size
                            valign: 'middle'
                        TextInput:
                            id: input_rfid_i2c_addr
                            text: '0x24'
                            font_size: '14sp'
                            multiline: False
                            size_hint_x: 0.3
                            size_hint_y: None
                            height: '36dp'
                            background_color: 0.07, 0.09, 0.13, 1
                            foreground_color: 0.96, 0.97, 0.98, 1
                            cursor_color: 0.00, 0.82, 0.73, 1
                            padding: [8, 6]

                    # Weight hardware settings
                    Label:
                        id: weight_hw_header
                        text: 'Weight Sensor (Serial)'
                        font_size: '12sp'
                        bold: True
                        color: 0.98, 0.65, 0.25, 1
                        size_hint_y: None
                        height: '20dp'
                        halign: 'left'
                        text_size: self.size

                    BoxLayout:
                        id: weight_hw_row
                        size_hint_y: None
                        height: '40dp'
                        spacing: 8
                        Label:
                            text: 'Port:'
                            font_size: '12sp'
                            color: 0.38, 0.42, 0.50, 1
                            size_hint_x: 0.2
                            halign: 'right'
                            text_size: self.size
                            valign: 'middle'
                        TextInput:
                            id: input_weight_port
                            text: '/dev/ttyUSB0'
                            font_size: '13sp'
                            multiline: False
                            size_hint_x: 0.4
                            size_hint_y: None
                            height: '36dp'
                            background_color: 0.07, 0.09, 0.13, 1
                            foreground_color: 0.96, 0.97, 0.98, 1
                            cursor_color: 0.00, 0.82, 0.73, 1
                            padding: [8, 6]
                        Label:
                            text: 'Baud:'
                            font_size: '12sp'
                            color: 0.38, 0.42, 0.50, 1
                            size_hint_x: 0.15
                            halign: 'right'
                            text_size: self.size
                            valign: 'middle'
                        TextInput:
                            id: input_weight_baud
                            text: '115200'
                            font_size: '13sp'
                            multiline: False
                            size_hint_x: 0.25
                            size_hint_y: None
                            height: '36dp'
                            background_color: 0.07, 0.09, 0.13, 1
                            foreground_color: 0.96, 0.97, 0.98, 1
                            cursor_color: 0.00, 0.82, 0.73, 1
                            padding: [8, 6]
                            input_filter: 'int'

                    # LED hardware settings
                    Label:
                        id: led_hw_header
                        text: 'LED Strip (WS2812B)'
                        font_size: '12sp'
                        bold: True
                        color: 0.98, 0.65, 0.25, 1
                        size_hint_y: None
                        height: '20dp'
                        halign: 'left'
                        text_size: self.size

                    BoxLayout:
                        id: led_hw_row
                        size_hint_y: None
                        height: '40dp'
                        spacing: 6
                        Label:
                            text: 'GPIO:'
                            font_size: '12sp'
                            color: 0.38, 0.42, 0.50, 1
                            size_hint_x: 0.18
                            halign: 'right'
                            text_size: self.size
                            valign: 'middle'
                        TextInput:
                            id: input_led_gpio
                            text: '18'
                            font_size: '14sp'
                            multiline: False
                            size_hint_x: 0.15
                            size_hint_y: None
                            height: '36dp'
                            background_color: 0.07, 0.09, 0.13, 1
                            foreground_color: 0.96, 0.97, 0.98, 1
                            cursor_color: 0.00, 0.82, 0.73, 1
                            padding: [8, 6]
                            input_filter: 'int'
                        Label:
                            text: 'Count:'
                            font_size: '12sp'
                            color: 0.38, 0.42, 0.50, 1
                            size_hint_x: 0.18
                            halign: 'right'
                            text_size: self.size
                            valign: 'middle'
                        TextInput:
                            id: input_led_count
                            text: '12'
                            font_size: '14sp'
                            multiline: False
                            size_hint_x: 0.15
                            size_hint_y: None
                            height: '36dp'
                            background_color: 0.07, 0.09, 0.13, 1
                            foreground_color: 0.96, 0.97, 0.98, 1
                            cursor_color: 0.00, 0.82, 0.73, 1
                            padding: [8, 6]
                            input_filter: 'int'
                        Label:
                            text: 'Bright:'
                            font_size: '12sp'
                            color: 0.38, 0.42, 0.50, 1
                            size_hint_x: 0.18
                            halign: 'right'
                            text_size: self.size
                            valign: 'middle'
                        TextInput:
                            id: input_led_brightness
                            text: '128'
                            font_size: '14sp'
                            multiline: False
                            size_hint_x: 0.16
                            size_hint_y: None
                            height: '36dp'
                            background_color: 0.07, 0.09, 0.13, 1
                            foreground_color: 0.96, 0.97, 0.98, 1
                            cursor_color: 0.00, 0.82, 0.73, 1
                            padding: [8, 6]
                            input_filter: 'int'

                    # Buzzer hardware settings
                    Label:
                        id: buzzer_hw_header
                        text: 'Buzzer (GPIO)'
                        font_size: '12sp'
                        bold: True
                        color: 0.98, 0.65, 0.25, 1
                        size_hint_y: None
                        height: '20dp'
                        halign: 'left'
                        text_size: self.size

                    BoxLayout:
                        id: buzzer_hw_row
                        size_hint_y: None
                        height: '40dp'
                        spacing: 8
                        Label:
                            text: 'GPIO Pin:'
                            font_size: '12sp'
                            color: 0.38, 0.42, 0.50, 1
                            size_hint_x: 0.35
                            halign: 'right'
                            text_size: self.size
                            valign: 'middle'
                        TextInput:
                            id: input_buzzer_gpio
                            text: '18'
                            font_size: '14sp'
                            multiline: False
                            size_hint_x: 0.25
                            size_hint_y: None
                            height: '36dp'
                            background_color: 0.07, 0.09, 0.13, 1
                            foreground_color: 0.96, 0.97, 0.98, 1
                            cursor_color: 0.00, 0.82, 0.73, 1
                            padding: [8, 6]
                            input_filter: 'int'
                        Widget:
                            size_hint_x: 0.4

                # ==== SECTION 3: POLLING & THRESHOLDS ====
                Label:
                    text: 'Polling & Thresholds'
                    font_size: '14sp'
                    bold: True
                    color: 0.00, 0.82, 0.73, 1
                    size_hint_y: None
                    height: '22dp'
                    halign: 'left'
                    text_size: self.size
                    padding: [4, 0]

                BoxLayout:
                    orientation: 'vertical'
                    size_hint_y: None
                    height: self.minimum_height
                    padding: [10, 8]
                    spacing: 4
                    canvas.before:
                        Color:
                            rgba: 0.10, 0.12, 0.16, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10]

                    BoxLayout:
                        size_hint_y: None
                        height: '40dp'
                        spacing: 8
                        Label:
                            text: 'RFID Poll (ms):'
                            font_size: '12sp'
                            color: 0.65, 0.68, 0.76, 1
                            size_hint_x: 0.45
                            halign: 'left'
                            text_size: self.size
                            valign: 'middle'
                        TextInput:
                            id: input_rfid_poll
                            text: '500'
                            font_size: '14sp'
                            multiline: False
                            size_hint_x: 0.55
                            size_hint_y: None
                            height: '36dp'
                            background_color: 0.07, 0.09, 0.13, 1
                            foreground_color: 0.96, 0.97, 0.98, 1
                            cursor_color: 0.00, 0.82, 0.73, 1
                            padding: [8, 6]
                            input_filter: 'int'

                    BoxLayout:
                        size_hint_y: None
                        height: '40dp'
                        spacing: 8
                        Label:
                            text: 'Weight Poll (ms):'
                            font_size: '12sp'
                            color: 0.65, 0.68, 0.76, 1
                            size_hint_x: 0.45
                            halign: 'left'
                            text_size: self.size
                            valign: 'middle'
                        TextInput:
                            id: input_weight_poll
                            text: '200'
                            font_size: '14sp'
                            multiline: False
                            size_hint_x: 0.55
                            size_hint_y: None
                            height: '36dp'
                            background_color: 0.07, 0.09, 0.13, 1
                            foreground_color: 0.96, 0.97, 0.98, 1
                            cursor_color: 0.00, 0.82, 0.73, 1
                            padding: [8, 6]
                            input_filter: 'int'

                    BoxLayout:
                        size_hint_y: None
                        height: '40dp'
                        spacing: 8
                        Label:
                            text: 'Weight Stable (s):'
                            font_size: '12sp'
                            color: 0.65, 0.68, 0.76, 1
                            size_hint_x: 0.45
                            halign: 'left'
                            text_size: self.size
                            valign: 'middle'
                        TextInput:
                            id: input_weight_stable
                            text: '3.0'
                            font_size: '14sp'
                            multiline: False
                            size_hint_x: 0.55
                            size_hint_y: None
                            height: '36dp'
                            background_color: 0.07, 0.09, 0.13, 1
                            foreground_color: 0.96, 0.97, 0.98, 1
                            cursor_color: 0.00, 0.82, 0.73, 1
                            padding: [8, 6]

                    BoxLayout:
                        size_hint_y: None
                        height: '40dp'
                        spacing: 8
                        Label:
                            text: 'Weight Tolerance (g):'
                            font_size: '12sp'
                            color: 0.65, 0.68, 0.76, 1
                            size_hint_x: 0.45
                            halign: 'left'
                            text_size: self.size
                            valign: 'middle'
                        TextInput:
                            id: input_weight_tolerance
                            text: '10'
                            font_size: '14sp'
                            multiline: False
                            size_hint_x: 0.55
                            size_hint_y: None
                            height: '36dp'
                            background_color: 0.07, 0.09, 0.13, 1
                            foreground_color: 0.96, 0.97, 0.98, 1
                            cursor_color: 0.00, 0.82, 0.73, 1
                            padding: [8, 6]
                            input_filter: 'int'

                # ==== SECTION 4: MIXING PARAMETERS ====
                Label:
                    text: 'Mixing Parameters'
                    font_size: '14sp'
                    bold: True
                    color: 0.00, 0.82, 0.73, 1
                    size_hint_y: None
                    height: '22dp'
                    halign: 'left'
                    text_size: self.size
                    padding: [4, 0]

                BoxLayout:
                    orientation: 'vertical'
                    size_hint_y: None
                    height: self.minimum_height
                    padding: [10, 8]
                    spacing: 4
                    canvas.before:
                        Color:
                            rgba: 0.10, 0.12, 0.16, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10]

                    BoxLayout:
                        size_hint_y: None
                        height: '40dp'
                        spacing: 8
                        Label:
                            text: 'Ratio Tolerance (%):'
                            font_size: '12sp'
                            color: 0.65, 0.68, 0.76, 1
                            size_hint_x: 0.45
                            halign: 'left'
                            text_size: self.size
                            valign: 'middle'
                        TextInput:
                            id: input_mix_tolerance
                            text: '5.0'
                            font_size: '14sp'
                            multiline: False
                            size_hint_x: 0.55
                            size_hint_y: None
                            height: '36dp'
                            background_color: 0.07, 0.09, 0.13, 1
                            foreground_color: 0.96, 0.97, 0.98, 1
                            cursor_color: 0.00, 0.82, 0.73, 1
                            padding: [8, 6]

                    BoxLayout:
                        size_hint_y: None
                        height: '40dp'
                        spacing: 8
                        Label:
                            text: 'Weight Stable (s):'
                            font_size: '12sp'
                            color: 0.65, 0.68, 0.76, 1
                            size_hint_x: 0.45
                            halign: 'left'
                            text_size: self.size
                            valign: 'middle'
                        TextInput:
                            id: input_mix_stable
                            text: '2.0'
                            font_size: '14sp'
                            multiline: False
                            size_hint_x: 0.55
                            size_hint_y: None
                            height: '36dp'
                            background_color: 0.07, 0.09, 0.13, 1
                            foreground_color: 0.96, 0.97, 0.98, 1
                            cursor_color: 0.00, 0.82, 0.73, 1
                            padding: [8, 6]

                    BoxLayout:
                        size_hint_y: None
                        height: '40dp'
                        spacing: 8
                        Label:
                            text: 'Thinner Max (%):'
                            font_size: '12sp'
                            color: 0.65, 0.68, 0.76, 1
                            size_hint_x: 0.45
                            halign: 'left'
                            text_size: self.size
                            valign: 'middle'
                        TextInput:
                            id: input_thinner_max
                            text: '20.0'
                            font_size: '14sp'
                            multiline: False
                            size_hint_x: 0.55
                            size_hint_y: None
                            height: '36dp'
                            background_color: 0.07, 0.09, 0.13, 1
                            foreground_color: 0.96, 0.97, 0.98, 1
                            cursor_color: 0.00, 0.82, 0.73, 1
                            padding: [8, 6]

                # ==== SECTION 5: SECURITY ====
                Label:
                    text: 'Security'
                    font_size: '14sp'
                    bold: True
                    color: 0.00, 0.82, 0.73, 1
                    size_hint_y: None
                    height: '22dp'
                    halign: 'left'
                    text_size: self.size
                    padding: [4, 0]

                BoxLayout:
                    orientation: 'vertical'
                    size_hint_y: None
                    height: self.minimum_height
                    padding: [10, 8]
                    spacing: 4
                    canvas.before:
                        Color:
                            rgba: 0.10, 0.12, 0.16, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10]

                    Label:
                        text: 'Change Admin Password'
                        font_size: '13sp'
                        bold: True
                        color: 0.98, 0.65, 0.25, 1
                        size_hint_y: None
                        height: '20dp'
                        halign: 'left'
                        text_size: self.size

                    BoxLayout:
                        size_hint_y: None
                        height: '40dp'
                        spacing: 8
                        Label:
                            text: 'Old:'
                            font_size: '12sp'
                            color: 0.38, 0.42, 0.50, 1
                            size_hint_x: 0.2
                            halign: 'right'
                            text_size: self.size
                            valign: 'middle'
                        TextInput:
                            id: input_old_password
                            hint_text: 'Current password'
                            font_size: '14sp'
                            multiline: False
                            password: True
                            size_hint_x: 0.8
                            size_hint_y: None
                            height: '36dp'
                            background_color: 0.07, 0.09, 0.13, 1
                            foreground_color: 0.96, 0.97, 0.98, 1
                            cursor_color: 0.00, 0.82, 0.73, 1
                            hint_text_color: 0.20, 0.22, 0.28, 1
                            padding: [8, 6]

                    BoxLayout:
                        size_hint_y: None
                        height: '40dp'
                        spacing: 8
                        Label:
                            text: 'New:'
                            font_size: '12sp'
                            color: 0.38, 0.42, 0.50, 1
                            size_hint_x: 0.2
                            halign: 'right'
                            text_size: self.size
                            valign: 'middle'
                        TextInput:
                            id: input_new_password
                            hint_text: 'New password'
                            font_size: '14sp'
                            multiline: False
                            password: True
                            size_hint_x: 0.8
                            size_hint_y: None
                            height: '36dp'
                            background_color: 0.07, 0.09, 0.13, 1
                            foreground_color: 0.96, 0.97, 0.98, 1
                            cursor_color: 0.00, 0.82, 0.73, 1
                            hint_text_color: 0.20, 0.22, 0.28, 1
                            padding: [8, 6]

                    BoxLayout:
                        size_hint_y: None
                        height: '40dp'
                        spacing: 8
                        Label:
                            text: 'Confirm:'
                            font_size: '12sp'
                            color: 0.38, 0.42, 0.50, 1
                            size_hint_x: 0.2
                            halign: 'right'
                            text_size: self.size
                            valign: 'middle'
                        TextInput:
                            id: input_confirm_password
                            hint_text: 'Confirm new password'
                            font_size: '14sp'
                            multiline: False
                            password: True
                            size_hint_x: 0.8
                            size_hint_y: None
                            height: '36dp'
                            background_color: 0.07, 0.09, 0.13, 1
                            foreground_color: 0.96, 0.97, 0.98, 1
                            cursor_color: 0.00, 0.82, 0.73, 1
                            hint_text_color: 0.20, 0.22, 0.28, 1
                            padding: [8, 6]

                    BoxLayout:
                        size_hint_y: None
                        height: '44dp'
                        spacing: 8
                        Button:
                            text: 'CHANGE PASSWORD'
                            font_size: '14sp'
                            bold: True
                            background_normal: ''
                            background_color: 0, 0, 0, 0
                            color: 0.02, 0.05, 0.08, 1
                            on_release: root.change_password()
                            canvas.before:
                                Color:
                                    rgba: 0.33, 0.58, 0.85, 1
                                RoundedRectangle:
                                    pos: self.pos
                                    size: self.size
                                    radius: [8]

                        Widget:
                            size_hint_x: 0.05

                    Label:
                        id: pw_change_status
                        text: ''
                        font_size: '12sp'
                        color: 0.38, 0.42, 0.50, 1
                        size_hint_y: None
                        height: '18dp'
                        halign: 'left'
                        text_size: self.size
                        markup: True

                    Label:
                        id: pw_last_changed
                        text: 'Last changed: ---'
                        font_size: '11sp'
                        color: 0.38, 0.42, 0.50, 1
                        size_hint_y: None
                        height: '16dp'
                        halign: 'left'
                        text_size: self.size

                # ==== BOTTOM STATUS ====
                Label:
                    id: admin_status_label
                    text: ''
                    font_size: '13sp'
                    color: 0.38, 0.42, 0.50, 1
                    size_hint_y: None
                    height: '22dp'
                    halign: 'center'
                    text_size: self.size
                    markup: True

                # ==== BOTTOM ACTION BUTTONS ====
                BoxLayout:
                    spacing: 8
                    size_hint_y: None
                    height: '64dp'

                    Button:
                        text: 'SAVE & RESTART'
                        font_size: '17sp'
                        bold: True
                        background_normal: ''
                        background_color: 0, 0, 0, 0
                        color: 0.02, 0.05, 0.08, 1
                        on_release: root.save_and_restart()
                        canvas.before:
                            Color:
                                rgba: 0.00, 0.82, 0.73, 1
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [12]

                    Button:
                        text: 'CANCEL'
                        font_size: '15sp'
                        bold: True
                        background_normal: ''
                        background_color: 0, 0, 0, 0
                        color: 0.60, 0.64, 0.72, 1
                        size_hint_x: 0.35
                        on_release: root.go_back()
                        canvas.before:
                            Color:
                                rgba: 0.13, 0.15, 0.20, 1
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [12]

                BoxLayout:
                    size_hint_y: None
                    height: '54dp'
                    Button:
                        text: 'FACTORY RESET'
                        font_size: '15sp'
                        bold: True
                        background_normal: ''
                        background_color: 0, 0, 0, 0
                        color: 1, 1, 1, 1
                        on_release: root.confirm_factory_reset()
                        canvas.before:
                            Color:
                                rgba: 0.93, 0.27, 0.32, 1
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [12]

                # Bottom spacer
                Widget:
                    size_hint_y: None
                    height: '12dp'
''')


class AdminScreen(Screen):
    """Password-protected admin configuration screen."""

    # Current working copy of driver modes
    _driver_modes = DictProperty({
        'rfid': 'fake',
        'weight': 'fake',
        'led': 'fake',
        'buzzer': 'fake',
    })

    def on_enter(self):
        """Load current settings into the form when entering."""
        self._load_current_settings()
        self._update_password_info()

    def _load_current_settings(self):
        """Populate all fields from current settings (DB overrides first, then defaults)."""
        app = App.get_running_app()

        # Load admin config from DB (may override defaults)
        admin_cfg = app.db.get_admin_config()

        # --- Driver modes ---
        self._driver_modes = {
            'rfid': admin_cfg.get('driver_rfid', settings.DRIVER_RFID),
            'weight': admin_cfg.get('driver_weight', settings.DRIVER_WEIGHT),
            'led': admin_cfg.get('driver_led', settings.DRIVER_LED),
            'buzzer': admin_cfg.get('driver_buzzer', settings.DRIVER_BUZZER),
        }
        self._refresh_toggle_buttons()

        # --- Hardware config ---
        self.ids.input_rfid_i2c_bus.text = str(
            admin_cfg.get('rfid_i2c_bus', settings.RFID_I2C_BUS))
        self.ids.input_rfid_i2c_addr.text = admin_cfg.get(
            'rfid_i2c_addr', hex(settings.RFID_I2C_ADDRESS))
        self.ids.input_weight_port.text = admin_cfg.get(
            'weight_serial_port', settings.WEIGHT_SERIAL_PORT)
        self.ids.input_weight_baud.text = str(
            admin_cfg.get('weight_serial_baud', settings.WEIGHT_SERIAL_BAUD))
        self.ids.input_led_gpio.text = str(
            admin_cfg.get('led_gpio_pin', settings.LED_GPIO_PIN))
        self.ids.input_led_count.text = str(
            admin_cfg.get('led_count', settings.LED_COUNT))
        self.ids.input_led_brightness.text = str(
            admin_cfg.get('led_brightness', settings.LED_BRIGHTNESS))
        self.ids.input_buzzer_gpio.text = str(
            admin_cfg.get('buzzer_gpio_pin', settings.BUZZER_GPIO_PIN))

        # --- Polling & thresholds ---
        self.ids.input_rfid_poll.text = str(
            admin_cfg.get('rfid_poll_interval_ms', settings.RFID_POLL_INTERVAL_MS))
        self.ids.input_weight_poll.text = str(
            admin_cfg.get('weight_poll_interval_ms', settings.WEIGHT_POLL_INTERVAL_MS))
        self.ids.input_weight_stable.text = str(
            admin_cfg.get('weight_stable_window_s', settings.WEIGHT_STABLE_WINDOW_S))
        self.ids.input_weight_tolerance.text = str(
            admin_cfg.get('weight_stable_tolerance_g', settings.WEIGHT_STABLE_TOLERANCE_G))

        # --- Mixing parameters ---
        self.ids.input_mix_tolerance.text = str(
            admin_cfg.get('mix_ratio_tolerance_pct', settings.MIX_RATIO_TOLERANCE_PCT))
        self.ids.input_mix_stable.text = str(
            admin_cfg.get('mix_weight_stable_s', settings.MIX_WEIGHT_STABLE_S))
        self.ids.input_thinner_max.text = str(
            admin_cfg.get('thinner_max_pct', settings.THINNER_MAX_PCT))

        # --- Clear password fields ---
        self.ids.input_old_password.text = ''
        self.ids.input_new_password.text = ''
        self.ids.input_confirm_password.text = ''
        self.ids.pw_change_status.text = ''

        # --- Clear status ---
        self.ids.admin_status_label.text = ''

        # --- Show/hide hardware config based on driver modes ---
        self._update_hw_visibility()

    def _refresh_toggle_buttons(self):
        """Update toggle button text and colors based on current driver modes."""
        for name in ['rfid', 'weight', 'led', 'buzzer']:
            btn = self.ids.get(f'toggle_{name}')
            if btn:
                mode = self._driver_modes.get(name, 'fake')
                if mode == 'real':
                    btn.text = 'REAL'
                    btn.background_color = [0.20, 0.82, 0.48, 1]  # Green
                else:
                    btn.text = 'FAKE'
                    btn.background_color = [0.30, 0.33, 0.38, 1]  # Gray

    def toggle_driver(self, driver_name):
        """Toggle a driver between fake and real mode."""
        current = self._driver_modes.get(driver_name, 'fake')
        new_mode = 'real' if current == 'fake' else 'fake'
        self._driver_modes[driver_name] = new_mode
        self._refresh_toggle_buttons()
        self._update_hw_visibility()

    def _update_hw_visibility(self):
        """Show/hide hardware config rows based on which drivers are set to real."""
        any_real = any(v == 'real' for v in self._driver_modes.values())

        # RFID hw config visibility
        rfid_real = self._driver_modes.get('rfid', 'fake') == 'real'
        self.ids.rfid_hw_header.opacity = 1 if rfid_real else 0.3
        self.ids.rfid_hw_row.opacity = 1 if rfid_real else 0.3
        self.ids.rfid_hw_row.disabled = not rfid_real

        # Weight hw config visibility
        weight_real = self._driver_modes.get('weight', 'fake') == 'real'
        self.ids.weight_hw_header.opacity = 1 if weight_real else 0.3
        self.ids.weight_hw_row.opacity = 1 if weight_real else 0.3
        self.ids.weight_hw_row.disabled = not weight_real

        # LED hw config visibility
        led_real = self._driver_modes.get('led', 'fake') == 'real'
        self.ids.led_hw_header.opacity = 1 if led_real else 0.3
        self.ids.led_hw_row.opacity = 1 if led_real else 0.3
        self.ids.led_hw_row.disabled = not led_real

        # Buzzer hw config visibility
        buzzer_real = self._driver_modes.get('buzzer', 'fake') == 'real'
        self.ids.buzzer_hw_header.opacity = 1 if buzzer_real else 0.3
        self.ids.buzzer_hw_row.opacity = 1 if buzzer_real else 0.3
        self.ids.buzzer_hw_row.disabled = not buzzer_real

    def _update_password_info(self):
        """Show the last password change date."""
        app = App.get_running_app()
        change_date = app.db.get_admin_password_change_date()
        if change_date:
            self.ids.pw_last_changed.text = f'Last changed: {change_date}'
        else:
            self.ids.pw_last_changed.text = 'Last changed: Never (using default)'

    def _collect_config(self):
        """Collect all form values into a config dictionary."""
        config = {}

        # Driver modes
        config['driver_rfid'] = self._driver_modes.get('rfid', 'fake')
        config['driver_weight'] = self._driver_modes.get('weight', 'fake')
        config['driver_led'] = self._driver_modes.get('led', 'fake')
        config['driver_buzzer'] = self._driver_modes.get('buzzer', 'fake')

        # Hardware config
        try:
            config['rfid_i2c_bus'] = int(self.ids.input_rfid_i2c_bus.text)
        except ValueError:
            config['rfid_i2c_bus'] = settings.RFID_I2C_BUS
        config['rfid_i2c_addr'] = self.ids.input_rfid_i2c_addr.text.strip()
        config['weight_serial_port'] = self.ids.input_weight_port.text.strip()
        try:
            config['weight_serial_baud'] = int(self.ids.input_weight_baud.text)
        except ValueError:
            config['weight_serial_baud'] = settings.WEIGHT_SERIAL_BAUD
        try:
            config['led_gpio_pin'] = int(self.ids.input_led_gpio.text)
        except ValueError:
            config['led_gpio_pin'] = settings.LED_GPIO_PIN
        try:
            config['led_count'] = int(self.ids.input_led_count.text)
        except ValueError:
            config['led_count'] = settings.LED_COUNT
        try:
            config['led_brightness'] = int(self.ids.input_led_brightness.text)
        except ValueError:
            config['led_brightness'] = settings.LED_BRIGHTNESS
        try:
            config['buzzer_gpio_pin'] = int(self.ids.input_buzzer_gpio.text)
        except ValueError:
            config['buzzer_gpio_pin'] = settings.BUZZER_GPIO_PIN

        # Polling & thresholds
        try:
            config['rfid_poll_interval_ms'] = int(self.ids.input_rfid_poll.text)
        except ValueError:
            config['rfid_poll_interval_ms'] = settings.RFID_POLL_INTERVAL_MS
        try:
            config['weight_poll_interval_ms'] = int(self.ids.input_weight_poll.text)
        except ValueError:
            config['weight_poll_interval_ms'] = settings.WEIGHT_POLL_INTERVAL_MS
        try:
            config['weight_stable_window_s'] = float(self.ids.input_weight_stable.text)
        except ValueError:
            config['weight_stable_window_s'] = settings.WEIGHT_STABLE_WINDOW_S
        try:
            config['weight_stable_tolerance_g'] = int(self.ids.input_weight_tolerance.text)
        except ValueError:
            config['weight_stable_tolerance_g'] = settings.WEIGHT_STABLE_TOLERANCE_G

        # Mixing parameters
        try:
            config['mix_ratio_tolerance_pct'] = float(self.ids.input_mix_tolerance.text)
        except ValueError:
            config['mix_ratio_tolerance_pct'] = settings.MIX_RATIO_TOLERANCE_PCT
        try:
            config['mix_weight_stable_s'] = float(self.ids.input_mix_stable.text)
        except ValueError:
            config['mix_weight_stable_s'] = settings.MIX_WEIGHT_STABLE_S
        try:
            config['thinner_max_pct'] = float(self.ids.input_thinner_max.text)
        except ValueError:
            config['thinner_max_pct'] = settings.THINNER_MAX_PCT

        return config

    def save_and_restart(self):
        """Save current admin configuration to DB and show restart message."""
        app = App.get_running_app()
        config = self._collect_config()
        app.db.save_admin_config(config)

        self.ids.admin_status_label.text = (
            '[color=33d17a]Settings saved! Restart app to apply changes.[/color]'
        )
        self.ids.admin_status_label.markup = True

    def change_password(self):
        """Change the admin password after validating old password."""
        app = App.get_running_app()
        old_pw = self.ids.input_old_password.text
        new_pw = self.ids.input_new_password.text
        confirm_pw = self.ids.input_confirm_password.text

        # Validate old password
        stored_hash = app.db.get_admin_password_hash()
        if stored_hash is None:
            # First time: default password
            expected_hash = hashlib.sha256(
                DEFAULT_ADMIN_PASSWORD.encode()
            ).hexdigest()
        else:
            expected_hash = stored_hash

        old_hash = hashlib.sha256(old_pw.encode()).hexdigest()
        if old_hash != expected_hash:
            self.ids.pw_change_status.text = (
                '[color=ed4550]Old password is incorrect[/color]'
            )
            self.ids.pw_change_status.markup = True
            return

        # Validate new password
        if not new_pw or len(new_pw) < 4:
            self.ids.pw_change_status.text = (
                '[color=ed4550]New password must be at least 4 characters[/color]'
            )
            self.ids.pw_change_status.markup = True
            return

        if new_pw != confirm_pw:
            self.ids.pw_change_status.text = (
                '[color=ed4550]New passwords do not match[/color]'
            )
            self.ids.pw_change_status.markup = True
            return

        # Save new hash
        new_hash = hashlib.sha256(new_pw.encode()).hexdigest()
        app.db.set_admin_password_hash(new_hash)

        # Clear fields and show success
        self.ids.input_old_password.text = ''
        self.ids.input_new_password.text = ''
        self.ids.input_confirm_password.text = ''
        self.ids.pw_change_status.text = (
            '[color=33d17a]Password changed successfully[/color]'
        )
        self.ids.pw_change_status.markup = True
        self._update_password_info()

    def confirm_factory_reset(self):
        """Show a confirmation dialog before factory reset."""
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)

        content.add_widget(Label(
            text='Reset ALL settings to factory defaults?',
            font_size='16sp',
            color=[0.96, 0.97, 0.98, 1],
            size_hint_y=None,
            height=40,
            halign='center',
            text_size=(350, None),
        ))
        content.add_widget(Label(
            text='This cannot be undone.',
            font_size='13sp',
            color=[0.93, 0.27, 0.32, 1],
            size_hint_y=None,
            height=24,
            halign='center',
            text_size=(350, None),
        ))

        btn_row = BoxLayout(spacing=12, size_hint_y=None, height=54)

        cancel_btn = Button(
            text='CANCEL',
            font_size='15sp',
            bold=True,
            background_normal='',
            background_color=[0.13, 0.15, 0.20, 1],
            color=[0.60, 0.64, 0.72, 1],
        )
        confirm_btn = Button(
            text='RESET',
            font_size='15sp',
            bold=True,
            background_normal='',
            background_color=[0.93, 0.27, 0.32, 1],
            color=[1, 1, 1, 1],
        )

        btn_row.add_widget(cancel_btn)
        btn_row.add_widget(confirm_btn)
        content.add_widget(btn_row)

        popup = Popup(
            title='Factory Reset',
            title_color=[0.93, 0.27, 0.32, 1],
            title_size='18sp',
            content=content,
            size_hint=(0.8, 0.45),
            separator_color=[0.93, 0.27, 0.32, 1],
            background_color=[0.08, 0.09, 0.12, 1],
            auto_dismiss=False,
        )

        cancel_btn.bind(on_release=popup.dismiss)
        confirm_btn.bind(on_release=lambda x: self._do_factory_reset(popup))
        popup.open()

    def _do_factory_reset(self, popup):
        """Execute factory reset: clear admin config and password from DB."""
        app = App.get_running_app()

        # Delete admin settings from config table
        try:
            app.db.conn.execute(
                "DELETE FROM config WHERE key = 'admin_settings'"
            )
            app.db.conn.execute(
                "DELETE FROM config WHERE key = 'admin_password_hash'"
            )
            app.db.conn.commit()
        except Exception:
            pass

        popup.dismiss()

        # Reload the form with defaults
        self._load_current_settings()
        self._update_password_info()
        self.ids.admin_status_label.text = (
            '[color=fac238]Factory reset complete. Restart app to apply.[/color]'
        )
        self.ids.admin_status_label.markup = True

    def go_back(self):
        """Navigate back to settings screen."""
        app = App.get_running_app()
        app.go_screen('settings')


# ============================================================
# PASSWORD DIALOG - shown before entering admin screen
# ============================================================

def show_admin_password_dialog(on_success):
    """
    Show a password dialog popup. Calls on_success() if correct.

    Usage from SettingsScreen:
        show_admin_password_dialog(lambda: app.go_screen('admin'))
    """
    app = App.get_running_app()

    # Ensure password hash exists in DB
    stored_hash = app.db.get_admin_password_hash()
    if stored_hash is None:
        # First time: hash the default and store it
        default_hash = hashlib.sha256(
            DEFAULT_ADMIN_PASSWORD.encode()
        ).hexdigest()
        app.db.set_admin_password_hash(default_hash)
        stored_hash = default_hash

    content = BoxLayout(orientation='vertical', padding=12, spacing=10)

    content.add_widget(Label(
        text='Enter admin password',
        font_size='16sp',
        color=[0.96, 0.97, 0.98, 1],
        size_hint_y=None,
        height=30,
        halign='center',
        text_size=(350, None),
    ))

    pw_input = TextInput(
        hint_text='Password',
        font_size='18sp',
        multiline=False,
        password=True,
        size_hint_y=None,
        height=50,
        background_color=[0.07, 0.09, 0.13, 1],
        foreground_color=[0.96, 0.97, 0.98, 1],
        cursor_color=[0.00, 0.82, 0.73, 1],
        hint_text_color=[0.20, 0.22, 0.28, 1],
        padding=[12, 12],
    )
    content.add_widget(pw_input)

    error_label = Label(
        text='',
        font_size='13sp',
        color=[0.93, 0.27, 0.32, 1],
        size_hint_y=None,
        height=22,
        halign='center',
        text_size=(350, None),
    )
    content.add_widget(error_label)

    btn_row = BoxLayout(spacing=12, size_hint_y=None, height=54)

    cancel_btn = Button(
        text='CANCEL',
        font_size='15sp',
        bold=True,
        background_normal='',
        background_color=[0.13, 0.15, 0.20, 1],
        color=[0.60, 0.64, 0.72, 1],
    )

    unlock_btn = Button(
        text='UNLOCK',
        font_size='15sp',
        bold=True,
        background_normal='',
        background_color=[0.00, 0.82, 0.73, 1],
        color=[0.02, 0.05, 0.08, 1],
    )

    btn_row.add_widget(cancel_btn)
    btn_row.add_widget(unlock_btn)
    content.add_widget(btn_row)

    popup = Popup(
        title='Admin Access',
        title_color=[0.00, 0.82, 0.73, 1],
        title_size='18sp',
        content=content,
        size_hint=(0.85, 0.48),
        separator_color=[0.00, 0.82, 0.73, 1],
        background_color=[0.08, 0.09, 0.12, 1],
        auto_dismiss=False,
    )

    def _check_password(instance):
        entered = pw_input.text
        entered_hash = hashlib.sha256(entered.encode()).hexdigest()
        # Re-read stored hash in case it was updated
        current_hash = app.db.get_admin_password_hash()
        if entered_hash == current_hash:
            popup.dismiss()
            on_success()
        else:
            error_label.text = 'Incorrect password'
            pw_input.text = ''

    cancel_btn.bind(on_release=lambda x: popup.dismiss())
    unlock_btn.bind(on_release=_check_password)
    # Also allow Enter key
    pw_input.bind(on_text_validate=_check_password)

    popup.open()
    # Focus the input
    Clock.schedule_once(lambda dt: setattr(pw_input, 'focus', True), 0.2)
