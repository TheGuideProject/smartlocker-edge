"""
SensorTestScreen — Live hardware diagnostics with 4 tabbed panels.

Tabs: RFID | WEIGHT | LED | BUZZER
Each tab shows: status, driver type, health, live data, action buttons.
"""

import time
import logging

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Rectangle, Line, Ellipse
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.app import App
from kivy.uix.screenmanager import Screen

from ui.app import DS

logger = logging.getLogger("smartlocker.sensor_test")


def _card(orientation="vertical", padding=None, spacing=None):
    """Create a dark rounded card container."""
    bx = BoxLayout(
        orientation=orientation,
        padding=padding or [dp(DS.PAD_CARD)] * 4,
        spacing=spacing or dp(DS.SPACING),
    )
    with bx.canvas.before:
        Color(*DS.BG_CARD)
        bx._bg = RoundedRectangle(pos=bx.pos, size=bx.size, radius=[dp(DS.RADIUS)])
    bx.bind(
        pos=lambda w, *a: setattr(w._bg, "pos", w.pos),
        size=lambda w, *a: setattr(w._bg, "size", w.size),
    )
    return bx


def _badge(text, color=DS.SUCCESS, font_size="12sp"):
    """Create a colored badge label."""
    lbl = Label(
        text=text,
        font_size=font_size,
        bold=True,
        color=color,
        size_hint=(None, None),
        size=(dp(90), dp(24)),
        halign="center",
        valign="middle",
    )
    lbl.bind(size=lbl.setter("text_size"))
    with lbl.canvas.before:
        Color(*color[:3], 0.15)
        lbl._bg = RoundedRectangle(pos=lbl.pos, size=lbl.size, radius=[dp(4)])
    lbl.bind(
        pos=lambda w, *a: setattr(w._bg, "pos", w.pos),
        size=lambda w, *a: setattr(w._bg, "size", w.size),
    )
    return lbl


