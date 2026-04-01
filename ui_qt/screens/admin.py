"""
Admin Screen -- Sensor driver toggles and system configuration.
Compact layout for 800x480 touch display with scroll support.
"""
import json
import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox, QGridLayout, QMessageBox,
    QScrollArea, QSpinBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui_qt.theme import C, F, S, enable_touch_scroll
from ui_qt.icons import (
    Icon, icon_badge, icon_label, section_header, screen_header, type_badge,
)

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

        # ── Screen header (consistent) ──
        header, header_layout = screen_header(
            self.app, "ADMIN CONFIG", Icon.SETTINGS, C.ACCENT
        )
        outer.addWidget(header)

        # ── Scroll area for content ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
        layout.setSpacing(S.PAD)

        # ── SENSOR DRIVERS card ──
        layout.addWidget(self._build_drivers_card())

        # ── HARDWARE card ──
        layout.addWidget(self._build_hardware_card())

        # ── ACTION BUTTONS card ──
        layout.addWidget(self._build_actions_card())

        layout.addStretch()
        scroll.setWidget(content)
        enable_touch_scroll(scroll)
        outer.addWidget(scroll)

    # ──────────────────────────────────────────────────
    # SENSOR DRIVERS card
    # ──────────────────────────────────────────────────

    def _build_drivers_card(self) -> QFrame:
        card = self._make_card(C.SECONDARY)
        lay = QVBoxLayout(card)
        lay.setSpacing(S.GAP)

        lay.addWidget(
            section_header(Icon.SENSORS, "SENSOR DRIVERS", C.SECONDARY)
        )

        drivers = [
            ("rfid", "RFID Reader", Icon.TAG),
            ("weight", "Weight (HX711)", Icon.WEIGHT),
            ("led", "LED Indicators", Icon.DOT),
            ("buzzer", "Buzzer", Icon.ALARM),
        ]

        grid = QGridLayout()
        grid.setSpacing(S.GAP)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 0)

        for row, (key, label_text, glyph) in enumerate(drivers):
            # Icon
            icn = icon_label(glyph, color=C.SECONDARY, size=16)
            grid.addWidget(icn, row, 0)

            # Label
            label = QLabel(label_text)
            label.setStyleSheet(
                f"color: {C.TEXT}; font-size: {F.BODY}px;"
            )
            grid.addWidget(label, row, 1)

            # Dropdown (stretch to fill)
            combo = QComboBox()
            combo.addItems(["real", "fake"])
            combo.setMinimumHeight(36)
            combo.setStyleSheet(
                f"QComboBox {{"
                f"  background-color: {C.BG_INPUT};"
                f"  color: {C.TEXT};"
                f"  border: 1px solid {C.BORDER};"
                f"  border-radius: 6px;"
                f"  padding: 4px 12px;"
                f"  font-size: {F.BODY}px;"
                f"  min-width: 120px;"
                f"}}"
                f"QComboBox:focus {{"
                f"  border-color: {C.SECONDARY};"
                f"}}"
                f"QComboBox::drop-down {{"
                f"  border: none;"
                f"  width: 28px;"
                f"}}"
                f"QComboBox QAbstractItemView {{"
                f"  background-color: {C.BG_CARD};"
                f"  color: {C.TEXT};"
                f"  border: 1px solid {C.BORDER};"
                f"  selection-background-color: {C.PRIMARY_BG};"
                f"  selection-color: {C.PRIMARY};"
                f"}}"
            )
            self._combos[key] = combo
            grid.addWidget(combo, row, 2)

        lay.addLayout(grid)
        return card

    # ──────────────────────────────────────────────────
    # HARDWARE card
    # ──────────────────────────────────────────────────

    def _build_hardware_card(self) -> QFrame:
        card = self._make_card(C.ACCENT)
        lay = QVBoxLayout(card)
        lay.setSpacing(S.GAP)

        lay.addWidget(
            section_header(Icon.SETTINGS, "HARDWARE", C.ACCENT)
        )

        combo_style = (
            f"QComboBox {{"
            f"  background-color: {C.BG_INPUT};"
            f"  color: {C.TEXT};"
            f"  border: 1px solid {C.BORDER};"
            f"  border-radius: 6px;"
            f"  padding: 4px 12px;"
            f"  font-size: {F.BODY}px;"
            f"  min-width: 160px;"
            f"}}"
            f"QComboBox:focus {{"
            f"  border-color: {C.ACCENT};"
            f"}}"
            f"QComboBox::drop-down {{"
            f"  border: none; width: 28px;"
            f"}}"
            f"QComboBox QAbstractItemView {{"
            f"  background-color: {C.BG_CARD};"
            f"  color: {C.TEXT};"
            f"  border: 1px solid {C.BORDER};"
            f"  selection-background-color: {C.ACCENT_BG};"
            f"  selection-color: {C.ACCENT};"
            f"}}"
        )

        grid = QGridLayout()
        grid.setSpacing(S.GAP)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 0)

        # Weight Mode
        grid.addWidget(
            icon_label(Icon.WEIGHT, color=C.ACCENT, size=16), 0, 0
        )
        wlbl = QLabel("Weight Mode")
        wlbl.setStyleSheet(f"color: {C.TEXT}; font-size: {F.BODY}px;")
        grid.addWidget(wlbl, 0, 1)

        self._weight_mode_combo = QComboBox()
        self._weight_mode_combo.addItems(["arduino_serial", "hx711_direct"])
        self._weight_mode_combo.setMinimumHeight(36)
        self._weight_mode_combo.setStyleSheet(combo_style)
        grid.addWidget(self._weight_mode_combo, 0, 2)

        # Buzzer Mode
        grid.addWidget(
            icon_label(Icon.ALARM, color=C.ACCENT, size=16), 1, 0
        )
        blbl = QLabel("Buzzer Mode")
        blbl.setStyleSheet(f"color: {C.TEXT}; font-size: {F.BODY}px;")
        grid.addWidget(blbl, 1, 1)

        self._buzzer_mode_combo = QComboBox()
        self._buzzer_mode_combo.addItems(["all", "alarms_only", "mute"])
        self._buzzer_mode_combo.setMinimumHeight(36)
        self._buzzer_mode_combo.setStyleSheet(combo_style)
        grid.addWidget(self._buzzer_mode_combo, 1, 2)

        lay.addLayout(grid)
        return card

    # ──────────────────────────────────────────────────
    # ACTIONS card
    # ──────────────────────────────────────────────────

    def _build_actions_card(self) -> QFrame:
        card = self._make_card(C.PRIMARY)
        lay = QVBoxLayout(card)
        lay.setSpacing(S.GAP)

        lay.addWidget(
            section_header(Icon.SAVE, "ACTIONS", C.PRIMARY)
        )

        # Save & Restart
        btn_save = QPushButton(f"{Icon.SAVE}  SAVE & RESTART")
        btn_save.setObjectName("accent")
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setMinimumHeight(48)
        btn_save.clicked.connect(self._save_and_restart)
        lay.addWidget(btn_save)

        # Reset to defaults
        btn_reset = QPushButton(f"{Icon.REFRESH}  RESET TO DEFAULTS")
        btn_reset.setObjectName("danger")
        btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset.setMinimumHeight(44)
        btn_reset.clicked.connect(self._reset_defaults)
        lay.addWidget(btn_reset)

        # Close app
        btn_close = QPushButton(f"{Icon.CLOSE}  CLOSE APP")
        btn_close.setObjectName("ghost")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setMinimumHeight(44)
        btn_close.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: transparent;"
            f"  color: {C.DANGER};"
            f"  border: 2px solid {C.DANGER};"
            f"  border-radius: 8px;"
            f"  font-size: {F.BODY}px; font-weight: bold;"
            f"  min-height: 44px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {C.DANGER_BG};"
            f"}}"
        )
        btn_close.clicked.connect(self._close_app)
        lay.addWidget(btn_close)

        return card

    # ══════════════════════════════════════════════════
    # LIFECYCLE
    # ══════════════════════════════════════════════════

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

        buzzer_mode = admin_cfg.get("buzzer_mode", "all")
        idx = self._buzzer_mode_combo.findText(buzzer_mode)
        if idx >= 0:
            self._buzzer_mode_combo.setCurrentIndex(idx)

    def _save_and_restart(self):
        admin_cfg = self.app.db.get_admin_config()
        admin_cfg["driver_rfid"] = self._combos["rfid"].currentText()
        admin_cfg["driver_weight"] = self._combos["weight"].currentText()
        admin_cfg["driver_led"] = self._combos["led"].currentText()
        admin_cfg["driver_buzzer"] = self._combos["buzzer"].currentText()
        admin_cfg["weight_mode"] = self._weight_mode_combo.currentText()
        admin_cfg["buzzer_mode"] = self._buzzer_mode_combo.currentText()

        self.app.db.conn.execute(
            """INSERT OR REPLACE INTO config (key, value, updated_at)
               VALUES ('admin_settings', ?, datetime('now'))""",
            (json.dumps(admin_cfg),),
        )
        self.app.db.conn.commit()
        logger.info(f"Admin settings saved: {admin_cfg}")

        # Restart: launch new process after a delay so serial port is released
        import sys
        import os
        import subprocess
        python = sys.executable
        script = os.path.abspath(sys.argv[0])
        args = sys.argv[1:]
        # Use bash to delay 3s before restarting
        restart_cmd = f"sleep 3 && {python} {script} {' '.join(args)}"
        subprocess.Popen(["bash", "-c", restart_cmd])

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

    # ══════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════

    @staticmethod
    def _make_card(accent_color: str = C.BORDER) -> QFrame:
        """Create a styled card frame with left accent border."""
        card = QFrame()
        card.setObjectName("card")
        card.setProperty("card", True)
        card.setStyleSheet(
            f"QFrame#card {{"
            f"  background-color: {C.BG_CARD};"
            f"  border: 1px solid {C.BORDER};"
            f"  border-left: 4px solid {accent_color};"
            f"  border-radius: {S.RADIUS}px;"
            f"  padding: {S.PAD_CARD}px;"
            f"}}"
        )
        return card
