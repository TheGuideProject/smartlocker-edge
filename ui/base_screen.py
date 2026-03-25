"""
BaseScreen — Common base class for all SmartLocker screens.

Provides:
- Automatic status bar construction (BACK, title, right info)
- Navigation stack (go_back pops history, not hardcoded to 'home')
- Clock management (auto-cancel on_leave to prevent memory leaks)
- Access to DisplayMode for responsive scaling
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.clock import Clock
from kivy.metrics import dp

from ui.app import DS
from ui.display_mode import DisplayMode


# Navigation history stack (shared across all screens)
_nav_stack = []


class BaseScreen(Screen):
    """
    Base class for SmartLocker screens.

    Subclass and override:
      - screen_title: str  — title shown in status bar
      - show_back: bool    — whether to show back button (default True)
      - build_content()    — create your screen content (called once)
      - refresh()          — update live data (called periodically if refresh_interval set)
      - refresh_interval   — seconds between refresh calls (0 = no auto-refresh)
    """

    screen_title = "Screen"
    show_back = True
    refresh_interval = 0  # seconds, 0 = disabled

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._clock_events = []
        self._content_built = False
        self._content_area = None
        self._dm = DisplayMode.instance()

    def on_enter(self, *args):
        """Called when screen becomes visible."""
        # Track navigation
        if _nav_stack and _nav_stack[-1] == self.name:
            pass  # Don't double-push
        else:
            _nav_stack.append(self.name)

        # Build content on first enter
        if not self._content_built:
            self._build_screen()
            self._content_built = True

        # Start auto-refresh if configured
        if self.refresh_interval > 0:
            ev = Clock.schedule_interval(self._do_refresh, self.refresh_interval)
            self._clock_events.append(ev)

        self.on_screen_enter()

    def on_leave(self, *args):
        """Called when screen is no longer visible. Cancel all clocks."""
        for ev in self._clock_events:
            ev.cancel()
        self._clock_events.clear()
        self.on_screen_leave()

    # ── Override points ───────────────────────────────────

    def build_content(self, content_area: BoxLayout):
        """Override: add your widgets to content_area."""
        pass

    def refresh(self):
        """Override: update live data. Called every refresh_interval seconds."""
        pass

    def on_screen_enter(self):
        """Override: called after on_enter (content already built)."""
        pass

    def on_screen_leave(self):
        """Override: called after on_leave (clocks already cancelled)."""
        pass

    # ── Navigation ────────────────────────────────────────

    def go_back(self):
        """Navigate to previous screen in history."""
        app = self.manager
        if not app:
            return

        # Pop current screen from stack
        if _nav_stack and _nav_stack[-1] == self.name:
            _nav_stack.pop()

        # Go to previous screen or home
        if _nav_stack:
            target = _nav_stack[-1]
        else:
            target = "home"

        app.current = target

    def go_screen(self, name: str):
        """Navigate to a named screen."""
        if self.manager:
            self.manager.current = name

    def schedule_clock(self, callback, interval):
        """Schedule a clock that auto-cancels on_leave."""
        ev = Clock.schedule_interval(callback, interval)
        self._clock_events.append(ev)
        return ev

    # ── Internal ──────────────────────────────────────────

    def _build_screen(self):
        """Build the full screen layout with status bar + content area."""
        root = BoxLayout(orientation="vertical")

        # Status bar
        status_bar = self._build_status_bar()
        root.add_widget(status_bar)

        # Content area
        self._content_area = BoxLayout(
            orientation="vertical",
            padding=[dp(DS.PAD_SCREEN)] * 4,
            spacing=dp(DS.SPACING),
        )
        with self._content_area.canvas.before:
            Color(*DS.BG_DARK)
            self._bg_rect = Rectangle(pos=self._content_area.pos, size=self._content_area.size)
        self._content_area.bind(pos=self._update_bg, size=self._update_bg)

        self.build_content(self._content_area)
        root.add_widget(self._content_area)

        self.add_widget(root)

    def _build_status_bar(self):
        """Create the top status bar with back button and title."""
        bar = BoxLayout(
            size_hint_y=None,
            height=dp(DS.STATUS_BAR_H),
            padding=[dp(12), dp(4)],
            spacing=dp(8),
        )
        with bar.canvas.before:
            Color(*DS.BG_STATUS_BAR)
            self._bar_rect = Rectangle(pos=bar.pos, size=bar.size)
            # Bottom accent line
            Color(*DS.PRIMARY, 0.25)
            self._bar_line = Rectangle(pos=bar.pos, size=(bar.width, 1))
        bar.bind(pos=self._update_bar, size=self._update_bar)

        # Back button
        if self.show_back:
            back_btn = Button(
                text="<",
                font_size="22sp",
                bold=True,
                size_hint=(None, 1),
                width=dp(50),
                background_normal="",
                background_color=DS.BG_CARD_HOVER,
                color=DS.TEXT_SECONDARY,
            )
            back_btn.bind(on_release=lambda x: self.go_back())
            bar.add_widget(back_btn)

        # Title
        title_lbl = Label(
            text=self.screen_title,
            font_size=DS.FONT_H2,
            bold=True,
            color=DS.TEXT_PRIMARY,
            halign="center",
            valign="middle",
            markup=True,
        )
        title_lbl.bind(size=title_lbl.setter("text_size"))
        bar.add_widget(title_lbl)

        # Right spacer (balance the back button)
        if self.show_back:
            bar.add_widget(BoxLayout(size_hint=(None, 1), width=dp(50)))

        return bar

    def _do_refresh(self, dt):
        self.refresh()

    def _update_bg(self, *args):
        self._bg_rect.pos = self._content_area.pos
        self._bg_rect.size = self._content_area.size

    def _update_bar(self, widget, *args):
        self._bar_rect.pos = widget.pos
        self._bar_rect.size = widget.size
        self._bar_line.pos = widget.pos
        self._bar_line.size = (widget.width, 1)
