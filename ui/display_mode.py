"""
DisplayMode — Singleton that manages display modes (touch43 / desktop).

Provides scaling factor and window dimensions for responsive layout.
Persists mode selection to data/display_mode.json.
Auto-reverts to previous mode if not confirmed within 15 seconds.
"""

import os
import json
import logging

from kivy.event import EventDispatcher
from kivy.properties import StringProperty, NumericProperty, BooleanProperty
from kivy.core.window import Window
from kivy.clock import Clock

logger = logging.getLogger("smartlocker.display_mode")

# Display mode presets
MODES = {
    "touch43": {"width": 800, "height": 480, "scale": 1.0, "label": "Touch 4.3\""},
    "desktop": {"width": 1280, "height": 800, "scale": 1.5, "label": "Desktop"},
}

PERSIST_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "display_mode.json",
)

# Auto-revert timeout (seconds)
CONFIRM_TIMEOUT_S = 15


class DisplayMode(EventDispatcher):
    """Manages display mode switching with auto-revert confirmation."""

    mode = StringProperty("touch43")
    scale = NumericProperty(1.0)
    pending_confirm = BooleanProperty(False)

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, **kwargs):
        if hasattr(self, "_initialized"):
            return
        super().__init__(**kwargs)
        self._initialized = True
        self._revert_event = None
        self._previous_mode = "touch43"
        self._load()

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Public API ────────────────────────────────────────

    def switch_mode(self, new_mode: str):
        """Switch display mode. Starts auto-revert timer (15s)."""
        if new_mode not in MODES:
            logger.warning(f"Unknown display mode: {new_mode}")
            return
        if new_mode == self.mode:
            return

        self._previous_mode = self.mode
        self._apply_mode(new_mode)
        self.pending_confirm = True

        # Start auto-revert timer
        if self._revert_event:
            self._revert_event.cancel()
        self._revert_event = Clock.schedule_once(self._auto_revert, CONFIRM_TIMEOUT_S)
        logger.info(f"Display mode → {new_mode} (confirm within {CONFIRM_TIMEOUT_S}s)")

    def confirm(self):
        """User confirmed the mode switch. Cancel auto-revert."""
        if self._revert_event:
            self._revert_event.cancel()
            self._revert_event = None
        self.pending_confirm = False
        self._save()
        logger.info(f"Display mode confirmed: {self.mode}")

    def cancel(self):
        """User cancelled. Revert immediately."""
        if self._revert_event:
            self._revert_event.cancel()
            self._revert_event = None
        self.pending_confirm = False
        self._apply_mode(self._previous_mode)
        logger.info(f"Display mode reverted to: {self.mode}")

    def get_preset(self) -> dict:
        """Return current mode preset dict."""
        return MODES.get(self.mode, MODES["touch43"])

    def scaled(self, dp_value):
        """Scale a dp value by current display mode factor."""
        return dp_value * self.scale

    @property
    def is_touch(self) -> bool:
        return self.mode == "touch43"

    @property
    def is_desktop(self) -> bool:
        return self.mode == "desktop"

    # ── Internal ──────────────────────────────────────────

    def _apply_mode(self, mode_name: str):
        preset = MODES[mode_name]
        self.mode = mode_name
        self.scale = preset["scale"]
        Window.size = (preset["width"], preset["height"])

    def _auto_revert(self, dt):
        """Called when confirmation timer expires."""
        logger.info("Display mode confirmation timeout — reverting")
        self.pending_confirm = False
        self._apply_mode(self._previous_mode)

    def _save(self):
        try:
            os.makedirs(os.path.dirname(PERSIST_PATH), exist_ok=True)
            with open(PERSIST_PATH, "w") as f:
                json.dump({"mode": self.mode}, f)
        except Exception as e:
            logger.warning(f"Failed to save display mode: {e}")

    def _load(self):
        try:
            if os.path.exists(PERSIST_PATH):
                with open(PERSIST_PATH) as f:
                    data = json.load(f)
                    saved = data.get("mode", "touch43")
                    if saved in MODES:
                        self.mode = saved
                        self.scale = MODES[saved]["scale"]
        except Exception as e:
            logger.warning(f"Failed to load display mode: {e}")
