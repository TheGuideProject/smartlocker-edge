"""mixing screen — PySide6 placeholder (will be implemented)."""
from ui_qt.screens.placeholder import PlaceholderScreen

class_map = {
    "pairing": "PairingScreen",
    "inventory": "InventoryScreen",
    "mixing": "MixingScreen",
    "paint_now": "PaintNowScreen",
    "chart_viewer": "ChartViewerScreen",
    "admin": "AdminScreen",
    "system_health": "SystemHealthScreen",
    "shelf_map": "ShelfMapScreen",
    "alarm": "AlarmScreen",
    "demo": "DemoScreen",
}

_name = "mixing"
_cls_name = class_map.get(_name, "PlaceholderScreen")
globals()[_cls_name] = type(_cls_name, (PlaceholderScreen,), {
    "__init__": lambda self, app: PlaceholderScreen.__init__(self, app, _name.replace("_", " ").title()),
})
