"""
Home Screen - Main Dashboard (2026 Redesign v2)

Layout (800x480):
+--------------------------------------------------+
| SMARTLOCKER    [mode badge]    [clock HH:MM]     |  44dp status bar
+--------------------------------------------------+
|                                                   |
|  +--PAINT NOW!--+  +--STATUS PANEL--+            |  Top section
|  | large teal   |  | Slots: 3/4    |            |
|  | gradient btn |  | Cloud: OK     |            |
|  | 140dp tall   |  | Sync: 2m ago  |            |
|  +--------------+  +---------------+            |
|                                                   |
|  +------+ +------+ +------+ +------+            |  Nav grid
|  |CHART | |INVEN | |SENSOR| |SETT  |            |  4 tiles, 100dp
|  +------+ +------+ +------+ +------+            |
|                                                   |
|  [alarm bar if active]  [mix bar if active]      |  Dynamic
+--------------------------------------------------+

Design: Modern dark theme, teal accents, 64dp touch targets for gloved hands.
"""

import time
import logging

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle, Rectangle, Line, Ellipse
from kivy.metrics import dp

from ui.app import DS

logger = logging.getLogger("smartlocker.home")


# ================================================================
# HELPERS
# ================================================================

def _card(orientation="vertical", padding=None, spacing=None,
          bg=None, radius=None):
    """Create a dark rounded-card container with canvas background."""
    bx = BoxLayout(
        orientation=orientation,
        padding=padding or [dp(DS.PAD_CARD)] * 4,
        spacing=spacing or dp(DS.SPACING),
    )
    _bg_color = bg or DS.BG_CARD
    _radius = radius or dp(DS.RADIUS)
    with bx.canvas.before:
        Color(*_bg_color)
        bx._bg = RoundedRectangle(pos=bx.pos, size=bx.size,
                                   radius=[_radius])
    bx.bind(
        pos=lambda w, *a: setattr(w._bg, "pos", w.pos),
        size=lambda w, *a: setattr(w._bg, "size", w.size),
    )
    return bx


def _nav_tile(label_text, icon_text, accent_color, on_press):
    """Build a single navigation tile with icon, label, and top accent bar."""
    btn = Button(
        text="",
        background_normal="",
        background_color=(0, 0, 0, 0),
        size_hint=(1, 1),
    )
    # We build content via canvas + child labels
    outer = BoxLayout(orientation="vertical", spacing=dp(2))

    # Card background
    with outer.canvas.before:
        Color(*DS.BG_CARD)
        outer._bg = RoundedRectangle(pos=outer.pos, size=outer.size,
                                      radius=[dp(DS.RADIUS)])
        # Top accent line
        Color(*accent_color)
        outer._accent = RoundedRectangle(
            pos=(outer.x + dp(4), outer.y + outer.height - dp(4)),
            size=(outer.width - dp(8), dp(3)),
            radius=[dp(2)],
        )

    def _update_bg(w, *a):
        w._bg.pos = w.pos
        w._bg.size = w.size
        w._accent.pos = (w.x + dp(4), w.y + w.height - dp(4))
        w._accent.size = (w.width - dp(8), dp(3))

    outer.bind(pos=_update_bg, size=_update_bg)

    # Icon
    icon_lbl = Label(
        text=icon_text, font_size="28sp",
        color=accent_color, halign="center", valign="bottom",
        size_hint_y=0.55,
    )
    icon_lbl.bind(size=icon_lbl.setter("text_size"))
    outer.add_widget(icon_lbl)

    # Text
    text_lbl = Label(
        text=label_text, font_size=DS.FONT_SMALL, bold=True,
        color=DS.TEXT_PRIMARY, halign="center", valign="top",
        size_hint_y=0.45,
    )
    text_lbl.bind(size=text_lbl.setter("text_size"))
    outer.add_widget(text_lbl)

    # Wrap in a button-like touch area
    container = BoxLayout(size_hint=(1, 1))

    # Invisible overlay button for touch
    overlay = Button(
        text="", background_normal="", background_color=(0, 0, 0, 0),
        size_hint=(1, 1),
    )
    overlay.bind(on_release=on_press)

    from kivy.uix.relativelayout import RelativeLayout
    rel = RelativeLayout()
    rel.add_widget(outer)
    rel.add_widget(overlay)
    return rel


