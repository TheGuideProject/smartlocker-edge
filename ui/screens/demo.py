"""
Demo Screen - Sensor Simulation Controls (2026 Redesign)

In TEST mode, provides buttons to simulate:
- Adding/removing RFID tags (cans on shelf)
- Changing shelf and scale weights
- Running a complete auto-demo sequence
- Viewing the event log

Design:
- Two-column layout with card-based sections
- Left: Shelf slot controls (add/remove cans)
- Right: Weight controls + Auto Demo
- Amber-tinted simulation buttons to distinguish from real actions
- Clear status feedback at bottom
"""

import time

from kivy.uix.screenmanager import Screen
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.lang import Builder
from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle, Rectangle


Builder.load_string('''
<DemoScreen>:
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
                text: 'DEMO CONTROLS'
                font_size: '18sp'
                bold: True
                color: 0.96, 0.97, 0.98, 1
                size_hint_x: 0.5
                halign: 'center'
                text_size: self.size
                valign: 'middle'

            Label:
                text: 'TEST MODE'
                font_size: '12sp'
                bold: True
                color: 0.98, 0.76, 0.22, 1
                size_hint_x: 0.3
                halign: 'right'
                text_size: self.size
                valign: 'middle'

        # ---- MAIN CONTENT (Two columns) ----
        BoxLayout:
            orientation: 'horizontal'
            padding: [8, 6, 8, 6]
            spacing: 8

            # LEFT PANEL: Slot Controls
            BoxLayout:
                orientation: 'vertical'
                spacing: 6
                size_hint_x: 0.5

                Label:
                    text: 'SHELF SLOTS'
                    font_size: '12sp'
                    bold: True
                    color: 0.38, 0.42, 0.50, 1
                    size_hint_y: None
                    height: '20dp'
                    halign: 'left'
                    text_size: self.size

                SimButton:
                    text: 'Add BASE  >>  Slot 1'
                    height: '50dp'
                    on_release: root.add_can(1, 'TAG-BASE-001')
                    canvas.before:
                        Color:
                            rgba: 0.06, 0.14, 0.10, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10]

                SimButton:
                    text: 'Add HARDENER  >>  Slot 2'
                    height: '50dp'
                    on_release: root.add_can(2, 'TAG-HARD-001')
                    canvas.before:
                        Color:
                            rgba: 0.06, 0.14, 0.10, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10]

                SimButton:
                    text: 'Add THINNER  >>  Slot 3'
                    height: '50dp'
                    on_release: root.add_can(3, 'TAG-THIN-001')
                    canvas.before:
                        Color:
                            rgba: 0.06, 0.14, 0.10, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10]

                SimButton:
                    text: 'Remove from Slot 1'
                    height: '50dp'
                    color: 0.98, 0.65, 0.25, 1
                    on_release: root.remove_can(1)
                    canvas.before:
                        Color:
                            rgba: 0.16, 0.10, 0.04, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10]

                SimButton:
                    text: 'Remove from Slot 2'
                    height: '50dp'
                    color: 0.98, 0.65, 0.25, 1
                    on_release: root.remove_can(2)
                    canvas.before:
                        Color:
                            rgba: 0.16, 0.10, 0.04, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10]

                Widget:
                    size_hint_y: 1

            # RIGHT PANEL: Weight & Auto Demo
            BoxLayout:
                orientation: 'vertical'
                spacing: 6
                size_hint_x: 0.5

                Label:
                    text: 'WEIGHT & ACTIONS'
                    font_size: '12sp'
                    bold: True
                    color: 0.38, 0.42, 0.50, 1
                    size_hint_y: None
                    height: '20dp'
                    halign: 'left'
                    text_size: self.size

                SimButton:
                    text: 'Shelf = 18.5 kg (3 cans)'
                    height: '50dp'
                    on_release: root.set_shelf_weight(18500)
                    canvas.before:
                        Color:
                            rgba: 0.08, 0.10, 0.16, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10]

                SimButton:
                    text: 'Shelf = 13 kg (less paint)'
                    height: '50dp'
                    on_release: root.set_shelf_weight(13000)
                    canvas.before:
                        Color:
                            rgba: 0.08, 0.10, 0.16, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10]

                SimButton:
                    text: 'Scale = 500g (base poured)'
                    height: '50dp'
                    on_release: root.set_scale_weight(500)
                    canvas.before:
                        Color:
                            rgba: 0.08, 0.10, 0.16, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10]

                SimButton:
                    text: 'Scale = 625g (+hardener)'
                    height: '50dp'
                    on_release: root.set_scale_weight(625)
                    canvas.before:
                        Color:
                            rgba: 0.08, 0.10, 0.16, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10]

                # Auto Demo button (prominent)
                Button:
                    text: 'RUN FULL AUTO DEMO'
                    font_size: '16sp'
                    bold: True
                    background_normal: ''
                    background_color: 0, 0, 0, 0
                    color: 0.02, 0.05, 0.08, 1
                    size_hint_y: None
                    height: '54dp'
                    on_release: root.run_auto_demo()
                    canvas.before:
                        Color:
                            rgba: 0.00, 0.82, 0.73, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10]

                # Status
                Label:
                    id: demo_status
                    text: 'Ready'
                    font_size: '12sp'
                    color: 0.38, 0.42, 0.50, 1
                    size_hint_y: None
                    height: '22dp'
                    halign: 'center'
                    text_size: self.size
                    markup: True

                Widget:
                    size_hint_y: 1
''')


