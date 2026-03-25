"""
CalibrationWizard — Modal popup for HX711 weight sensor calibration.

4 steps:
1. Remove all weight → set zero (tare offset)
2. Enter known weight (grams)
3. Place known weight → read loaded value
4. Show results → save or cancel
"""

import logging
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.app import App

from ui.app import DS

logger = logging.getLogger("smartlocker.calibration")


class CalibrationWizard(Popup):
    """Weight sensor calibration wizard."""

    def __init__(self, weight_driver=None, **kwargs):
        super().__init__(
            title="Weight Calibration",
            size_hint=(0.9, 0.85),
            auto_dismiss=False,
            **kwargs,
        )
        self._driver = weight_driver
        self._step = 1
        self._offset = 0
        self._known_g = 1000
        self._loaded_raw = 0
        self._scale_factor = 0
        self._clock_ev = None
        self._channel = None

        # Detect channel
        if self._driver:
            try:
                channels = self._driver.get_channels()
                self._channel = channels[0] if channels else "shelf1"
            except Exception:
                self._channel = "shelf1"

        self._build_step(1)

    def on_open(self):
        self._start_live_reading()

    def on_dismiss(self):
        self._stop_live_reading()

    # ═══════════════════════════════════════════════════════
    # STEP BUILDERS
    # ═══════════════════════════════════════════════════════

    def _build_step(self, step):
        self._step = step
        self.content = None
        if step == 1:
            self._build_step1()
        elif step == 2:
            self._build_step2()
        elif step == 3:
            self._build_step3()
        elif step == 4:
            self._build_step4()

    def _build_step1(self):
        """Step 1: Remove all weight and set zero."""
        self.title = "Calibration — Step 1/4: Set Zero"
        box = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(12))

        box.add_widget(Label(
            text="Remove ALL weight from the scale.\nWait until the reading stabilizes.",
            font_size="16sp", color=DS.TEXT_PRIMARY,
            halign="center", valign="middle",
            size_hint_y=0.3,
        ))

        # Live reading
        self._live_label = Label(
            text="Reading...", font_size=DS.FONT_HERO, bold=True,
            color=DS.PRIMARY, halign="center", valign="middle",
            size_hint_y=0.3,
        )
        box.add_widget(self._live_label)

        self._raw_label = Label(
            text="Raw: --", font_size=DS.FONT_SMALL,
            color=DS.TEXT_MUTED, halign="center",
            size_hint_y=0.1,
        )
        box.add_widget(self._raw_label)

        # Buttons
        btn_row = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(8))
        cancel_btn = Button(
            text="CANCEL", font_size="16sp", bold=True,
            background_normal="", background_color=DS.DANGER,
            color=(1, 1, 1, 1),
        )
        cancel_btn.bind(on_release=lambda x: self.dismiss())
        btn_row.add_widget(cancel_btn)

        self._zero_btn = Button(
            text="SET ZERO", font_size="16sp", bold=True,
            background_normal="", background_color=DS.PRIMARY,
            color=DS.BG_DARK,
        )
        self._zero_btn.bind(on_release=lambda x: self._set_zero())
        btn_row.add_widget(self._zero_btn)

        box.add_widget(btn_row)
        self.content = box

    def _build_step2(self):
        """Step 2: Enter known weight."""
        self.title = "Calibration — Step 2/4: Known Weight"
        box = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(12))

        box.add_widget(Label(
            text="Enter the weight of your test object (grams):",
            font_size="16sp", color=DS.TEXT_PRIMARY,
            halign="center", size_hint_y=0.2,
        ))

        # Text input
        self._weight_input = TextInput(
            text="1000",
            font_size="28sp",
            halign="center",
            input_filter="float",
            multiline=False,
            size_hint_y=None,
            height=dp(60),
            background_color=DS.BG_INPUT,
            foreground_color=DS.TEXT_PRIMARY,
            cursor_color=DS.PRIMARY,
        )
        box.add_widget(self._weight_input)

        # Quick presets
        preset_row = GridLayout(cols=4, spacing=dp(8), size_hint_y=None, height=dp(54))
        for grams in [500, 1000, 2000, 5000]:
            btn = Button(
                text=f"{grams}g", font_size="15sp", bold=True,
                background_normal="",
                background_color=DS.BG_CARD_HOVER,
                color=DS.TEXT_SECONDARY,
            )
            btn.grams = grams
            btn.bind(on_release=lambda x: setattr(self._weight_input, "text", str(x.grams)))
            preset_row.add_widget(btn)
        box.add_widget(preset_row)

        box.add_widget(Widget(size_hint_y=0.2))  # spacer

        # Buttons
        btn_row = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(8))
        back_btn = Button(
            text="BACK", font_size="16sp", bold=True,
            background_normal="", background_color=DS.BG_CARD_HOVER,
            color=DS.TEXT_SECONDARY,
        )
        back_btn.bind(on_release=lambda x: self._build_step(1))
        btn_row.add_widget(back_btn)

        next_btn = Button(
            text="NEXT", font_size="16sp", bold=True,
            background_normal="", background_color=DS.PRIMARY,
            color=DS.BG_DARK,
        )
        next_btn.bind(on_release=lambda x: self._go_step3())
        btn_row.add_widget(next_btn)

        box.add_widget(btn_row)
        self.content = box

    def _build_step3(self):
        """Step 3: Place known weight and read."""
        self.title = "Calibration — Step 3/4: Place Weight"
        box = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(12))

        box.add_widget(Label(
            text=f"Place {self._known_g}g on the scale.\nWait until stable, then press READ.",
            font_size="16sp", color=DS.TEXT_PRIMARY,
            halign="center", valign="middle",
            size_hint_y=0.3,
        ))

        self._live_label = Label(
            text="Reading...", font_size=DS.FONT_HERO, bold=True,
            color=DS.ACCENT, halign="center", valign="middle",
            size_hint_y=0.3,
        )
        box.add_widget(self._live_label)

        self._raw_label = Label(
            text="Raw: --", font_size=DS.FONT_SMALL,
            color=DS.TEXT_MUTED, halign="center",
            size_hint_y=0.1,
        )
        box.add_widget(self._raw_label)

        # Buttons
        btn_row = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(8))
        back_btn = Button(
            text="BACK", font_size="16sp", bold=True,
            background_normal="", background_color=DS.BG_CARD_HOVER,
            color=DS.TEXT_SECONDARY,
        )
        back_btn.bind(on_release=lambda x: self._build_step(2))
        btn_row.add_widget(back_btn)

        self._read_btn = Button(
            text="READ", font_size="16sp", bold=True,
            background_normal="", background_color=DS.ACCENT,
            color=DS.BG_DARK,
        )
        self._read_btn.bind(on_release=lambda x: self._read_loaded())
        btn_row.add_widget(self._read_btn)

        box.add_widget(btn_row)
        self.content = box
        self._start_live_reading()

    def _build_step4(self):
        """Step 4: Show results."""
        self.title = "Calibration — Step 4/4: Results"

        # Calculate
        diff = abs(self._offset - self._loaded_raw)
        if self._known_g > 0 and diff > 0:
            self._scale_factor = diff / self._known_g
        else:
            self._scale_factor = 1.0

        # Verify: calculate what the known weight reads as
        test_grams = diff / self._scale_factor if self._scale_factor else 0
        error_pct = abs(test_grams - self._known_g) / self._known_g * 100 if self._known_g else 0
        resolution = 1.0 / self._scale_factor if self._scale_factor else 999

        box = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12))

        # Results card
        results = [
            ("Zero Offset (raw)", f"{self._offset}"),
            ("Loaded Value (raw)", f"{self._loaded_raw}"),
            ("Scale Factor", f"{self._scale_factor:.4f} units/g"),
            ("Resolution", f"{resolution:.2f} g"),
            ("Verification", f"{test_grams:.1f}g (expected {self._known_g}g)"),
            ("Error", f"{error_pct:.2f}%"),
        ]

        for label, value in results:
            row = BoxLayout(size_hint_y=None, height=dp(30))
            row.add_widget(Label(
                text=label, font_size="14sp",
                color=DS.TEXT_SECONDARY, halign="left",
            ))
            color = DS.SUCCESS if error_pct < 2 else DS.WARNING if error_pct < 5 else DS.DANGER
            row.add_widget(Label(
                text=value, font_size="14sp", bold=True,
                color=color if "Error" in label or "Verification" in label else DS.TEXT_PRIMARY,
                halign="right",
            ))
            box.add_widget(row)

        box.add_widget(Widget(size_hint_y=0.1))

        # Inverted note
        inverted = self._loaded_raw < self._offset
        if inverted:
            box.add_widget(Label(
                text="[color=fac222]Note: Values decrease with weight (inverted)[/color]",
                font_size="12sp", markup=True, halign="center",
                size_hint_y=None, height=dp(20),
            ))

        # Buttons
        btn_row = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(8))
        cancel_btn = Button(
            text="DISCARD", font_size="16sp", bold=True,
            background_normal="", background_color=DS.DANGER,
            color=(1, 1, 1, 1),
        )
        cancel_btn.bind(on_release=lambda x: self.dismiss())
        btn_row.add_widget(cancel_btn)

        save_btn = Button(
            text="SAVE CALIBRATION", font_size="16sp", bold=True,
            background_normal="", background_color=DS.SUCCESS,
            color=DS.BG_DARK,
        )
        save_btn.bind(on_release=lambda x: self._save_calibration())
        btn_row.add_widget(save_btn)

        box.add_widget(btn_row)
        self.content = box

    # ═══════════════════════════════════════════════════════
    # ACTIONS
    # ═══════════════════════════════════════════════════════

    def _set_zero(self):
        """Read current value as zero offset."""
        raw = self._read_raw_averaged(10)
        if raw is not None:
            self._offset = raw
            logger.info(f"Calibration zero offset: {self._offset}")
            self._build_step(2)

    def _go_step3(self):
        try:
            self._known_g = float(self._weight_input.text)
            if self._known_g <= 0:
                return
        except ValueError:
            return
        self._build_step(3)

    def _read_loaded(self):
        """Read current value with known weight."""
        raw = self._read_raw_averaged(10)
        if raw is not None:
            self._loaded_raw = raw
            logger.info(f"Calibration loaded raw: {self._loaded_raw}")
            self._stop_live_reading()
            self._build_step(4)

    def _save_calibration(self):
        """Save calibration to driver and database."""
        app = App.get_running_app()

        # Save to HX711 driver if available
        if self._driver and hasattr(self._driver, "set_calibration"):
            inverted = self._loaded_raw < self._offset
            self._driver.set_calibration(
                self._channel, self._offset, self._scale_factor, inverted
            )

        # Persist to database
        if app and hasattr(app, "db"):
            try:
                app.db.save_admin_config("hx711_offset", str(self._offset))
                app.db.save_admin_config("hx711_scale_factor", str(self._scale_factor))
                app.db.save_admin_config("hx711_inverted", "1" if self._loaded_raw < self._offset else "0")
                logger.info(f"Calibration saved: offset={self._offset}, scale={self._scale_factor:.4f}")
            except Exception as e:
                logger.warning(f"Failed to save calibration to DB: {e}")

        self.dismiss()

    # ═══════════════════════════════════════════════════════
    # LIVE READING
    # ═══════════════════════════════════════════════════════

    def _start_live_reading(self):
        self._stop_live_reading()
        self._clock_ev = Clock.schedule_interval(self._update_live, 0.3)

    def _stop_live_reading(self):
        if self._clock_ev:
            self._clock_ev.cancel()
            self._clock_ev = None

    def _update_live(self, dt):
        """Update live reading display."""
        if not hasattr(self, "_live_label") or not self._live_label:
            return
        raw = self._read_raw_single()
        if raw is not None:
            # If we have offset, show grams estimate
            if self._offset and self._step >= 3:
                diff = abs(self._offset - raw)
                est_g = diff / self._scale_factor if self._scale_factor > 0 else diff
                self._live_label.text = f"{est_g:.1f} g"
            else:
                self._live_label.text = f"{raw}"
            if hasattr(self, "_raw_label") and self._raw_label:
                self._raw_label.text = f"Raw: {raw}"

    def _read_raw_single(self):
        """Read a single raw value from the weight driver."""
        if not self._driver:
            return None
        try:
            reading = self._driver.read_weight(self._channel)
            if reading:
                return getattr(reading, "raw_value", None) or int(getattr(reading, "grams", 0))
        except Exception:
            pass
        return None

    def _read_raw_averaged(self, samples=10):
        """Read and average multiple raw values."""
        if not self._driver:
            return None
        readings = []
        for _ in range(samples):
            val = self._read_raw_single()
            if val is not None:
                readings.append(val)
        if readings:
            # Remove outliers (top/bottom 20%)
            readings.sort()
            trim = max(1, len(readings) // 5)
            trimmed = readings[trim:-trim] if len(readings) > 3 else readings
            return int(sum(trimmed) / len(trimmed))
        return None
