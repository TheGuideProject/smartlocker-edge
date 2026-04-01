"""
Admin Screen — Sensor driver toggles and system configuration.
Compact layout for 800x480 touch display with scroll support.
"""
import json
import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox, QGroupBox, QGridLayout, QMessageBox,
    QScrollArea,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui_qt.theme import C, F, S

logger = logging.getLogger("smartlocker.admin")


class AdminScreen(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._combos = {}
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header (fixed, not scrollable)
        header = QHBoxLayout()
        header.setContentsMargins(15, 8, 15, 8)
        btn_back = QPushButton("< Back")
        btn_back.setFixedSize(90, 36)
        btn_back.clicked.connect(self.app.go_back)
        header.addWidget(btn_back)

        title = QLabel("ADMIN")
        title.setFont(QFont("Sans", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(title, 1)
        header.addSpacing(90)
        outer.addLayout(header)

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(15, 5, 15, 10)
        layout.setSpacing(6)

        # ── SENSOR DRIVERS (compact grid) ──
        lbl = QLabel("Sensor Drivers")
        lbl.setFont(QFont("Sans", 13, QFont.Weight.Bold))
        layout.addWidget(lbl)

        drivers = [
            ("rfid", "RFID Reader"),
            ("weight", "Weight (HX711)"),
            ("led", "LED Indicators"),
            ("buzzer", "Buzzer"),
        ]

        grid = QGridLayout()
        grid.setSpacing(4)
        for row, (key, label_text) in enumerate(drivers):
            label = QLabel(label_text)
            label.setFont(QFont("Sans", 12))
            grid.addWidget(label, row, 0)

            combo = QComboBox()
            combo.addItems(["real", "fake"])
            combo.setFixedSize(100, 32)
            self._combos[key] = combo
            grid.addWidget(combo, row, 1, Qt.AlignmentFlag.AlignRight)

        layout.addLayout(grid)

        # ── WEIGHT MODE ──
        wrow = QHBoxLayout()
        wrow.addWidget(QLabel("Weight Mode:"))
        self._weight_mode_combo = QComboBox()
        self._weight_mode_combo.addItems(["arduino_serial", "hx711_direct"])
        self._weight_mode_combo.setFixedSize(160, 32)
        wrow.addWidget(self._weight_mode_combo)
        wrow.addStretch()
        layout.addLayout(wrow)

        layout.addSpacing(8)

        # ── BUTTONS ──
        btn_save = QPushButton("SAVE & RESTART")
        btn_save.setFixedHeight(44)
        btn_save.setFont(QFont("Sans", 13, QFont.Weight.Bold))
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {C.ACCENT};
                color: white;
                border-radius: 6px;
            }}
        """)
        btn_save.clicked.connect(self._save_and_restart)
        layout.addWidget(btn_save)

        btn_reset = QPushButton("RESET TO DEFAULTS")
        btn_reset.setFixedHeight(40)
        btn_reset.setStyleSheet(f"""
            QPushButton {{
                background-color: {C.DANGER};
                color: white;
                border-radius: 6px;
            }}
        """)
        btn_reset.clicked.connect(self._reset_defaults)
        layout.addWidget(btn_reset)

        btn_close = QPushButton("CLOSE APP")
        btn_close.setFixedHeight(40)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: #333;
                color: white;
                border: 2px solid {C.DANGER};
                border-radius: 6px;
            }}
        """)
        btn_close.clicked.connect(self._close_app)
        layout.addWidget(btn_close)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def on_enter(self):
        admin_cfg = self.app.db.get_admin_config()
        from config import settings

        current = {
            "rfid": admin_cfg.get("driver_rfid", settings.DRIVER_RFID),
            "weight": admin_cfg.get("driver_weight", settings.DRIVER_WEIGHT),
            "led": admin_cfg.get("driver_led", settings.DRIVER_LED),
            "buzzer": admin_cfg.get("driver_buzzer", settings.DRIVER_BUZZER),
        }

        for key, combo in self._combos.items():
            idx = combo.findText(current.get(key, "fake"))
            if idx >= 0:
                combo.setCurrentIndex(idx)

        weight_mode = admin_cfg.get("weight_mode", settings.WEIGHT_MODE)
        idx = self._weight_mode_combo.findText(weight_mode)
        if idx >= 0:
            self._weight_mode_combo.setCurrentIndex(idx)

    def _save_and_restart(self):
        admin_cfg = self.app.db.get_admin_config()
        admin_cfg["driver_rfid"] = self._combos["rfid"].currentText()
        admin_cfg["driver_weight"] = self._combos["weight"].currentText()
        admin_cfg["driver_led"] = self._combos["led"].currentText()
        admin_cfg["driver_buzzer"] = self._combos["buzzer"].currentText()
        admin_cfg["weight_mode"] = self._weight_mode_combo.currentText()

        self.app.db.conn.execute(
            """INSERT OR REPLACE INTO config (key, value, updated_at)
               VALUES ('admin_settings', ?, datetime('now'))""",
            (json.dumps(admin_cfg),),
        )
        self.app.db.conn.commit()
        logger.info(f"Admin settings saved: {admin_cfg}")

        # Restart: launch new process then quit current
        import sys
        import os
        import subprocess
        python = sys.executable
        script = os.path.abspath(sys.argv[0])
        args = sys.argv[1:]
        subprocess.Popen([python, script] + args)

        from PyQt6.QtWidgets import QApplication
        QApplication.instance().quit()

    def _reset_defaults(self):
        self.app.db.conn.execute(
            "DELETE FROM config WHERE key = 'admin_settings'"
        )
        self.app.db.conn.commit()
        logger.info("Admin settings reset to defaults")
        self.on_enter()

    def _close_app(self):
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().quit()