class DemoScreen(Screen):

    def _set_status(self, text, color='6b7280'):
        self.ids.demo_status.text = f'[color={color}]{text}[/color]'

    def add_can(self, slot_num, tag_id):
        """Simulate placing a can on a slot."""
        app = App.get_running_app()
        slot_id = f'shelf1_slot{slot_num}'

        try:
            app.rfid.add_tag(slot_id, tag_id)
            app.inventory.poll()
            self._set_status(f'Added {tag_id} to slot {slot_num}', '00d1ba')
        except Exception as e:
            self._set_status(f'Error: {e}', 'ed4552')

    def remove_can(self, slot_num):
        """Simulate removing a can from a slot."""
        app = App.get_running_app()
        slot_id = f'shelf1_slot{slot_num}'

        try:
            app.rfid.remove_tag(slot_id)
            app.inventory.poll()
            self._set_status(f'Removed can from slot {slot_num}', 'fba640')
        except Exception as e:
            self._set_status(f'Error: {e}', 'ed4552')

    def set_shelf_weight(self, grams):
        """Set the shelf weight."""
        app = App.get_running_app()
        try:
            app.weight.set_weight('shelf1', grams)
            self._set_status(f'Shelf weight: {grams/1000:.1f} kg', '5494d9')
        except Exception as e:
            self._set_status(f'Error: {e}', 'ed4552')

    def set_scale_weight(self, grams):
        """Set the mixing scale weight."""
        app = App.get_running_app()
        try:
            app.weight.set_weight('mixing_scale', grams)
            self._set_status(f'Scale weight: {grams} g', '5494d9')
        except Exception as e:
            self._set_status(f'Error: {e}', 'ed4552')

    def run_auto_demo(self):
        """Run a complete demo sequence with visual steps."""
        self._set_status('Running auto demo...', 'fac438')
        self._demo_step = 0
        Clock.schedule_once(self._auto_demo_next, 0.3)

    def _auto_demo_next(self, dt):
        """Execute one step of the auto demo."""
        app = App.get_running_app()
        step = self._demo_step

        try:
            if step == 0:
                self._set_status('Step 1: Adding 3 cans to shelf...', 'fac438')
                app.rfid.add_tag('shelf1_slot1', 'TAG-BASE-001')
                app.rfid.add_tag('shelf1_slot2', 'TAG-HARD-001')
                app.rfid.add_tag('shelf1_slot3', 'TAG-THIN-001')
                app.weight.set_weight('shelf1', 18500)
                app.inventory.poll()

            elif step == 1:
                self._set_status('Step 2: Starting mixing session...', 'fac438')
                app.inventory.active_session = True
                app.mixing.start_session(
                    recipe_id='RCP-001',
                    user_name='Demo Crew',
                    job_id='JOB-DEMO-001',
                )
                app.mixing.show_recipe(base_amount_g=500.0)

            elif step == 2:
                self._set_status('Step 3: Picking base can...', 'fac438')
                app.mixing.advance_to_pick_base()
                app.rfid.remove_tag('shelf1_slot1')
                app.inventory.poll()
                app.mixing.confirm_base_picked('TAG-BASE-001')

            elif step == 3:
                self._set_status('Step 4: Weighing base (500g)...', 'fac438')
                app.weight.set_weight('mixing_scale', 200)
                app.mixing.tare_scale()
                app.weight.set_weight('mixing_scale', 702)
                app.mixing.confirm_base_weighed()

            elif step == 4:
                self._set_status('Step 5: Picking hardener...', 'fac438')
                app.rfid.remove_tag('shelf1_slot2')
                app.inventory.poll()
                app.mixing.confirm_hardener_picked('TAG-HARD-001')

            elif step == 5:
                self._set_status('Step 6: Weighing hardener...', 'fac438')
                app.weight.set_weight('mixing_scale', 828)
                app.mixing.confirm_hardener_weighed()

            elif step == 6:
                self._set_status('Step 7: Confirming mix & pot-life...', 'fac438')
                app.mixing.confirm_mix()
                app.mixing.skip_thinner()

            elif step == 7:
                self._set_status('Step 8: Returning cans...', 'fac438')
                app.mixing.return_cans_phase()
                app.rfid.add_tag('shelf1_slot1', 'TAG-BASE-001')
                app.rfid.add_tag('shelf1_slot2', 'TAG-HARD-001')
                app.weight.set_weight('shelf1', 13800)
                app.inventory.poll()

            elif step == 8:
                app.mixing.complete_session()
                app.inventory.active_session = False
                events = len(app.event_log)
                self._set_status(
                    f'Demo complete! {events} events generated', '00d1ba'
                )
                return  # Done

        except Exception as e:
            self._set_status(f'Demo error at step {step}: {e}', 'ed4552')
            return

        self._demo_step += 1
        Clock.schedule_once(self._auto_demo_next, 0.8)
