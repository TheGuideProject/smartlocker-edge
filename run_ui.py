"""
SmartLocker UI - Touchscreen Interface

Launch the Kivy-based touchscreen application.
Works on both desktop (for testing) and Raspberry Pi (with 4.3" DSI touchscreen).

Usage:
    pip install kivy          # Install Kivy first (one time)
    python run_ui.py          # Launch the UI

On Raspberry Pi:
    pip3 install kivy
    python3 run_ui.py
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Kivy configuration MUST be set before importing kivy
os.environ.setdefault('KIVY_NO_CONSOLELOG', '1')
os.environ.setdefault('KIVY_LOG_LEVEL', 'warning')

from kivy.config import Config

# Window size for 4.3" touchscreen (800x480)
Config.set('graphics', 'width', '800')
Config.set('graphics', 'height', '480')
Config.set('graphics', 'resizable', '1')
Config.set('graphics', 'minimum_width', '800')
Config.set('graphics', 'minimum_height', '480')

# Touch input: disable multitouch emulation (red dots on right-click)
Config.set('input', 'mouse', 'mouse,multitouch_on_demand')

# Disable Kivy settings panel (gesture from bottom)
Config.set('kivy', 'exit_on_escape', '1')

from ui.app import SmartLockerApp


if __name__ == '__main__':
    SmartLockerApp().run()
