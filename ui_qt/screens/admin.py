"""
Admin Screen — Sensor driver toggles and system configuration.

No password required during development.
"""
import json
import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox, QGroupBox, QGridLayout, QMessageBox,
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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        btn_back = QPushButton("< Back")
        btn_back.setFixedSize(100, 40)
        btn_back.clicked.connect(self.app.go_back)
        header.addWidget(btn_back)

        title = QLabel("ADMIN SETTINGS")
        title.setFont(QFont("Sans", 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(title, 1)

        # Spacer to balance back button
        header.addSpacing(100)
        layout.addLayout(header)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # ── SENSOR DRIVERS ──
        group = QGroupBox("Sensor Drivers")
        group.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        grid = QGridLayout()
        grid.setSpacing(10)

        drivers = [
            ("rfid", "RFID Reader", "PN532 NFC tag reader"),
            ("weight", "Weight Sensors", "HX711 load cells (Arduino bridge)"),
            ("led", "LED Indicators", "Bar graph + shelf LEDs (Arduino)"),
            ("buzzer", "Buzzer", "GPIO PWM audio feedback"),
        ]

        for row, (key, label_text, desc) in enumerate(drivers):
            label = QLabel(f"{label_text}")
            label.setFont(QFont("Sans", 13, QFont.Weight.Bold))
            grid.addWidget(label, row * 2, 0)

            desc_label = QLabel(desc)
            desc_label.setFont(QFont("Sans", 10))
            desc_label.setStyleSheet(f"color: {C.TEXT_MUTED};")
            grid.addWidget(desc_label, row * 2 + 1, 0)

            combo = QComboBox()
            combo.addItems(["real", "fake"])
            combo.setFixedSize(120, 36)
            combo.setFont(QFont("Sans", 12))
            self._combos[key] = combo
            grid.addWidget(combo, row * 2, 1, 2, 1, Qt.AlignmentFlag.AlignRight)

        group.setLayout(grid)
        layout.addWidget(group)

        # ── WEIGHT MODE ──
        weight_group = QGroupBox("Weight Mode")
        weight_group.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        wl = QHBoxLayout()

        wl.addWidget(QLabel("Mode:"))
        self._weight_mode_combo = QComboBox()
        self._weight_mode_combo.addItems(["arduino_serial", "hx711_direct"])
        self._weight_mode_combo.setFixedSize(180, 36)
        self._weight_mode_combo.setFont(QFont("Sans", 12))
        wl.addWidget(self._weight_mode_combo)
        wl.addStretch()

        weight_group.setLayout(wl)
        layout.addWidget(weight_group)

        # ── SAVE / RESET ──
        btn_row = QHBoxLayout()

        btn_save = QPushButton("SAVE & RESTART APP")
        btn_save.setFixedHeight(50)
        btn_save.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {C.ACCENT};
                color: white;
                border-radius: 8px;
            }}
            QPushButton:pressed {{
                background-color: {C.PRIMARY_DIM};
            }}
        """)
        btn_save.clicked.connect(self._save_settings)
        btn_row.addWidget(btn_save, 2)

        btn_reset = QPushButton("RESET TO DEFAULTS")
        btn_reset.setFixedHeight(50)
        btn_reset.setFont(QFont("Sans", 12))
        btn_reset.setStyleSheet(f"""
            QPushButton {{
                background-color: {C.DANGER};
                color: white;
                border-radius: 8px;
            }}
        """)
        btn_reset.clicked.connect(self._reset_defaults)
        btn_row.addWidget(btn_reset, 1)

        layout.addLayout(btn_row)
        layout.addStretch()

        # ── CLOSE APP ──
        btn_close = QPushButton("CLOSE APP")
        btn_close.setFixedHeight(50)
        btn_close.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: #333;
                color: white;
                border: 2px solid {C.DANGER};
                border-radius: 8px;
            }}
            QPushButton:pressed {{
                background-color: {C.DANGER};
            }}
        """)
        btn_close.clicked.connect(self._close_app)
        layout.addWidget(btn_close)

        # ── INFO ──
        info = QLabel("Changes require app restart to take effect.")
        info.setFont(QFont("Sans", 10))
        info.setStyleSheet(f"color: {C.TEXT_MUTED};")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)

    def on_enter(self):
        """Load current driver settings."""
        # Load from admin DB overrides first, then fall back to settings.py
        admin_cfg = self.app.db.get_admin_config()

        from config import settings
        current = {
            "rfid": admin_cfg.get("driver_rfid", settings.DRIVER_RFID),
            "weight": admin_cfg.get("driver_weight", settings.DRIVER_WEIGHT),
            "led": admin_cfg.get("driver_led", settings.DRIVER_LED),
            "buzzer": admin_cfg.get("driver_buzzer", settings.DRIVER_BUZZER),
        }

        for key, combo in self._combos.items():
            val = current.get(key, "fake")
            idx = combo.findText(val)
            if idx >= 0:
                combo.setCurrentIndex(idx)

        weight_mode = admin_cfg.get("weight_mode", settings.WEIGHT_MODE)
        idx = self._weight_mode_combo.findText(weight_mode)
        if idx >= 0:
            self._weight_mode_combo.setCurrentIndex(idx)

    def _save_settings(self):
        """Save driver selections to DB and suggest restart."""
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

        QMessageBox.information(
            self, "Settings Saved",
            "Driver settings saved.\n\nRestart the app for changes to take effect.",
        )

    def _reset_defaults(self):
        """Remove admin overrides — use settings.py defaults."""
        self.app.db.conn.execute(
            "DELETE FROM config WHERE key = 'admin_settings'"
        )
        self.app.db.conn.commit()

        logger.info("Admin settings reset to defaults")

        QMessageBox.information(
            self, "Reset",
            "Admin overrides removed.\nApp will use settings.py defaults on next restart.",
        )

        # Refresh UI
        self.on_enter()

    def _close_app(self):
        """Close the application."""
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().quit()