class SensorTestScreen(Screen):
    """Hardware diagnostics screen with 4 sensor tabs."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._active_tab = "rfid"
        self._clock_events = []
        self._content_area = None
        self._tab_buttons = {}
        self._built = False

        # Live data caches
        self._rfid_history = []
        self._weight_readings = {}  # channel -> list of (timestamp, grams)
        self._led_states = {}
        self._last_poll_time = 0

    def on_enter(self, *args):
        if not self._built:
            self._build_ui()
            self._built = True
        self._switch_tab(self._active_tab)
        # Start polling
        ev = Clock.schedule_interval(self._poll, 0.5)
        self._clock_events.append(ev)

    def on_leave(self, *args):
        for ev in self._clock_events:
            ev.cancel()
        self._clock_events.clear()

    # ═══════════════════════════════════════════════════════
    # BUILD UI
    # ═══════════════════════════════════════════════════════

    def _build_ui(self):
        root = BoxLayout(orientation="vertical")

        # ── Status bar ──
        bar = BoxLayout(
            size_hint_y=None, height=dp(DS.STATUS_BAR_H),
            padding=[dp(12), dp(4)], spacing=dp(8),
        )
        with bar.canvas.before:
            Color(*DS.BG_STATUS_BAR)
            bar._bg = Rectangle(pos=bar.pos, size=bar.size)
            Color(*DS.PRIMARY, 0.25)
            bar._line = Rectangle(pos=bar.pos, size=(bar.width, 1))
        bar.bind(
            pos=lambda w, *a: (setattr(w._bg, "pos", w.pos), setattr(w._line, "pos", w.pos)),
            size=lambda w, *a: (setattr(w._bg, "size", w.size), setattr(w._line, "size", (w.width, 1))),
        )
        # Back button
        back = Button(
            text="<", font_size="22sp", bold=True,
            size_hint=(None, 1), width=dp(50),
            background_normal="", background_color=DS.BG_CARD_HOVER,
            color=DS.TEXT_SECONDARY,
        )
        back.bind(on_release=lambda x: self._go_back())
        bar.add_widget(back)
        # Title
        title = Label(
            text="SENSOR TESTING", font_size=DS.FONT_H2, bold=True,
            color=DS.TEXT_PRIMARY, halign="center", valign="middle", markup=True,
        )
        title.bind(size=title.setter("text_size"))
        bar.add_widget(title)
        bar.add_widget(Widget(size_hint=(None, 1), width=dp(50)))
        root.add_widget(bar)

        # ── Tab bar ──
        tab_bar = BoxLayout(
            size_hint_y=None, height=dp(48),
            spacing=dp(2), padding=[dp(8), dp(4)],
        )
        with tab_bar.canvas.before:
            Color(*DS.BG_DARK)
            tab_bar._bg = Rectangle(pos=tab_bar.pos, size=tab_bar.size)
        tab_bar.bind(
            pos=lambda w, *a: setattr(w._bg, "pos", w.pos),
            size=lambda w, *a: setattr(w._bg, "size", w.size),
        )

        tabs = [
            ("rfid", "RFID"),
            ("weight", "WEIGHT"),
            ("led", "LED"),
            ("buzzer", "BUZZER"),
        ]
        for tab_id, label in tabs:
            btn = Button(
                text=label, font_size="14sp", bold=True,
                background_normal="",
                background_color=DS.PRIMARY if tab_id == self._active_tab else DS.BG_CARD,
                color=DS.BG_DARK if tab_id == self._active_tab else DS.TEXT_SECONDARY,
                size_hint_y=None, height=dp(40),
            )
            btn.tab_id = tab_id
            btn.bind(on_release=lambda x: self._switch_tab(x.tab_id))
            self._tab_buttons[tab_id] = btn
            tab_bar.add_widget(btn)
        root.add_widget(tab_bar)

        # ── Content area (swapped per tab) ──
        self._content_area = BoxLayout(
            orientation="vertical",
            padding=[dp(DS.PAD_SCREEN)] * 4,
            spacing=dp(DS.SPACING),
        )
        root.add_widget(self._content_area)

        self.add_widget(root)

    # ═══════════════════════════════════════════════════════
    # TAB SWITCHING
    # ═══════════════════════════════════════════════════════

    def _switch_tab(self, tab_id):
        self._active_tab = tab_id
        # Update tab button styles
        for tid, btn in self._tab_buttons.items():
            if tid == tab_id:
                btn.background_color = DS.PRIMARY
                btn.color = DS.BG_DARK
            else:
                btn.background_color = DS.BG_CARD
                btn.color = DS.TEXT_SECONDARY
        # Rebuild content
        self._content_area.clear_widgets()
        if tab_id == "rfid":
            self._build_rfid_tab()
        elif tab_id == "weight":
            self._build_weight_tab()
        elif tab_id == "led":
            self._build_led_tab()
        elif tab_id == "buzzer":
            self._build_buzzer_tab()

    # ═══════════════════════════════════════════════════════
    # STATUS HEADER (shared by all tabs)
    # ═══════════════════════════════════════════════════════

    def _build_status_header(self, sensor_name):
        """Build status + driver info header card."""
        app = App.get_running_app()
        driver_status = getattr(app, "driver_status", {})
        driver_type = driver_status.get(sensor_name, "unknown")

        # Check health
        driver = self._get_driver(sensor_name)
        healthy = False
        if driver and hasattr(driver, "is_healthy"):
            try:
                healthy = driver.is_healthy()
            except Exception:
                healthy = False

        card = _card(orientation="horizontal", padding=[dp(12), dp(8)], spacing=dp(16))
        card.size_hint_y = None
        card.height = dp(56)

        # Status dot + label
        status_box = BoxLayout(orientation="horizontal", spacing=dp(6), size_hint_x=0.3)
        dot_color = DS.SUCCESS if healthy else DS.DANGER
        dot = Widget(size_hint=(None, None), size=(dp(12), dp(12)))
        with dot.canvas:
            Color(*dot_color)
            dot._el = Ellipse(pos=dot.pos, size=dot.size)
        dot.bind(pos=lambda w, *a: setattr(w._el, "pos", w.pos))
        status_box.add_widget(dot)
        status_box.add_widget(Label(
            text="OK" if healthy else "ERROR",
            font_size="14sp", bold=True,
            color=dot_color, halign="left",
            size_hint_x=1,
        ))
        card.add_widget(status_box)

        # Driver badge
        drv_color = DS.SUCCESS if driver_type == "real" else DS.ACCENT
        card.add_widget(_badge(
            f"{'REAL' if driver_type == 'real' else 'FAKE'}",
            color=drv_color,
        ))

        # Health label
        card.add_widget(Label(
            text=f"[b]Health:[/b] {'Healthy' if healthy else 'Unhealthy'}",
            font_size="13sp", color=DS.TEXT_SECONDARY, markup=True,
            halign="right",
        ))

        self._content_area.add_widget(card)

    # ═══════════════════════════════════════════════════════
    # RFID TAB
    # ═══════════════════════════════════════════════════════

    def _build_rfid_tab(self):
        self._build_status_header("rfid")

        # Last tag card
        last_card = _card()
        last_card.size_hint_y = None
        last_card.height = dp(100)

        last_card.add_widget(Label(
            text="Last Tag Detected", font_size=DS.FONT_H3, bold=True,
            color=DS.TEXT_PRIMARY, size_hint_y=None, height=dp(24),
            halign="left",
        ))

        self._rfid_uid_label = Label(
            text="No tag scanned yet",
            font_size=DS.FONT_H1, bold=True,
            color=DS.PRIMARY, halign="center", valign="middle",
            markup=True,
        )
        last_card.add_widget(self._rfid_uid_label)

        self._rfid_info_label = Label(
            text="", font_size=DS.FONT_SMALL,
            color=DS.TEXT_SECONDARY, halign="center", markup=True,
        )
        last_card.add_widget(self._rfid_info_label)
        self._content_area.add_widget(last_card)

        # History (scrollable)
        history_card = _card()
        history_card.add_widget(Label(
            text="Scan History", font_size=DS.FONT_H3, bold=True,
            color=DS.TEXT_PRIMARY, size_hint_y=None, height=dp(24),
            halign="left",
        ))
        self._rfid_history_box = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=None)
        self._rfid_history_box.bind(minimum_height=self._rfid_history_box.setter("height"))
        scroll = ScrollView()
        scroll.add_widget(self._rfid_history_box)
        history_card.add_widget(scroll)
        self._content_area.add_widget(history_card)

        # Action button
        btn = Button(
            text="SCAN NOW", font_size="16sp", bold=True,
            size_hint_y=None, height=dp(DS.BTN_HEIGHT_LG),
            background_normal="", background_color=DS.PRIMARY,
            color=DS.BG_DARK,
        )
        btn.bind(on_release=lambda x: self._rfid_scan_now())
        self._content_area.add_widget(btn)

    def _rfid_scan_now(self):
        """Trigger a single RFID poll and display results."""
        driver = self._get_driver("rfid")
        if not driver:
            return
        try:
            tags = driver.poll_tags()
            if tags:
                for tag in tags:
                    uid = tag.tag_id if hasattr(tag, "tag_id") else str(tag)
                    self._rfid_uid_label.text = uid
                    product = getattr(tag, "product_data", None) or ""
                    signal = getattr(tag, "signal_strength", 0)
                    self._rfid_info_label.text = (
                        f"Signal: {signal}  |  "
                        f"Product: {product if product else 'N/A'}"
                    )
                    # Add to history
                    ts = time.strftime("%H:%M:%S")
                    self._rfid_history.insert(0, f"{ts}  {uid}")
                    self._rfid_history = self._rfid_history[:10]
                    self._update_rfid_history()
            else:
                self._rfid_uid_label.text = "No tag found"
                self._rfid_info_label.text = "Hold a tag near the reader"
        except Exception as e:
            self._rfid_uid_label.text = "Error"
            self._rfid_info_label.text = str(e)[:60]

    def _update_rfid_history(self):
        self._rfid_history_box.clear_widgets()
        for entry in self._rfid_history:
            lbl = Label(
                text=entry, font_size=DS.FONT_SMALL,
                color=DS.TEXT_SECONDARY, size_hint_y=None, height=dp(22),
                halign="left",
            )
            lbl.bind(size=lbl.setter("text_size"))
            self._rfid_history_box.add_widget(lbl)

    # ═══════════════════════════════════════════════════════
    # WEIGHT TAB
    # ═══════════════════════════════════════════════════════

    def _build_weight_tab(self):
        self._build_status_header("weight")

        # Live weight display
        weight_card = _card()
        weight_card.size_hint_y = None
        weight_card.height = dp(160)

        weight_card.add_widget(Label(
            text="Live Weight", font_size=DS.FONT_H3, bold=True,
            color=DS.TEXT_PRIMARY, size_hint_y=None, height=dp(24),
            halign="left",
        ))

        self._weight_value_label = Label(
            text="0.0 g", font_size=DS.FONT_HERO, bold=True,
            color=DS.PRIMARY, halign="center", valign="middle",
        )
        weight_card.add_widget(self._weight_value_label)

        # Stability + raw value row
        info_row = BoxLayout(size_hint_y=None, height=dp(24), spacing=dp(16))
        self._weight_stable_label = Label(
            text="", font_size=DS.FONT_SMALL,
            color=DS.TEXT_SECONDARY, halign="left", markup=True,
        )
        self._weight_raw_label = Label(
            text="Raw: --", font_size=DS.FONT_TINY,
            color=DS.TEXT_MUTED, halign="right", markup=True,
        )
        info_row.add_widget(self._weight_stable_label)
        info_row.add_widget(self._weight_raw_label)
        weight_card.add_widget(info_row)

        self._content_area.add_widget(weight_card)

        # Weight history graph placeholder
        graph_card = _card()
        graph_card.size_hint_y = None
        graph_card.height = dp(80)
        self._weight_graph_points = []
        self._weight_graph_widget = Widget()
        graph_card.add_widget(self._weight_graph_widget)
        self._content_area.add_widget(graph_card)

        # Buttons row
        btn_row = BoxLayout(size_hint_y=None, height=dp(DS.BTN_HEIGHT_LG), spacing=dp(8))
        tare_btn = Button(
            text="TARE (ZERO)", font_size="16sp", bold=True,
            background_normal="", background_color=DS.SECONDARY,
            color=(1, 1, 1, 1),
        )
        tare_btn.bind(on_release=lambda x: self._weight_tare())
        btn_row.add_widget(tare_btn)

        cal_btn = Button(
            text="CALIBRATE", font_size="16sp", bold=True,
            background_normal="", background_color=DS.ACCENT,
            color=DS.BG_DARK,
        )
        cal_btn.bind(on_release=lambda x: self._weight_calibrate())
        btn_row.add_widget(cal_btn)

        self._content_area.add_widget(btn_row)

    def _weight_tare(self):
        driver = self._get_driver("weight")
        if driver:
            try:
                channels = driver.get_channels()
                for ch in channels:
                    driver.tare(ch)
                self._weight_value_label.text = "0.0 g"
                self._weight_value_label.color = DS.SUCCESS
                Clock.schedule_once(lambda dt: setattr(self._weight_value_label, "color", DS.PRIMARY), 1)
            except Exception as e:
                logger.warning(f"Tare failed: {e}")

    def _weight_calibrate(self):
        """Open calibration wizard popup."""
        try:
            from ui.widgets.calibration_wizard import CalibrationWizard
            app = App.get_running_app()
            wizard = CalibrationWizard(weight_driver=getattr(app, "weight", None))
            wizard.open()
        except ImportError:
            logger.warning("CalibrationWizard not yet implemented")

    def _update_weight_display(self):
        """Read current weight and update display."""
        driver = self._get_driver("weight")
        if not driver:
            return
        try:
            channels = driver.get_channels()
            if channels:
                reading = driver.read_weight(channels[0])
                if reading:
                    grams = reading.grams if hasattr(reading, "grams") else 0
                    stable = reading.stable if hasattr(reading, "stable") else False
                    raw = reading.raw_value if hasattr(reading, "raw_value") else 0

                    # Format display
                    if abs(grams) >= 1000:
                        self._weight_value_label.text = f"{grams / 1000:.2f} kg"
                    else:
                        self._weight_value_label.text = f"{grams:.1f} g"

                    # Stability
                    if stable:
                        self._weight_stable_label.text = "[color=33d17a]● STABLE[/color]"
                    else:
                        self._weight_stable_label.text = "[color=fac222]● SETTLING...[/color]"

                    self._weight_raw_label.text = f"Raw: {raw}"

                    # Graph data
                    self._weight_graph_points.append(grams)
                    if len(self._weight_graph_points) > 50:
                        self._weight_graph_points = self._weight_graph_points[-50:]
                    self._draw_weight_graph()
        except Exception as e:
            logger.debug(f"Weight read error: {e}")

    def _draw_weight_graph(self):
        """Draw simple line graph of weight readings."""
        w = self._weight_graph_widget
        w.canvas.clear()
        if len(self._weight_graph_points) < 2:
            return

        pts = self._weight_graph_points
        min_v = min(pts) - 10
        max_v = max(pts) + 10
        rng = max_v - min_v if max_v != min_v else 1

        with w.canvas:
            # Grid
            Color(*DS.DIVIDER)
            for i in range(5):
                y = w.y + (w.height * i / 4)
                Line(points=[w.x, y, w.x + w.width, y], width=0.5)

            # Line
            Color(*DS.PRIMARY)
            points = []
            for i, v in enumerate(pts):
                x = w.x + (w.width * i / (len(pts) - 1))
                y = w.y + (w.height * (v - min_v) / rng)
                points.extend([x, y])
            if len(points) >= 4:
                Line(points=points, width=1.5)

    # ═══════════════════════════════════════════════════════
    # LED TAB
    # ═══════════════════════════════════════════════════════

    def _build_led_tab(self):
        self._build_status_header("led")

        from hal.interfaces import LEDColor, LEDPattern

        # Slot grid
        slot_card = _card()
        slot_card.add_widget(Label(
            text="Slot LEDs", font_size=DS.FONT_H3, bold=True,
            color=DS.TEXT_PRIMARY, size_hint_y=None, height=dp(24),
            halign="left",
        ))

        grid = GridLayout(cols=4, spacing=dp(8), size_hint_y=None, height=dp(80))
        app = App.get_running_app()
        slot_count = getattr(app, "slot_count", 4) if app else 4

        colors = [LEDColor.OFF, LEDColor.GREEN, LEDColor.RED, LEDColor.YELLOW, LEDColor.BLUE, LEDColor.WHITE]
        color_names = ["OFF", "GREEN", "RED", "YELLOW", "BLUE", "WHITE"]
        color_rgbas = [
            DS.SLOT_EMPTY, DS.SUCCESS, DS.DANGER,
            DS.WARNING, DS.SECONDARY, DS.TEXT_PRIMARY,
        ]

        self._led_slot_index = {}  # slot_id -> current color index

        for i in range(slot_count):
            slot_id = f"shelf1_slot{i + 1}"
            self._led_slot_index[slot_id] = 0

            btn = Button(
                text=f"S{i + 1}\nOFF", font_size="14sp", bold=True,
                background_normal="",
                background_color=DS.SLOT_EMPTY,
                color=DS.TEXT_PRIMARY,
                halign="center",
            )
            btn.slot_id = slot_id
            btn.color_list = colors
            btn.color_names = color_names
            btn.color_rgbas = color_rgbas
            btn.bind(on_release=lambda x: self._led_toggle_slot(x))
            grid.add_widget(btn)

        slot_card.add_widget(grid)
        self._content_area.add_widget(slot_card)

        # Pattern selector
        pattern_card = _card(orientation="horizontal", spacing=dp(6))
        pattern_card.size_hint_y = None
        pattern_card.height = dp(54)

        patterns = [
            ("SOLID", LEDPattern.SOLID),
            ("BLINK", LEDPattern.BLINK_SLOW),
            ("FAST", LEDPattern.BLINK_FAST),
            ("PULSE", LEDPattern.PULSE),
        ]
        self._current_led_pattern = LEDPattern.SOLID

        for name, pattern in patterns:
            btn = Button(
                text=name, font_size="13sp", bold=True,
                background_normal="",
                background_color=DS.PRIMARY if pattern == LEDPattern.SOLID else DS.BG_CARD_HOVER,
                color=DS.BG_DARK if pattern == LEDPattern.SOLID else DS.TEXT_SECONDARY,
            )
            btn.pattern = pattern
            btn.bind(on_release=lambda x: self._led_set_pattern(x))
            pattern_card.add_widget(btn)

        self._content_area.add_widget(pattern_card)

        # All off / all on
        btn_row = BoxLayout(size_hint_y=None, height=dp(DS.BTN_HEIGHT_MD), spacing=dp(8))
        off_btn = Button(
            text="ALL OFF", font_size="16sp", bold=True,
            background_normal="", background_color=DS.BG_CARD_HOVER,
            color=DS.TEXT_SECONDARY,
        )
        off_btn.bind(on_release=lambda x: self._led_all_off())
        btn_row.add_widget(off_btn)

        on_btn = Button(
            text="ALL GREEN", font_size="16sp", bold=True,
            background_normal="", background_color=DS.SUCCESS,
            color=DS.BG_DARK,
        )
        on_btn.bind(on_release=lambda x: self._led_all_on())
        btn_row.add_widget(on_btn)
        self._content_area.add_widget(btn_row)

    def _led_toggle_slot(self, btn):
        from hal.interfaces import LEDColor
        slot_id = btn.slot_id
        idx = (self._led_slot_index.get(slot_id, 0) + 1) % len(btn.color_list)
        self._led_slot_index[slot_id] = idx

        color = btn.color_list[idx]
        name = btn.color_names[idx]
        rgba = btn.color_rgbas[idx]

        btn.text = f"S{slot_id[-1]}\n{name}"
        btn.background_color = rgba

        driver = self._get_driver("led")
        if driver:
            try:
                if color == LEDColor.OFF:
                    driver.clear_slot(slot_id)
                else:
                    driver.set_slot(slot_id, color, self._current_led_pattern)
            except Exception as e:
                logger.debug(f"LED set error: {e}")

    def _led_set_pattern(self, btn):
        self._current_led_pattern = btn.pattern
        # Update button styles
        parent = btn.parent
        if parent:
            for child in parent.children:
                if hasattr(child, "pattern"):
                    if child.pattern == btn.pattern:
                        child.background_color = DS.PRIMARY
                        child.color = DS.BG_DARK
                    else:
                        child.background_color = DS.BG_CARD_HOVER
                        child.color = DS.TEXT_SECONDARY

    def _led_all_off(self):
        driver = self._get_driver("led")
        if driver:
            try:
                driver.clear_all()
            except Exception:
                pass

    def _led_all_on(self):
        from hal.interfaces import LEDColor
        driver = self._get_driver("led")
        if driver:
            try:
                app = App.get_running_app()
                slot_count = getattr(app, "slot_count", 4) if app else 4
                for i in range(slot_count):
                    driver.set_slot(f"shelf1_slot{i + 1}", LEDColor.GREEN, self._current_led_pattern)
            except Exception:
                pass

    # ═══════════════════════════════════════════════════════
    # BUZZER TAB
    # ═══════════════════════════════════════════════════════

    def _build_buzzer_tab(self):
        self._build_status_header("buzzer")

        from hal.interfaces import BuzzerPattern

        card = _card()
        card.add_widget(Label(
            text="Play Sound Pattern", font_size=DS.FONT_H3, bold=True,
            color=DS.TEXT_PRIMARY, size_hint_y=None, height=dp(24),
            halign="left",
        ))

        patterns = [
            ("CONFIRM", BuzzerPattern.CONFIRM, "Single beep (1000Hz)", DS.SUCCESS),
            ("WARNING", BuzzerPattern.WARNING, "Double beep (800Hz)", DS.WARNING),
            ("ERROR", BuzzerPattern.ERROR, "Long buzz (400Hz)", DS.DANGER),
            ("TARGET", BuzzerPattern.TARGET_REACHED, "Rising 3-tone", DS.PRIMARY),
            ("TICK", BuzzerPattern.TICK, "Short click (1500Hz)", DS.TEXT_SECONDARY),
        ]

        grid = GridLayout(cols=2, spacing=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))

        for name, pattern, desc, color in patterns:
            btn = Button(
                text=f"{name}\n[size=11sp]{desc}[/size]",
                font_size="15sp", bold=True,
                background_normal="",
                background_color=(*color[:3], 0.3),
                color=color,
                size_hint_y=None, height=dp(64),
                markup=True, halign="center",
            )
            btn.pattern = pattern
            btn.bind(on_release=lambda x: self._buzzer_play(x.pattern))
            grid.add_widget(btn)

        # Add spacer if odd number
        if len(patterns) % 2:
            grid.add_widget(Widget())

        card.add_widget(grid)
        self._content_area.add_widget(card)

        # Stop button
        stop_btn = Button(
            text="STOP", font_size="16sp", bold=True,
            size_hint_y=None, height=dp(DS.BTN_HEIGHT_MD),
            background_normal="", background_color=DS.DANGER,
            color=(1, 1, 1, 1),
        )
        stop_btn.bind(on_release=lambda x: self._buzzer_stop())
        self._content_area.add_widget(stop_btn)

    def _buzzer_play(self, pattern):
        driver = self._get_driver("buzzer")
        if driver:
            try:
                driver.play(pattern)
            except Exception as e:
                logger.debug(f"Buzzer play error: {e}")

    def _buzzer_stop(self):
        driver = self._get_driver("buzzer")
        if driver:
            try:
                driver.stop()
            except Exception:
                pass

    # ═══════════════════════════════════════════════════════
    # POLLING
    # ═══════════════════════════════════════════════════════

    def _poll(self, dt):
        """Periodic update for active tab."""
        if self._active_tab == "weight":
            self._update_weight_display()
        elif self._active_tab == "rfid":
            # Auto-poll RFID
            pass  # Only poll on SCAN NOW button press

    # ═══════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════

    def _get_driver(self, sensor_name):
        """Get the driver instance from the running app."""
        app = App.get_running_app()
        if not app:
            return None
        drivers = {
            "rfid": getattr(app, "rfid", None),
            "weight": getattr(app, "weight", None),
            "led": getattr(app, "led", None),
            "buzzer": getattr(app, "buzzer", None),
        }
        return drivers.get(sensor_name)

    def _go_back(self):
        if self.manager:
            self.manager.current = "settings"
