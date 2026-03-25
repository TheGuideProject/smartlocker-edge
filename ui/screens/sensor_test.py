"""
SensorTestScreen - Live hardware diagnostics with 4 tabbed panels.

Tabs: RFID | WEIGHT | LED | BUZZER
Each tab shows: driver status, health indicator, live data, action buttons.

Designed for 800x480 touchscreen with 64dp touch targets for gloved hands.
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


# ================================================================
# HELPERS
# ================================================================

def _card(orientation="vertical", padding=None, spacing=None, bg=None):
    """Create a dark rounded card container."""
    bx = BoxLayout(
        orientation=orientation,
        padding=padding or [dp(DS.PAD_CARD)] * 4,
        spacing=spacing or dp(DS.SPACING),
    )
    bg_color = bg or DS.BG_CARD
    with bx.canvas.before:
        Color(*bg_color)
        bx._bg = RoundedRectangle(pos=bx.pos, size=bx.size,
                                   radius=[dp(DS.RADIUS)])
    bx.bind(
        pos=lambda w, *a: setattr(w._bg, "pos", w.pos),
        size=lambda w, *a: setattr(w._bg, "size", w.size),
    )
    return bx


def _badge(text, color=DS.SUCCESS, font_size="12sp"):
    """Create a small colored pill badge."""
    lbl = Label(
        text=text, font_size=font_size, bold=True,
        color=color, size_hint=(None, None),
        size=(dp(80), dp(24)), halign="center", valign="middle",
    )
    lbl.bind(size=lbl.setter("text_size"))
    with lbl.canvas.before:
        Color(*color[:3], 0.15)
        lbl._bg = RoundedRectangle(pos=lbl.pos, size=lbl.size,
                                    radius=[dp(4)])
    lbl.bind(
        pos=lambda w, *a: setattr(w._bg, "pos", w.pos),
        size=lambda w, *a: setattr(w._bg, "size", w.size),
    )
    return lbl


def _dot_widget(color, size=8):
    """Create a small colored dot (Ellipse widget)."""
    dot = Widget(size_hint=(None, None), size=(dp(size), dp(size)))
    with dot.canvas:
        Color(*color)
        dot._el = Ellipse(pos=dot.pos, size=dot.size)
    dot.bind(
        pos=lambda w, *a: setattr(w._el, "pos", w.pos),
        size=lambda w, *a: setattr(w._el, "size", w.size),
    )
    return dot


class SensorTestScreen(Screen):
    """Hardware diagnostics screen with 4 sensor tabs."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._active_tab = "rfid"
        self._clock_events = []
        self._content_area = None
        self._tab_buttons = {}
        self._tab_dots = {}
        self._built = False

        # Live data caches
        self._rfid_history = []
        self._weight_readings = []
        self._led_slot_index = {}
        self._current_led_pattern = None

        # Widget references (set when tab is built)
        self._rfid_uid_label = None
        self._rfid_info_label = None
        self._rfid_history_box = None
        self._weight_value_label = None
        self._weight_kg_label = None
        self._weight_stable_label = None
        self._weight_raw_label = None
        self._weight_graph_widget = None

    # ────────────────────────────────────────────────────────
    # LIFECYCLE
    # ────────────────────────────────────────────────────────

    def on_enter(self, *args):
        if not self._built:
            self._build_ui()
            self._built = True
        self._refresh_tab_dots()
        self._switch_tab(self._active_tab)
        # Weight polling at 300ms for live display
        ev_weight = Clock.schedule_interval(self._poll_weight, 0.3)
        self._clock_events.append(ev_weight)
        # Health dot refresh every 3s
        ev_health = Clock.schedule_interval(
            lambda dt: self._refresh_tab_dots(), 3.0)
        self._clock_events.append(ev_health)

    def on_leave(self, *args):
        for ev in self._clock_events:
            ev.cancel()
        self._clock_events.clear()

    # ────────────────────────────────────────────────────────
    # BUILD UI
    # ────────────────────────────────────────────────────────

    def _build_ui(self):
        root = BoxLayout(orientation="vertical")
        with root.canvas.before:
            Color(*DS.BG_DARK)
            root._bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(
            pos=lambda w, *a: setattr(w._bg, "pos", w.pos),
            size=lambda w, *a: setattr(w._bg, "size", w.size),
        )

        # ── Status bar ──
        bar = BoxLayout(
            size_hint_y=None, height=dp(DS.STATUS_BAR_H),
            padding=[dp(12), dp(4)], spacing=dp(8),
        )
        with bar.canvas.before:
            Color(*DS.BG_STATUS_BAR)
            bar._bg = Rectangle(pos=bar.pos, size=bar.size)
            Color(*DS.PRIMARY[:3], 0.25)
            bar._line = Rectangle(pos=bar.pos, size=(bar.width, 1))
        bar.bind(
            pos=lambda w, *a: (
                setattr(w._bg, "pos", w.pos),
                setattr(w._line, "pos", w.pos),
            ),
            size=lambda w, *a: (
                setattr(w._bg, "size", w.size),
                setattr(w._line, "size", (w.width, 1)),
            ),
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
            color=DS.TEXT_PRIMARY, halign="center", valign="middle",
        )
        title.bind(size=title.setter("text_size"))
        bar.add_widget(title)
        # Right spacer
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
            tab_box = BoxLayout(
                orientation="horizontal", spacing=dp(6),
                padding=[dp(4), 0],
            )
            # Health dot
            dot = _dot_widget(DS.TEXT_MUTED, size=8)
            self._tab_dots[tab_id] = dot
            tab_box.add_widget(Widget(size_hint_x=None, width=dp(4)))
            tab_box.add_widget(dot)

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
            tab_box.add_widget(btn)
            tab_bar.add_widget(tab_box)
        root.add_widget(tab_bar)

        # ── Content area ──
        self._content_area = BoxLayout(
            orientation="vertical",
            padding=[dp(DS.PAD_SCREEN)] * 4,
            spacing=dp(DS.SPACING),
        )
        root.add_widget(self._content_area)

        self.add_widget(root)

    # ────────────────────────────────────────────────────────
    # TAB SWITCHING
    # ────────────────────────────────────────────────────────

    def _switch_tab(self, tab_id):
        self._active_tab = tab_id
        for tid, btn in self._tab_buttons.items():
            if tid == tab_id:
                btn.background_color = DS.PRIMARY
                btn.color = DS.BG_DARK
            else:
                btn.background_color = DS.BG_CARD
                btn.color = DS.TEXT_SECONDARY
        self._content_area.clear_widgets()
        builders = {
            "rfid": self._build_rfid_tab,
            "weight": self._build_weight_tab,
            "led": self._build_led_tab,
            "buzzer": self._build_buzzer_tab,
        }
        builders[tab_id]()

    def _refresh_tab_dots(self):
        """Update health dots on each tab."""
        for sensor_name, dot in self._tab_dots.items():
            driver = self._get_driver(sensor_name)
            healthy = False
            if driver and hasattr(driver, "is_healthy"):
                try:
                    healthy = driver.is_healthy()
                except Exception:
                    healthy = False
            new_color = DS.SUCCESS if healthy else DS.DANGER
            dot.canvas.clear()
            with dot.canvas:
                Color(*new_color)
                dot._el = Ellipse(pos=dot.pos, size=dot.size)
            dot.bind(
                pos=lambda w, *a: setattr(w._el, "pos", w.pos),
                size=lambda w, *a: setattr(w._el, "size", w.size),
            )

    # ────────────────────────────────────────────────────────
    # STATUS HEADER (shared)
    # ────────────────────────────────────────────────────────

    def _build_status_header(self, sensor_name):
        """Status card showing driver type + health."""
        app = App.get_running_app()
        driver_status = getattr(app, "driver_status", {})
        driver_type = driver_status.get(sensor_name, "unknown")

        driver = self._get_driver(sensor_name)
        healthy = False
        if driver and hasattr(driver, "is_healthy"):
            try:
                healthy = driver.is_healthy()
            except Exception:
                healthy = False

        card = _card(orientation="horizontal",
                     padding=[dp(12), dp(8)], spacing=dp(16))
        card.size_hint_y = None
        card.height = dp(50)

        # Driver badge
        drv_color = DS.SUCCESS if driver_type == "real" else DS.ACCENT
        drv_label = "REAL" if driver_type == "real" else "FAKE"
        left_box = BoxLayout(orientation="horizontal", spacing=dp(6),
                             size_hint_x=0.35)
        left_box.add_widget(Label(
            text="Driver:", font_size=DS.FONT_SMALL,
            color=DS.TEXT_MUTED, halign="right", valign="middle",
            size_hint_x=0.5,
        ))
        left_box.add_widget(_badge(drv_label, color=drv_color))
        card.add_widget(left_box)

        # Spacer
        card.add_widget(Widget(size_hint_x=0.1))

        # Health
        right_box = BoxLayout(orientation="horizontal", spacing=dp(6),
                              size_hint_x=0.55)
        right_box.add_widget(Label(
            text="Health:", font_size=DS.FONT_SMALL,
            color=DS.TEXT_MUTED, halign="right", valign="middle",
            size_hint_x=0.4,
        ))
        health_color = DS.SUCCESS if healthy else DS.DANGER
        health_text = "OK" if healthy else "ERROR"
        dot = _dot_widget(health_color, size=10)
        right_box.add_widget(dot)
        right_box.add_widget(Label(
            text=health_text, font_size=DS.FONT_BODY, bold=True,
            color=health_color, halign="left", valign="middle",
        ))
        card.add_widget(right_box)

        self._content_area.add_widget(card)

    # ════════════════════════════════════════════════════════
    # RFID TAB
    # ════════════════════════════════════════════════════════

    def _build_rfid_tab(self):
        self._build_status_header("rfid")

        # ── Last tag card ──
        last_card = _card()
        last_card.size_hint_y = None
        last_card.height = dp(110)

        header = Label(
            text="Last Tag Detected", font_size=DS.FONT_H3, bold=True,
            color=DS.TEXT_PRIMARY, size_hint_y=None, height=dp(22),
            halign="left",
        )
        header.bind(size=header.setter("text_size"))
        last_card.add_widget(header)

        self._rfid_uid_label = Label(
            text="No tag scanned yet",
            font_size=DS.FONT_H1, bold=True,
            color=DS.PRIMARY, halign="center", valign="middle",
            markup=True,
        )
        last_card.add_widget(self._rfid_uid_label)

        self._rfid_info_label = Label(
            text="Press SCAN NOW to read tags",
            font_size=DS.FONT_SMALL,
            color=DS.TEXT_SECONDARY, halign="center", markup=True,
            size_hint_y=None, height=dp(20),
        )
        self._rfid_info_label.bind(
            size=self._rfid_info_label.setter("text_size"))
        last_card.add_widget(self._rfid_info_label)

        self._content_area.add_widget(last_card)

        # ── Scan history ──
        history_card = _card()
        hist_header = Label(
            text="Scan History (last 10)", font_size=DS.FONT_H3, bold=True,
            color=DS.TEXT_PRIMARY, size_hint_y=None, height=dp(22),
            halign="left",
        )
        hist_header.bind(size=hist_header.setter("text_size"))
        history_card.add_widget(hist_header)

        self._rfid_history_box = BoxLayout(
            orientation="vertical", spacing=dp(3),
            size_hint_y=None,
        )
        self._rfid_history_box.bind(
            minimum_height=self._rfid_history_box.setter("height"))
        scroll = ScrollView()
        scroll.add_widget(self._rfid_history_box)
        history_card.add_widget(scroll)
        self._content_area.add_widget(history_card)

        # Populate existing history
        self._render_rfid_history()

        # ── SCAN NOW button ──
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
            self._rfid_uid_label.text = "No driver"
            self._rfid_info_label.text = "RFID driver not available"
            return
        try:
            tags = driver.poll_tags()
            if tags:
                for tag in tags:
                    uid = tag.tag_id if hasattr(tag, "tag_id") else str(tag)
                    self._rfid_uid_label.text = uid
                    product = getattr(tag, "product_data", None) or ""
                    signal = getattr(tag, "signal_strength", 0)
                    reader = getattr(tag, "reader_id", "?")
                    ppg = getattr(tag, "ppg_code", None) or ""
                    prod_name = getattr(tag, "product_name", None) or ""
                    color_val = getattr(tag, "color", None) or ""

                    info_parts = []
                    if signal:
                        info_parts.append(f"Signal: {signal}")
                    if reader:
                        info_parts.append(f"Reader: {reader}")
                    if prod_name:
                        info_parts.append(f"Product: {prod_name}")
                    elif product:
                        info_parts.append(f"Data: {product[:30]}")
                    if ppg:
                        info_parts.append(f"PPG: {ppg}")
                    if color_val:
                        info_parts.append(f"Color: {color_val}")
                    self._rfid_info_label.text = "  |  ".join(info_parts) if info_parts else "No extra data"

                    # History
                    ts = time.strftime("%H:%M:%S")
                    entry_text = f"{ts}  {uid}"
                    if prod_name:
                        entry_text += f"  ({prod_name})"
                    self._rfid_history.insert(0, entry_text)
                    self._rfid_history = self._rfid_history[:10]
                    self._render_rfid_history()
            else:
                self._rfid_uid_label.text = "No tag found"
                self._rfid_info_label.text = "Hold a tag near the reader"
        except Exception as e:
            self._rfid_uid_label.text = "Error"
            self._rfid_info_label.text = str(e)[:80]
            logger.warning(f"RFID scan error: {e}")

    def _render_rfid_history(self):
        """Re-render the RFID history list."""
        if not self._rfid_history_box:
            return
        self._rfid_history_box.clear_widgets()
        for entry in self._rfid_history:
            lbl = Label(
                text=entry, font_size=DS.FONT_SMALL,
                color=DS.TEXT_SECONDARY, size_hint_y=None, height=dp(20),
                halign="left", valign="middle",
            )
            lbl.bind(size=lbl.setter("text_size"))
            self._rfid_history_box.add_widget(lbl)

    # ════════════════════════════════════════════════════════
    # WEIGHT TAB
    # ════════════════════════════════════════════════════════

    def _build_weight_tab(self):
        self._build_status_header("weight")

        # ── Live weight hero display ──
        weight_card = _card()
        weight_card.size_hint_y = None
        weight_card.height = dp(140)

        w_header = Label(
            text="Live Weight", font_size=DS.FONT_H3, bold=True,
            color=DS.TEXT_PRIMARY, size_hint_y=None, height=dp(22),
            halign="left",
        )
        w_header.bind(size=w_header.setter("text_size"))
        weight_card.add_widget(w_header)

        # Hero number
        self._weight_value_label = Label(
            text="0.0 g", font_size=DS.FONT_HERO, bold=True,
            color=DS.PRIMARY, halign="center", valign="middle",
        )
        weight_card.add_widget(self._weight_value_label)

        # Kg conversion
        self._weight_kg_label = Label(
            text="0.000 kg", font_size=DS.FONT_BODY,
            color=DS.TEXT_MUTED, halign="center", valign="top",
            size_hint_y=None, height=dp(18),
        )
        weight_card.add_widget(self._weight_kg_label)

        # Stability + raw value row
        info_row = BoxLayout(size_hint_y=None, height=dp(22), spacing=dp(16))
        self._weight_stable_label = Label(
            text="", font_size=DS.FONT_SMALL,
            color=DS.TEXT_SECONDARY, halign="left", markup=True,
        )
        self._weight_stable_label.bind(
            size=self._weight_stable_label.setter("text_size"))
        self._weight_raw_label = Label(
            text="Raw: --", font_size=DS.FONT_TINY,
            color=DS.TEXT_MUTED, halign="right", markup=True,
        )
        self._weight_raw_label.bind(
            size=self._weight_raw_label.setter("text_size"))
        info_row.add_widget(self._weight_stable_label)
        info_row.add_widget(self._weight_raw_label)
        weight_card.add_widget(info_row)

        self._content_area.add_widget(weight_card)

        # ── Weight graph ──
        graph_card = _card()
        graph_card.size_hint_y = None
        graph_card.height = dp(80)
        g_header = Label(
            text="History (last 50)", font_size=DS.FONT_TINY,
            color=DS.TEXT_MUTED, halign="left", valign="middle",
            size_hint_y=None, height=dp(14),
        )
        g_header.bind(size=g_header.setter("text_size"))
        graph_card.add_widget(g_header)
        self._weight_graph_widget = Widget()
        graph_card.add_widget(self._weight_graph_widget)
        self._content_area.add_widget(graph_card)

        # ── Action buttons ──
        btn_row = BoxLayout(
            size_hint_y=None, height=dp(DS.BTN_HEIGHT_LG), spacing=dp(8))

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

    def _poll_weight(self, dt):
        """Called every 300ms to update weight display when weight tab is active."""
        if self._active_tab != "weight":
            return
        if not self._weight_value_label:
            return
        driver = self._get_driver("weight")
        if not driver:
            return
        try:
            channels = driver.get_channels()
            if not channels:
                return
            reading = driver.read_weight(channels[0])
            if not reading:
                return

            grams = reading.grams if hasattr(reading, "grams") else 0.0
            stable = reading.stable if hasattr(reading, "stable") else False
            raw = reading.raw_value if hasattr(reading, "raw_value") else 0

            # Hero display: grams
            self._weight_value_label.text = f"{grams:.1f} g"

            # Kg conversion
            if self._weight_kg_label:
                self._weight_kg_label.text = f"{grams / 1000:.3f} kg"

            # Stability indicator
            if self._weight_stable_label:
                if stable:
                    self._weight_stable_label.text = (
                        "[color=33d17a]\u25cf STABLE[/color]"
                    )
                else:
                    self._weight_stable_label.text = (
                        "[color=fac222]\u25cf SETTLING...[/color]"
                    )

            # Raw ADC
            if self._weight_raw_label:
                self._weight_raw_label.text = f"Raw ADC: {raw}"

            # Graph data
            self._weight_readings.append(grams)
            if len(self._weight_readings) > 50:
                self._weight_readings = self._weight_readings[-50:]
            self._draw_weight_graph()

        except Exception as e:
            logger.debug(f"Weight poll error: {e}")

    def _draw_weight_graph(self):
        """Draw a simple line graph of the last 50 weight readings."""
        w = self._weight_graph_widget
        if not w:
            return
        w.canvas.after.clear()
        pts = self._weight_readings
        if len(pts) < 2:
            return

        min_v = min(pts) - 10
        max_v = max(pts) + 10
        rng = max_v - min_v if max_v != min_v else 1.0

        with w.canvas.after:
            # Horizontal grid lines
            Color(*DS.DIVIDER)
            for i in range(5):
                y = w.y + (w.height * i / 4)
                Line(points=[w.x, y, w.x + w.width, y], width=0.5)

            # Data line
            Color(*DS.PRIMARY)
            points = []
            for i, v in enumerate(pts):
                x = w.x + (w.width * i / (len(pts) - 1))
                y = w.y + (w.height * (v - min_v) / rng)
                points.extend([x, y])
            if len(points) >= 4:
                Line(points=points, width=1.5)

            # Current value marker
            if len(points) >= 2:
                Color(*DS.PRIMARY)
                Ellipse(
                    pos=(points[-2] - dp(3), points[-1] - dp(3)),
                    size=(dp(6), dp(6)),
                )

    def _weight_tare(self):
        """Zero all weight channels."""
        driver = self._get_driver("weight")
        if not driver:
            return
        try:
            channels = driver.get_channels()
            for ch in channels:
                driver.tare(ch)
            if self._weight_value_label:
                self._weight_value_label.text = "0.0 g"
                self._weight_value_label.color = DS.SUCCESS
                Clock.schedule_once(
                    lambda dt: setattr(
                        self._weight_value_label, "color", DS.PRIMARY),
                    1.0,
                )
            if self._weight_kg_label:
                self._weight_kg_label.text = "0.000 kg"
            self._weight_readings.clear()
            logger.info("Weight tare completed")
        except Exception as e:
            logger.warning(f"Tare failed: {e}")

    def _weight_calibrate(self):
        """Open calibration wizard popup."""
        try:
            from ui.widgets.calibration_wizard import CalibrationWizard
            app = App.get_running_app()
            wizard = CalibrationWizard(
                weight_driver=getattr(app, "weight", None))
            wizard.open()
        except ImportError:
            logger.warning("CalibrationWizard not available")
        except Exception as e:
            logger.warning(f"Calibration wizard error: {e}")

    # ════════════════════════════════════════════════════════
    # LED TAB
    # ════════════════════════════════════════════════════════

    def _build_led_tab(self):
        self._build_status_header("led")

        from hal.interfaces import LEDColor, LEDPattern

        # ── Slot grid ──
        slot_card = _card()
        s_header = Label(
            text="Slot LEDs", font_size=DS.FONT_H3, bold=True,
            color=DS.TEXT_PRIMARY, size_hint_y=None, height=dp(24),
            halign="left",
        )
        s_header.bind(size=s_header.setter("text_size"))
        slot_card.add_widget(s_header)

        grid = GridLayout(
            cols=4, spacing=dp(8), size_hint_y=None, height=dp(80))
        app = App.get_running_app()
        slot_count = getattr(app, "slot_count", 4) if app else 4

        colors = [
            LEDColor.OFF, LEDColor.GREEN, LEDColor.RED,
            LEDColor.YELLOW, LEDColor.BLUE, LEDColor.WHITE,
        ]
        color_names = ["OFF", "GREEN", "RED", "YELLOW", "BLUE", "WHITE"]
        color_rgbas = [
            DS.SLOT_EMPTY, DS.SUCCESS, DS.DANGER,
            DS.WARNING, DS.SECONDARY, DS.TEXT_PRIMARY,
        ]

        self._led_slot_index = {}
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

        # ── Pattern selector ──
        pattern_card = _card(
            orientation="horizontal", spacing=dp(6),
            padding=[dp(8), dp(6)],
        )
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
            is_active = pattern == LEDPattern.SOLID
            btn = Button(
                text=name, font_size="13sp", bold=True,
                background_normal="",
                background_color=DS.PRIMARY if is_active else DS.BG_CARD_HOVER,
                color=DS.BG_DARK if is_active else DS.TEXT_SECONDARY,
            )
            btn.pattern = pattern
            btn.bind(on_release=lambda x: self._led_set_pattern(x))
            pattern_card.add_widget(btn)

        self._content_area.add_widget(pattern_card)

        # ── All off / All green buttons ──
        btn_row = BoxLayout(
            size_hint_y=None, height=dp(DS.BTN_HEIGHT_LG), spacing=dp(8))

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
        """Cycle through LED colors for a slot."""
        from hal.interfaces import LEDColor
        slot_id = btn.slot_id
        idx = (self._led_slot_index.get(slot_id, 0) + 1) % len(btn.color_list)
        self._led_slot_index[slot_id] = idx

        color = btn.color_list[idx]
        name = btn.color_names[idx]
        rgba = btn.color_rgbas[idx]

        slot_num = slot_id[-1]
        btn.text = f"S{slot_num}\n{name}"
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
        """Switch the active LED pattern and update button styles."""
        self._current_led_pattern = btn.pattern
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
        """Turn off all LEDs."""
        driver = self._get_driver("led")
        if driver:
            try:
                driver.clear_all()
                logger.info("All LEDs cleared")
            except Exception as e:
                logger.debug(f"LED clear_all error: {e}")

    def _led_all_on(self):
        """Set all slots to green with current pattern."""
        from hal.interfaces import LEDColor
        driver = self._get_driver("led")
        if not driver:
            return
        try:
            app = App.get_running_app()
            slot_count = getattr(app, "slot_count", 4) if app else 4
            for i in range(slot_count):
                driver.set_slot(
                    f"shelf1_slot{i + 1}",
                    LEDColor.GREEN,
                    self._current_led_pattern,
                )
            logger.info("All LEDs set to GREEN")
        except Exception as e:
            logger.debug(f"LED all_on error: {e}")

    # ════════════════════════════════════════════════════════
    # BUZZER TAB
    # ════════════════════════════════════════════════════════

    def _build_buzzer_tab(self):
        self._build_status_header("buzzer")

        from hal.interfaces import BuzzerPattern

        card = _card()
        b_header = Label(
            text="Play Sound Pattern", font_size=DS.FONT_H3, bold=True,
            color=DS.TEXT_PRIMARY, size_hint_y=None, height=dp(24),
            halign="left",
        )
        b_header.bind(size=b_header.setter("text_size"))
        card.add_widget(b_header)

        patterns = [
            ("CONFIRM", BuzzerPattern.CONFIRM,
             "Single beep (1000Hz)", DS.SUCCESS),
            ("WARNING", BuzzerPattern.WARNING,
             "Double beep (800Hz)", DS.WARNING),
            ("ERROR", BuzzerPattern.ERROR,
             "Long buzz (400Hz)", DS.DANGER),
            ("TARGET", BuzzerPattern.TARGET_REACHED,
             "Rising 3-tone", DS.PRIMARY),
            ("TICK", BuzzerPattern.TICK,
             "Short click (1500Hz)", DS.TEXT_SECONDARY),
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
                size_hint_y=None, height=dp(DS.BTN_HEIGHT_LG),
                markup=True, halign="center",
            )
            btn.pattern = pattern
            btn.bind(on_release=lambda x: self._buzzer_play(x.pattern))
            grid.add_widget(btn)

        # Pad odd count
        if len(patterns) % 2:
            grid.add_widget(Widget())

        card.add_widget(grid)
        self._content_area.add_widget(card)

        # ── Stop button ──
        stop_btn = Button(
            text="STOP", font_size="16sp", bold=True,
            size_hint_y=None, height=dp(DS.BTN_HEIGHT_LG),
            background_normal="", background_color=DS.DANGER,
            color=(1, 1, 1, 1),
        )
        stop_btn.bind(on_release=lambda x: self._buzzer_stop())
        self._content_area.add_widget(stop_btn)

    def _buzzer_play(self, pattern):
        """Play a buzzer pattern."""
        driver = self._get_driver("buzzer")
        if driver:
            try:
                driver.play(pattern)
                logger.info(f"Buzzer playing: {pattern}")
            except Exception as e:
                logger.debug(f"Buzzer play error: {e}")

    def _buzzer_stop(self):
        """Stop any active buzzer sound."""
        driver = self._get_driver("buzzer")
        if driver:
            try:
                driver.stop()
                logger.info("Buzzer stopped")
            except Exception as e:
                logger.debug(f"Buzzer stop error: {e}")

    # ════════════════════════════════════════════════════════
    # HELPERS
    # ════════════════════════════════════════════════════════

    def _get_driver(self, sensor_name):
        """Get the driver instance from the running app."""
        app = App.get_running_app()
        if not app:
            return None
        attr_map = {
            "rfid": "rfid",
            "weight": "weight",
            "led": "led",
            "buzzer": "buzzer",
        }
        attr = attr_map.get(sensor_name)
        if attr:
            return getattr(app, attr, None)
        return None

    def _go_back(self):
        """Navigate back to settings (or home)."""
        if self.manager:
            self.manager.current = "settings"