class HomeScreen(Screen):
    """Main dashboard screen with hero button, status panel, and nav tiles."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._clock_events = []
        self._built = False

        # Widget references
        self._clock_label = None
        self._mode_label = None
        self._slot_label = None
        self._cloud_label = None
        self._sync_label = None
        self._alarm_container = None
        self._mix_container = None
        self._alarm_indicator_bg = None
        self._alarm_indicator_label = None
        self._mix_indicator_bg = None
        self._mix_indicator_label = None

    # ────────────────────────────────────────────────────────
    # LIFECYCLE
    # ────────────────────────────────────────────────────────

    def on_enter(self, *args):
        if not self._built:
            self._build_ui()
            self._built = True
        self._update_mode_badge()
        self._tick(0)
        ev = Clock.schedule_interval(self._tick, 1.0)
        self._clock_events.append(ev)

    def on_leave(self, *args):
        for ev in self._clock_events:
            ev.cancel()
        self._clock_events.clear()

    # ────────────────────────────────────────────────────────
    # BUILD UI
    # ────────────────────────────────────────────────────────

    def _build_ui(self):
        root = BoxLayout(orientation="vertical")

        # Full-screen dark background
        with root.canvas.before:
            Color(*DS.BG_DARK)
            root._bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(
            pos=lambda w, *a: setattr(w._bg, "pos", w.pos),
            size=lambda w, *a: setattr(w._bg, "size", w.size),
        )

        # ── STATUS BAR (44dp) ──
        root.add_widget(self._build_status_bar())

        # ── MAIN CONTENT ──
        content = BoxLayout(
            orientation="vertical",
            padding=[dp(DS.PAD_SCREEN), dp(8), dp(DS.PAD_SCREEN), dp(6)],
            spacing=dp(DS.SPACING),
        )

        # Top section: hero button + status panel side by side
        top_row = BoxLayout(
            orientation="horizontal",
            spacing=dp(10),
            size_hint_y=None,
            height=dp(140),
        )
        top_row.add_widget(self._build_hero_button())
        top_row.add_widget(self._build_status_panel())
        content.add_widget(top_row)

        # Spacer
        content.add_widget(Widget(size_hint_y=None, height=dp(6)))

        # Nav tiles row (4 tiles)
        content.add_widget(self._build_nav_grid())

        # Flexible spacer
        content.add_widget(Widget(size_hint_y=1))

        # Dynamic alarm indicator
        self._alarm_container = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=0,
            padding=[0, 0],
            spacing=0,
        )
        content.add_widget(self._alarm_container)

        # Dynamic mix indicator
        self._mix_container = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=0,
            padding=[0, 0],
            spacing=0,
        )
        content.add_widget(self._mix_container)

        root.add_widget(content)
        self.add_widget(root)

    # ── STATUS BAR ──

    def _build_status_bar(self):
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

        # Brand
        brand = Label(
            text="SMARTLOCKER", font_size="18sp", bold=True,
            color=DS.TEXT_PRIMARY, size_hint_x=0.35,
            halign="left", valign="middle",
        )
        brand.bind(size=brand.setter("text_size"))
        bar.add_widget(brand)

        # Mode badge
        self._mode_label = Label(
            text="TEST MODE", font_size="13sp", bold=True,
            color=DS.PRIMARY, size_hint_x=0.35,
            halign="center", valign="middle", markup=True,
        )
        self._mode_label.bind(size=self._mode_label.setter("text_size"))
        bar.add_widget(self._mode_label)

        # Clock
        self._clock_label = Label(
            text="00:00", font_size="15sp", bold=True,
            color=DS.TEXT_SECONDARY, size_hint_x=0.30,
            halign="right", valign="middle",
        )
        self._clock_label.bind(size=self._clock_label.setter("text_size"))
        bar.add_widget(self._clock_label)

        return bar

    # ── HERO PAINT NOW BUTTON ──

    def _build_hero_button(self):
        hero = Button(
            text="", background_normal="", background_color=(0, 0, 0, 0),
            size_hint_x=0.55,
        )

        # Teal gradient
        with hero.canvas.before:
            Color(0.00, 0.72, 0.63, 1)
            hero._bg_main = RoundedRectangle(
                pos=hero.pos, size=hero.size, radius=[dp(16)],
            )
            # Lighter upper half for gradient effect
            Color(0.00, 0.92, 0.82, 0.35)
            hero._bg_glow = RoundedRectangle(
                pos=(hero.x + dp(2), hero.y + hero.height * 0.55),
                size=(hero.width - dp(4), hero.height * 0.44),
                radius=[dp(16), dp(16), 0, 0],
            )
            # Border glow
            Color(0.00, 0.92, 0.80, 0.3)
            hero._border = Line(
                rounded_rectangle=(hero.x, hero.y, hero.width,
                                   hero.height, dp(16)),
                width=1.2,
            )

        def _update_hero(w, *a):
            w._bg_main.pos = w.pos
            w._bg_main.size = w.size
            w._bg_glow.pos = (w.x + dp(2), w.y + w.height * 0.55)
            w._bg_glow.size = (w.width - dp(4), w.height * 0.44)
            w._border.rounded_rectangle = (w.x, w.y, w.width,
                                           w.height, dp(16))

        hero.bind(pos=_update_hero, size=_update_hero)

        # Overlay labels
        from kivy.uix.relativelayout import RelativeLayout
        rel = RelativeLayout(size_hint=(0.55, 1))

        hero_inner = BoxLayout(orientation="vertical",
                               padding=[dp(12), dp(16)], spacing=dp(4))

        title = Label(
            text="PAINT NOW!", font_size="32sp", bold=True,
            color=(0.02, 0.05, 0.08, 1),
            halign="center", valign="bottom", size_hint_y=0.6,
        )
        title.bind(size=title.setter("text_size"))
        hero_inner.add_widget(title)

        sub = Label(
            text="Select area & start mixing", font_size=DS.FONT_SMALL,
            color=(0.02, 0.05, 0.08, 0.7),
            halign="center", valign="top", size_hint_y=0.4,
        )
        sub.bind(size=sub.setter("text_size"))
        hero_inner.add_widget(sub)

        rel.add_widget(hero)
        rel.add_widget(hero_inner)

        # Touch handler on entire area
        touch_overlay = Button(
            text="", background_normal="", background_color=(0, 0, 0, 0),
        )
        touch_overlay.bind(on_release=lambda x: self._go_paint())
        rel.add_widget(touch_overlay)

        return rel

    # ── STATUS PANEL ──

    def _build_status_panel(self):
        panel = _card(
            orientation="vertical",
            padding=[dp(12), dp(10)],
            spacing=dp(8),
        )
        panel.size_hint_x = 0.45

        # Title
        header = Label(
            text="STATUS", font_size=DS.FONT_SMALL, bold=True,
            color=DS.TEXT_MUTED, halign="left", valign="middle",
            size_hint_y=None, height=dp(18),
        )
        header.bind(size=header.setter("text_size"))
        panel.add_widget(header)

        # Slot row
        slot_row = BoxLayout(size_hint_y=None, height=dp(22), spacing=dp(4))
        slot_dot = Widget(size_hint=(None, None), size=(dp(8), dp(8)))
        with slot_dot.canvas:
            Color(*DS.PRIMARY)
            slot_dot._el = Ellipse(pos=slot_dot.pos, size=slot_dot.size)
        slot_dot.bind(
            pos=lambda w, *a: setattr(w._el, "pos", w.pos),
            size=lambda w, *a: setattr(w._el, "size", w.size),
        )
        slot_row.add_widget(slot_dot)
        self._slot_label = Label(
            text="Slots: --/--", font_size=DS.FONT_BODY, bold=True,
            color=DS.TEXT_PRIMARY, halign="left", valign="middle",
        )
        self._slot_label.bind(size=self._slot_label.setter("text_size"))
        slot_row.add_widget(self._slot_label)
        panel.add_widget(slot_row)

        # Cloud row
        cloud_row = BoxLayout(size_hint_y=None, height=dp(22), spacing=dp(4))
        self._cloud_dot = Widget(size_hint=(None, None), size=(dp(8), dp(8)))
        with self._cloud_dot.canvas:
            Color(*DS.SUCCESS)
            self._cloud_dot._el = Ellipse(
                pos=self._cloud_dot.pos, size=self._cloud_dot.size)
        self._cloud_dot.bind(
            pos=lambda w, *a: setattr(w._el, "pos", w.pos),
            size=lambda w, *a: setattr(w._el, "size", w.size),
        )
        cloud_row.add_widget(self._cloud_dot)
        self._cloud_label = Label(
            text="Cloud: --", font_size=DS.FONT_BODY, bold=True,
            color=DS.TEXT_PRIMARY, halign="left", valign="middle",
        )
        self._cloud_label.bind(size=self._cloud_label.setter("text_size"))
        cloud_row.add_widget(self._cloud_label)
        panel.add_widget(cloud_row)

        # Sync row
        sync_row = BoxLayout(size_hint_y=None, height=dp(22), spacing=dp(4))
        sync_icon = Label(
            text="~", font_size="12sp", color=DS.TEXT_MUTED,
            size_hint=(None, None), size=(dp(8), dp(8)),
            halign="center", valign="middle",
        )
        sync_row.add_widget(sync_icon)
        self._sync_label = Label(
            text="Sync: --", font_size=DS.FONT_BODY,
            color=DS.TEXT_SECONDARY, halign="left", valign="middle",
        )
        self._sync_label.bind(size=self._sync_label.setter("text_size"))
        sync_row.add_widget(self._sync_label)
        panel.add_widget(sync_row)

        # Filler
        panel.add_widget(Widget(size_hint_y=1))

        return panel

    # ── NAV GRID ──

    def _build_nav_grid(self):
        grid = GridLayout(
            cols=4, spacing=dp(10),
            size_hint_y=None, height=dp(100),
        )

        app_ref = App.get_running_app

        tiles = [
            ("CHECK\nCHART", "C", DS.SECONDARY, "chart_viewer"),
            ("INVENTORY", "I", DS.SUCCESS, "inventory"),
            ("SENSORS", "S", DS.ACCENT, "sensor_test"),
            ("SETTINGS", "G", DS.TEXT_SECONDARY, "settings"),
        ]

        icon_map = {
            "CHECK\nCHART": "[C]",
            "INVENTORY": "[I]",
            "SENSORS": "[S]",
            "SETTINGS": "[G]",
        }

        for label_text, _short, accent, screen_name in tiles:
            icon = icon_map.get(label_text, _short)
            tile = _nav_tile(
                label_text=label_text,
                icon_text=icon,
                accent_color=accent,
                on_press=lambda x, s=screen_name: self._go_screen(s),
            )
            grid.add_widget(tile)

        return grid

    # ────────────────────────────────────────────────────────
    # PERIODIC TICK (every 1s)
    # ────────────────────────────────────────────────────────

    def _tick(self, dt):
        """Update clock, status, alarms, and mix indicators."""
        # Clock
        if self._clock_label:
            self._clock_label.text = time.strftime("%H:%M")

        app = App.get_running_app()
        if not app:
            return

        # Slot summary
        self._update_slot_status(app)
        # Cloud status
        self._update_cloud_status(app)
        # Sync status
        self._update_sync_status(app)
        # Alarm bar
        self._update_alarm_indicator(app)
        # Mix bar
        self._update_mix_indicator(app)

    def _update_mode_badge(self):
        """Set the mode label based on app config."""
        app = App.get_running_app()
        if not app or not self._mode_label:
            return
        mode_text = getattr(app, "mode", "TEST").upper()
        cloud_paired = False
        cloud = getattr(app, "cloud", None)
        if cloud:
            cloud_paired = getattr(cloud, "is_paired", False)

        if cloud_paired:
            self._mode_label.text = f"{mode_text} | CLOUD"
            self._mode_label.color = DS.SECONDARY
        else:
            self._mode_label.text = f"{mode_text} MODE"
            self._mode_label.color = DS.PRIMARY

    def _update_slot_status(self, app):
        """Update the slot occupancy label."""
        if not self._slot_label:
            return
        try:
            inventory = getattr(app, "inventory", None)
            if inventory:
                slots = inventory.get_all_slots()
                occupied = sum(
                    1 for s in slots
                    if hasattr(s, "status") and s.status.value == "occupied"
                )
                total = len(slots)
                self._slot_label.text = f"Slots: {occupied}/{total}"
            else:
                self._slot_label.text = "Slots: --"
        except Exception:
            self._slot_label.text = "Slots: err"

    def _update_cloud_status(self, app):
        """Update the cloud status label and dot color."""
        if not self._cloud_label:
            return
        cloud = getattr(app, "cloud", None)
        if cloud and getattr(cloud, "is_paired", False):
            self._cloud_label.text = "Cloud: OK"
            self._cloud_label.color = DS.TEXT_PRIMARY
            self._set_dot_color(self._cloud_dot, DS.SUCCESS)
        else:
            self._cloud_label.text = "Cloud: OFF"
            self._cloud_label.color = DS.TEXT_MUTED
            self._set_dot_color(self._cloud_dot, DS.TEXT_MUTED)

    def _update_sync_status(self, app):
        """Update the last sync timestamp."""
        if not self._sync_label:
            return
        sync_engine = getattr(app, "sync_engine", None)
        if sync_engine:
            last_sync = getattr(sync_engine, "last_sync_time", None)
            if last_sync:
                elapsed = time.time() - last_sync
                if elapsed < 60:
                    self._sync_label.text = "Sync: just now"
                elif elapsed < 3600:
                    mins = int(elapsed / 60)
                    self._sync_label.text = f"Sync: {mins}m ago"
                else:
                    hrs = int(elapsed / 3600)
                    self._sync_label.text = f"Sync: {hrs}h ago"
            else:
                self._sync_label.text = "Sync: pending"
        else:
            self._sync_label.text = "Sync: N/A"

    # ────────────────────────────────────────────────────────
    # ALARM INDICATOR BAR
    # ────────────────────────────────────────────────────────

    def _update_alarm_indicator(self, app):
        """Show/hide pulsing alarm bar when alarms are active."""
        container = self._alarm_container
        if not container:
            return

        alarm_mgr = getattr(app, "alarm_manager", None)
        alarm_count = 0
        has_critical = False
        if alarm_mgr:
            alarm_count = alarm_mgr.active_count() if hasattr(alarm_mgr, "active_count") else 0
            if alarm_count > 0:
                has_critical = alarm_mgr.has_critical() if hasattr(alarm_mgr, "has_critical") else False

        if alarm_count > 0:
            if has_critical:
                bg_color = (0.93, 0.27, 0.32, 0.25)
                text_color = DS.DANGER
                bar_text = "CRITICAL ALARM -- Tap to view"
            else:
                bg_color = (0.98, 0.76, 0.22, 0.20)
                text_color = DS.WARNING
                suf = "s" if alarm_count > 1 else ""
                bar_text = f"{alarm_count} warning{suf}"

            # Build bar if collapsed
            if container.height < dp(40):
                container.clear_widgets()
                container.height = dp(44)
                container.padding = [dp(8), dp(4)]
                container.spacing = dp(8)

                container.canvas.before.clear()
                with container.canvas.before:
                    Color(*bg_color)
                    self._alarm_indicator_bg = RoundedRectangle(
                        pos=container.pos, size=container.size,
                        radius=[dp(8)],
                    )
                container.bind(
                    pos=lambda w, *a: setattr(self._alarm_indicator_bg, "pos", w.pos),
                    size=lambda w, *a: setattr(self._alarm_indicator_bg, "size", w.size),
                )

                self._alarm_indicator_label = Label(
                    text="", font_size="14sp", bold=True,
                    color=text_color, size_hint_x=0.7,
                    halign="left", valign="middle", markup=True,
                )
                self._alarm_indicator_label.bind(
                    size=self._alarm_indicator_label.setter("text_size"),
                )
                container.add_widget(self._alarm_indicator_label)

                view_btn = Button(
                    text="VIEW", font_size="14sp", bold=True,
                    background_normal="", background_color=text_color,
                    color=(0.02, 0.05, 0.08, 1), size_hint_x=0.3,
                )
                view_btn.bind(
                    on_release=lambda x: self._go_screen("alarm"),
                )
                container.add_widget(view_btn)

            # Update text
            if self._alarm_indicator_label:
                self._alarm_indicator_label.text = bar_text
        else:
            # Hide
            if container.height > 0:
                container.clear_widgets()
                container.canvas.before.clear()
                container.height = 0
                container.padding = [0, 0]
                container.spacing = 0

    # ────────────────────────────────────────────────────────
    # MIX INDICATOR BAR
    # ────────────────────────────────────────────────────────

    def _update_mix_indicator(self, app):
        """Show/hide active mix progress bar."""
        container = self._mix_container
        if not container:
            return

        mixing = getattr(app, "mixing", None)
        is_active = mixing.is_active if mixing else False

        if is_active:
            session = getattr(mixing, "session", None)
            state_text = mixing.current_state.value.replace("_", " ").upper()

            # Get recipe name
            recipe_name = ""
            if session and hasattr(session, "recipe_id") and session.recipe_id:
                recipes = getattr(mixing, "_recipes", {})
                recipe = recipes.get(session.recipe_id)
                if recipe:
                    recipe_name = getattr(recipe, "name", "")
            display_name = recipe_name or "Active Session"

            # Build bar if collapsed
            if container.height < dp(40):
                container.clear_widgets()
                container.height = dp(48)
                container.padding = [dp(8), dp(4)]
                container.spacing = dp(8)

                container.canvas.before.clear()
                with container.canvas.before:
                    Color(0.00, 0.82, 0.73, 0.15)
                    self._mix_indicator_bg = RoundedRectangle(
                        pos=container.pos, size=container.size,
                        radius=[dp(8)],
                    )
                container.bind(
                    pos=lambda w, *a: setattr(self._mix_indicator_bg, "pos", w.pos),
                    size=lambda w, *a: setattr(self._mix_indicator_bg, "size", w.size),
                )

                self._mix_indicator_label = Label(
                    text="", font_size="13sp", bold=True,
                    color=DS.PRIMARY, size_hint_x=0.7,
                    halign="left", valign="middle", markup=True,
                )
                self._mix_indicator_label.bind(
                    size=self._mix_indicator_label.setter("text_size"),
                )
                container.add_widget(self._mix_indicator_label)

                resume_btn = Button(
                    text="RESUME", font_size="14sp", bold=True,
                    background_normal="",
                    background_color=DS.PRIMARY,
                    color=(0.02, 0.05, 0.08, 1),
                    size_hint_x=0.3,
                )
                resume_btn.bind(
                    on_release=lambda x: self._go_screen("mixing"),
                )
                container.add_widget(resume_btn)

            # Update text
            if self._mix_indicator_label:
                self._mix_indicator_label.text = (
                    f"MIX: [b]{display_name}[/b]  -  {state_text}"
                )
        else:
            # Hide
            if container.height > 0:
                container.clear_widgets()
                container.canvas.before.clear()
                container.height = 0
                container.padding = [0, 0]
                container.spacing = 0

    # ────────────────────────────────────────────────────────
    # HELPERS
    # ────────────────────────────────────────────────────────

    @staticmethod
    def _set_dot_color(dot_widget, color):
        """Re-draw a dot widget's ellipse with a new color."""
        if not dot_widget:
            return
        dot_widget.canvas.clear()
        with dot_widget.canvas:
            Color(*color)
            dot_widget._el = Ellipse(pos=dot_widget.pos,
                                     size=dot_widget.size)
        dot_widget.bind(
            pos=lambda w, *a: setattr(w._el, "pos", w.pos),
            size=lambda w, *a: setattr(w._el, "size", w.size),
        )

    def _go_paint(self):
        app = App.get_running_app()
        if app:
            app.go_screen("paint_now")

    def _go_screen(self, name):
        app = App.get_running_app()
        if app:
            app.go_screen(name)
