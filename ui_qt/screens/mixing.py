"""
SmartLocker Mixing Screen

Full mixing workflow: select recipe -> weigh base -> weigh hardener -> confirm -> pot life.
Optimized for 800x480 4.3" touch display.

7-page wizard:
  Page 0: Select Recipe
  Page 1: Show Recipe / Enter Amount
  Page 2: Weighing (base or hardener) -- CRITICAL
  Page 3: Confirm Mix
  Page 4: Thinner (application method)
  Page 5: Pot Life Active
  Page 6: Session Complete
"""

import logging
import time
import threading

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox, QLineEdit, QProgressBar, QApplication,
    QStackedWidget, QGridLayout, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer

from ui_qt.theme import C, F, S
from ui_qt.animations import ProgressRing, PulsingDot
from ui_qt.icons import (
    Icon, icon_badge, icon_label, status_dot, type_badge, section_header,
    screen_header,
)
from core.models import MixingState, ApplicationMethod
from hal.interfaces import BuzzerPattern

logger = logging.getLogger("smartlocker.ui.mixing")


# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────

def _card_frame(accent: str = C.PRIMARY) -> QFrame:
    """Return a styled QFrame card with left-border accent."""
    card = QFrame()
    card.setObjectName("card")
    card.setStyleSheet(
        f"QFrame#card {{"
        f"  background-color: {C.BG_CARD};"
        f"  border: 1px solid {C.BORDER};"
        f"  border-left: 4px solid {accent};"
        f"  border-radius: {S.RADIUS}px;"
        f"}}"
    )
    return card


def _styled_combo() -> QComboBox:
    """Return a consistently styled QComboBox."""
    combo = QComboBox()
    combo.setStyleSheet(
        f"QComboBox {{"
        f"  background-color: {C.BG_INPUT}; color: {C.TEXT};"
        f"  border: 1px solid {C.BORDER}; border-radius: 8px;"
        f"  padding: 10px 14px; font-size: {F.BODY}px; min-height: 40px;"
        f"}}"
        f"QComboBox::drop-down {{ border: none; width: 28px; }}"
        f"QComboBox QAbstractItemView {{"
        f"  background-color: {C.BG_CARD}; color: {C.TEXT};"
        f"  border: 1px solid {C.BORDER};"
        f"  selection-background-color: {C.PRIMARY_BG};"
        f"  font-size: {F.BODY}px;"
        f"}}"
    )
    return combo


def _styled_input(placeholder: str = "", font_size: int = F.BODY) -> QLineEdit:
    """Return a consistently styled QLineEdit."""
    inp = QLineEdit()
    inp.setPlaceholderText(placeholder)
    inp.setStyleSheet(
        f"background-color: {C.BG_INPUT}; color: {C.TEXT};"
        f"border: 1px solid {C.BORDER}; border-radius: 8px;"
        f"padding: 8px 12px; font-size: {font_size}px; min-height: 40px;"
    )
    return inp


def _gradient_btn(text: str, color1: str = C.PRIMARY,
                  color2: str = C.SECONDARY, font_size: int = F.H3,
                  min_h: int = S.BTN_H_LG) -> QPushButton:
    """Return a gradient-styled primary action button."""
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton {{"
        f"  background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
        f"    stop:0 {color1}, stop:1 {color2});"
        f"  color: {C.BG_DARK}; border: none; border-radius: {S.RADIUS}px;"
        f"  font-size: {font_size}px; font-weight: bold;"
        f"  min-height: {min_h}px; padding: 8px 16px;"
        f"}}"
        f"QPushButton:hover {{"
        f"  background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
        f"    stop:0 {C.PRIMARY_DIM}, stop:1 {color2});"
        f"}}"
    )
    return btn


# ═════════════════════════════════════════════════════════
# MIXING SCREEN
# ═════════════════════════════════════════════════════════

class MixingScreen(QWidget):
    """Mixing workflow wizard -- 7-page stacked widget."""

    def __init__(self, app):
        super().__init__()
        self.app = app

        # Timers
        self._weight_timer = QTimer()
        self._weight_timer.timeout.connect(self._update_weight)
        self._pot_life_timer = QTimer()
        self._pot_life_timer.timeout.connect(self._update_pot_life)

        # State
        self._last_buzzer_zone = ""
        self._tick_counter = 0
        self._barcode_verified_base = False
        self._barcode_verified_hardener = False
        self._current_recipe = None
        self._weighing_phase = "base"
        self._weight_target = 0.0
        self._recipes_list = []

        self._build_ui()

    # ══════════════════════════════════════════════════════
    # UI BUILD
    # ══════════════════════════════════════════════════════

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ──
        header, h_layout = screen_header(
            self.app, "MIXING", Icon.MIXING, C.PRIMARY
        )

        self._state_badge = type_badge("IDLE", "muted")
        h_layout.addWidget(self._state_badge)

        root.addWidget(header)

        # ── Stacked pages ──
        self._stack = QStackedWidget()
        root.addWidget(self._stack, stretch=1)

        self._page_select = self._build_select_page()
        self._stack.addWidget(self._page_select)

        self._page_recipe = self._build_recipe_page()
        self._stack.addWidget(self._page_recipe)

        self._page_weigh = self._build_weigh_page()
        self._stack.addWidget(self._page_weigh)

        self._page_confirm = self._build_confirm_page()
        self._stack.addWidget(self._page_confirm)

        self._page_thinner = self._build_thinner_page()
        self._stack.addWidget(self._page_thinner)

        self._page_potlife = self._build_potlife_page()
        self._stack.addWidget(self._page_potlife)

        self._page_complete = self._build_complete_page()
        self._stack.addWidget(self._page_complete)

    # ──────────────────────────────────────────────────────
    # Helper to update the state badge text + variant
    # ──────────────────────────────────────────────────────

    def _set_state_badge(self, text: str, variant: str = "muted"):
        colors = {
            "primary": (C.PRIMARY_BG, C.PRIMARY, C.PRIMARY),
            "secondary": (C.SECONDARY_BG, C.SECONDARY, C.SECONDARY),
            "accent": (C.ACCENT_BG, C.ACCENT, C.ACCENT),
            "success": (C.SUCCESS_BG, C.SUCCESS, C.SUCCESS),
            "warning": (C.WARNING_BG, C.WARNING, C.WARNING),
            "danger": (C.DANGER_BG, C.DANGER, C.DANGER),
            "muted": (C.BG_CARD_ALT, C.TEXT_MUTED, C.TEXT_MUTED),
        }
        bg, fg, bd = colors.get(variant, colors["muted"])
        self._state_badge.setText(text)
        self._state_badge.setStyleSheet(
            f"background-color: {bg}; color: {fg};"
            f"border: 1px solid {bd}; border-radius: 4px;"
            f"padding: 2px 8px; font-size: {F.TINY}px; font-weight: bold;"
        )

    # ══════════════════════════════════════════════════════
    # PAGE 0: SELECT RECIPE
    # ══════════════════════════════════════════════════════

    def _build_select_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(S.PAD * 2, S.PAD * 2, S.PAD * 2, S.PAD * 2)
        lay.setSpacing(S.PAD)

        # Centered icon
        badge = icon_badge(Icon.MIXING, bg_color=C.PRIMARY_BG,
                           fg_color=C.PRIMARY, size=40)
        lay.addWidget(badge, alignment=Qt.AlignmentFlag.AlignCenter)

        # Title
        title = QLabel("SELECT RECIPE")
        title.setStyleSheet(
            f"font-size: {F.H2}px; font-weight: bold; color: {C.PRIMARY};"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        lay.addSpacing(4)

        # Recipe dropdown
        self._combo_recipe = _styled_combo()
        lay.addWidget(self._combo_recipe)

        # Operator row
        op_row = QHBoxLayout()
        op_row.setSpacing(S.GAP)

        op_icon = icon_label(Icon.INFO, color=C.TEXT_SEC, size=16)
        op_row.addWidget(op_icon)

        op_lbl = QLabel("OPERATOR")
        op_lbl.setStyleSheet(
            f"font-size: {F.SMALL}px; font-weight: bold; color: {C.TEXT_SEC};"
        )
        op_row.addWidget(op_lbl)

        self._input_user = _styled_input("Name (optional)")
        op_row.addWidget(self._input_user, stretch=1)

        lay.addLayout(op_row)

        lay.addStretch(1)

        # Start button -- gradient
        btn_start = _gradient_btn(
            f"{Icon.PLAY}  START MIXING", C.PRIMARY, C.SECONDARY, F.H3
        )
        btn_start.clicked.connect(self._on_start)
        lay.addWidget(btn_start)

        return page

    # ══════════════════════════════════════════════════════
    # PAGE 1: SHOW RECIPE / ENTER AMOUNT
    # ══════════════════════════════════════════════════════

    def _build_recipe_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(S.PAD * 2, S.PAD, S.PAD * 2, S.PAD)
        lay.setSpacing(S.PAD)

        # Recipe name
        self._lbl_recipe_name = QLabel("Recipe")
        self._lbl_recipe_name.setStyleSheet(
            f"font-size: {F.H2}px; font-weight: bold; color: {C.PRIMARY};"
        )
        self._lbl_recipe_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._lbl_recipe_name)

        # Recipe info card with left border
        info_card = _card_frame(C.PRIMARY)
        info_grid = QGridLayout(info_card)
        info_grid.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
        info_grid.setSpacing(S.GAP)

        # Row 0
        lbl_r = QLabel("RATIO")
        lbl_r.setStyleSheet(
            f"font-size: {F.TINY}px; color: {C.TEXT_MUTED}; font-weight: bold;"
        )
        info_grid.addWidget(lbl_r, 0, 0)

        lbl_p = QLabel("POT LIFE")
        lbl_p.setStyleSheet(
            f"font-size: {F.TINY}px; color: {C.TEXT_MUTED}; font-weight: bold;"
        )
        info_grid.addWidget(lbl_p, 0, 1)

        lbl_t = QLabel("TOLERANCE")
        lbl_t.setStyleSheet(
            f"font-size: {F.TINY}px; color: {C.TEXT_MUTED}; font-weight: bold;"
        )
        info_grid.addWidget(lbl_t, 0, 2)

        # Row 1: values
        self._lbl_ratio = QLabel("--")
        self._lbl_ratio.setStyleSheet(
            f"font-size: {F.BODY}px; font-weight: bold; color: {C.TEXT};"
        )
        info_grid.addWidget(self._lbl_ratio, 1, 0)

        self._lbl_potlife_info = QLabel("--")
        self._lbl_potlife_info.setStyleSheet(
            f"font-size: {F.BODY}px; font-weight: bold; color: {C.TEXT};"
        )
        info_grid.addWidget(self._lbl_potlife_info, 1, 1)

        self._lbl_tolerance = QLabel("--")
        self._lbl_tolerance.setStyleSheet(
            f"font-size: {F.BODY}px; font-weight: bold; color: {C.TEXT};"
        )
        info_grid.addWidget(self._lbl_tolerance, 1, 2)

        lay.addWidget(info_card)

        # Base amount section
        amt_header = section_header(Icon.WEIGHT, "BASE AMOUNT (g)", C.SECONDARY)
        lay.addWidget(amt_header)

        amount_row = QHBoxLayout()
        amount_row.setSpacing(S.GAP)

        self._input_amount = _styled_input("e.g. 500", F.H3)
        self._input_amount.setAlignment(Qt.AlignmentFlag.AlignCenter)
        amount_row.addWidget(self._input_amount, stretch=1)

        for preset in ["250", "500", "1000", "2000"]:
            btn = QPushButton(f"{preset}g")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"background-color: {C.BG_CARD_ALT}; color: {C.TEXT_SEC};"
                f"border: 1px solid {C.BORDER}; border-radius: 6px;"
                f"padding: 6px 10px; font-size: {F.SMALL}px;"
                f"font-weight: bold; min-height: 36px;"
            )
            btn.clicked.connect(lambda _, v=preset: self._input_amount.setText(v))
            amount_row.addWidget(btn)

        lay.addLayout(amount_row)

        # Calculated targets card
        calc_card = _card_frame(C.SECONDARY)
        calc_lay = QHBoxLayout(calc_card)
        calc_lay.setContentsMargins(S.PAD, S.PAD_CARD, S.PAD, S.PAD_CARD)
        calc_lay.setSpacing(S.PAD)

        self._lbl_calc_base = QLabel("")
        self._lbl_calc_base.setStyleSheet(
            f"font-size: {F.BODY}px; font-weight: bold; color: {C.TEXT};"
        )
        calc_lay.addWidget(self._lbl_calc_base, stretch=1)

        self._lbl_calc_hardener = QLabel("")
        self._lbl_calc_hardener.setStyleSheet(
            f"font-size: {F.BODY}px; font-weight: bold; color: {C.ACCENT};"
        )
        calc_lay.addWidget(self._lbl_calc_hardener, stretch=1)

        lay.addWidget(calc_card)

        lay.addStretch(1)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(S.GAP)

        btn_cancel = QPushButton(f"{Icon.CLOSE}  CANCEL")
        btn_cancel.setObjectName("danger")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setMinimumHeight(48)
        btn_cancel.clicked.connect(self._on_abort)
        btn_row.addWidget(btn_cancel)

        btn_next = _gradient_btn(
            f"{Icon.PLAY}  TARE & START", C.PRIMARY, C.SECONDARY, F.BODY, 48
        )
        btn_next.clicked.connect(self._on_tare_and_pour)
        btn_row.addWidget(btn_next, stretch=1)

        lay.addLayout(btn_row)

        return page

    # ══════════════════════════════════════════════════════
    # PAGE 2: WEIGHING (BASE / HARDENER) -- CRITICAL
    # ══════════════════════════════════════════════════════

    def _build_weigh_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(S.PAD * 2, S.PAD, S.PAD * 2, S.PAD)
        lay.setSpacing(S.GAP)

        # Pour title
        self._lbl_pour_title = QLabel("POUR BASE")
        self._lbl_pour_title.setStyleSheet(
            f"font-size: {F.H2}px; font-weight: bold; color: {C.PRIMARY};"
        )
        self._lbl_pour_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._lbl_pour_title)

        # Main weight card with gradient background
        weight_card = QFrame()
        weight_card.setObjectName("weight_card")
        weight_card.setStyleSheet(
            f"QFrame#weight_card {{"
            f"  background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"    stop:0 {C.BG_CARD}, stop:0.5 {C.BG_CARD_ALT},"
            f"    stop:1 {C.BG_CARD});"
            f"  border: 1px solid {C.BORDER};"
            f"  border-left: 4px solid {C.PRIMARY};"
            f"  border-radius: {S.RADIUS}px;"
            f"}}"
        )
        wc_lay = QVBoxLayout(weight_card)
        wc_lay.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
        wc_lay.setSpacing(S.GAP)

        # Weight row: ProgressRing LEFT + Weight text RIGHT
        weight_row = QHBoxLayout()
        weight_row.setSpacing(S.PAD * 2)

        # Circular progress ring (left side)
        self._pour_ring = ProgressRing(size=100, thickness=8)
        self._pour_ring.set_color(C.PRIMARY)
        weight_row.addWidget(
            self._pour_ring,
            alignment=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )

        # Weight text column (right side)
        weight_text = QVBoxLayout()
        weight_text.setSpacing(2)

        self._lbl_weight_current = QLabel("0.00 kg")
        self._lbl_weight_current.setStyleSheet(
            f"font-size: {F.HERO}px; font-weight: bold; color: {C.PRIMARY};"
        )
        self._lbl_weight_current.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        weight_text.addWidget(self._lbl_weight_current)

        self._lbl_weight_target = QLabel("Target: --- kg")
        self._lbl_weight_target.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.TEXT_MUTED};"
        )
        self._lbl_weight_target.setAlignment(Qt.AlignmentFlag.AlignRight)
        weight_text.addWidget(self._lbl_weight_target)

        # Zone label (dynamic color)
        self._lbl_weight_zone = QLabel("Start pouring...")
        self._lbl_weight_zone.setStyleSheet(
            f"font-size: {F.BODY}px; font-weight: bold; color: {C.TEXT_MUTED};"
        )
        self._lbl_weight_zone.setAlignment(Qt.AlignmentFlag.AlignRight)
        weight_text.addWidget(self._lbl_weight_zone)

        weight_row.addLayout(weight_text, stretch=1)
        wc_lay.addLayout(weight_row)

        # Linear progress bar (16px, rounded, dynamic color)
        self._progress_weight = QProgressBar()
        self._progress_weight.setRange(0, 100)
        self._progress_weight.setValue(0)
        self._progress_weight.setStyleSheet(
            f"QProgressBar {{"
            f"  background-color: {C.BG_INPUT}; border: none;"
            f"  border-radius: 8px; min-height: 16px; max-height: 16px;"
            f"}}"
            f"QProgressBar::chunk {{"
            f"  background-color: {C.PRIMARY}; border-radius: 8px;"
            f"}}"
        )
        wc_lay.addWidget(self._progress_weight)

        # Barcode verification banner (hidden until scan)
        self._barcode_banner = QFrame()
        self._barcode_banner.setVisible(False)
        bb_lay = QHBoxLayout(self._barcode_banner)
        bb_lay.setContentsMargins(S.PAD_CARD, 6, S.PAD_CARD, 6)
        bb_lay.setSpacing(S.GAP)

        self._barcode_icon = QLabel()
        self._barcode_icon.setFixedWidth(28)
        self._barcode_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bb_lay.addWidget(self._barcode_icon)

        self._barcode_msg = QLabel("")
        self._barcode_msg.setStyleSheet(
            f"font-size: {F.SMALL}px; font-weight: bold;"
        )
        bb_lay.addWidget(self._barcode_msg, stretch=1)
        wc_lay.addWidget(self._barcode_banner)

        # RFID hint (hidden unless RFID down)
        self._lbl_rfid_hint = QLabel(
            f"{Icon.WARN}  RFID unavailable -- scan barcode to verify product"
        )
        self._lbl_rfid_hint.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.WARNING}; font-style: italic;"
        )
        self._lbl_rfid_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_rfid_hint.setVisible(False)
        wc_lay.addWidget(self._lbl_rfid_hint)

        lay.addWidget(weight_card, stretch=1)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(S.GAP)

        btn_abort = QPushButton(f"{Icon.CLOSE}  ABORT")
        btn_abort.setObjectName("danger")
        btn_abort.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_abort.setMinimumHeight(48)
        btn_abort.clicked.connect(self._on_abort)
        btn_row.addWidget(btn_abort)

        self._btn_confirm_pour = QPushButton(f"{Icon.OK}  CONFIRM POUR")
        self._btn_confirm_pour.setObjectName("success")
        self._btn_confirm_pour.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_confirm_pour.setMinimumHeight(48)
        self._btn_confirm_pour.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {C.SUCCESS}; color: {C.BG_DARK};"
            f"  border: none; border-radius: {S.RADIUS}px;"
            f"  font-size: {F.BODY}px; font-weight: bold;"
            f"  min-height: 48px; padding: 8px 16px;"
            f"}}"
            f"QPushButton:hover {{ background-color: #2ab86a; }}"
        )
        self._btn_confirm_pour.clicked.connect(self._on_confirm_pour)
        btn_row.addWidget(self._btn_confirm_pour, stretch=1)

        lay.addLayout(btn_row)

        return page

    # ══════════════════════════════════════════════════════
    # PAGE 3: CONFIRM MIX
    # ══════════════════════════════════════════════════════

    def _build_confirm_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(S.PAD * 2, S.PAD * 2, S.PAD * 2, S.PAD)
        lay.setSpacing(S.PAD)

        # Title
        title = QLabel("MIX RESULT")
        title.setStyleSheet(
            f"font-size: {F.H2}px; font-weight: bold; color: {C.PRIMARY};"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        # Results card
        card = _card_frame(C.PRIMARY)
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
        card_lay.setSpacing(S.GAP)

        self._lbl_result_base = QLabel("Base: ---")
        self._lbl_result_base.setStyleSheet(
            f"font-size: {F.BODY}px; color: {C.TEXT};"
        )
        card_lay.addWidget(self._lbl_result_base)

        self._lbl_result_hardener = QLabel("Hardener: ---")
        self._lbl_result_hardener.setStyleSheet(
            f"font-size: {F.BODY}px; color: {C.TEXT};"
        )
        card_lay.addWidget(self._lbl_result_hardener)

        # Ratio + spec badge row
        ratio_row = QHBoxLayout()
        ratio_row.setSpacing(S.GAP)

        self._lbl_result_ratio = QLabel("Ratio: ---")
        self._lbl_result_ratio.setStyleSheet(
            f"font-size: {F.H2}px; font-weight: bold; color: {C.SUCCESS};"
        )
        self._lbl_result_ratio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ratio_row.addWidget(self._lbl_result_ratio, stretch=1)

        self._lbl_result_spec = type_badge("--", "muted")
        ratio_row.addWidget(self._lbl_result_spec)

        card_lay.addLayout(ratio_row)

        lay.addWidget(card)
        lay.addStretch(1)

        btn = _gradient_btn(
            f"{Icon.OK}  CONFIRM MIX", C.SUCCESS, C.PRIMARY, F.H3
        )
        btn.clicked.connect(self._on_confirm_mix)
        lay.addWidget(btn)

        return page

    # ══════════════════════════════════════════════════════
    # PAGE 4: THINNER (Application Method)
    # ══════════════════════════════════════════════════════

    def _build_thinner_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(S.PAD * 2, S.PAD * 2, S.PAD * 2, S.PAD)
        lay.setSpacing(S.PAD)

        # Title
        title = QLabel("ADD THINNER?")
        title.setStyleSheet(
            f"font-size: {F.H2}px; font-weight: bold; color: {C.PRIMARY};"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        sub = QLabel("Select application method:")
        sub.setStyleSheet(f"font-size: {F.BODY}px; color: {C.TEXT_SEC};")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(sub)

        lay.addSpacing(S.GAP)

        # Method buttons with icon_badges
        methods = [
            ("brush", "BRUSH", Icon.EDIT),
            ("roller", "ROLLER", Icon.SHELF),
            ("spray", "SPRAY", Icon.CLOUD),
        ]

        btn_row = QHBoxLayout()
        btn_row.setSpacing(S.PAD)

        for method_key, method_label, method_icon in methods:
            method_card = QFrame()
            method_card.setStyleSheet(
                f"QFrame {{"
                f"  background-color: {C.BG_CARD};"
                f"  border: 1px solid {C.BORDER};"
                f"  border-radius: {S.RADIUS}px;"
                f"}}"
                f"QFrame:hover {{ border-color: {C.PRIMARY}; }}"
            )
            mc_lay = QVBoxLayout(method_card)
            mc_lay.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
            mc_lay.setSpacing(S.GAP)
            mc_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

            badge = icon_badge(method_icon, bg_color=C.PRIMARY_BG,
                               fg_color=C.PRIMARY, size=36)
            mc_lay.addWidget(badge, alignment=Qt.AlignmentFlag.AlignCenter)

            btn = QPushButton(method_label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"background-color: transparent; color: {C.TEXT};"
                f"border: none; font-size: {F.BODY}px; font-weight: bold;"
                f"min-height: 36px;"
            )
            btn.clicked.connect(lambda _, m=method_key: self._on_thinner(m))
            mc_lay.addWidget(btn)

            btn_row.addWidget(method_card)

        lay.addLayout(btn_row)

        lay.addStretch(1)

        btn_skip = QPushButton(f"{Icon.FORWARD}  SKIP - NO THINNER")
        btn_skip.setObjectName("secondary")
        btn_skip.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_skip.setMinimumHeight(48)
        btn_skip.clicked.connect(self._on_skip_thinner)
        lay.addWidget(btn_skip)

        return page

    # ══════════════════════════════════════════════════════
    # PAGE 5: POT LIFE ACTIVE
    # ══════════════════════════════════════════════════════

    def _build_potlife_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(S.PAD * 2, S.PAD, S.PAD * 2, S.PAD)
        lay.setSpacing(S.PAD)

        # Title
        title = QLabel("POT LIFE ACTIVE")
        title.setStyleSheet(
            f"font-size: {F.H2}px; font-weight: bold; color: {C.SUCCESS};"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        # Large countdown ProgressRing
        self._potlife_ring = ProgressRing(size=120, thickness=10)
        self._potlife_ring.set_color(C.SUCCESS)
        lay.addWidget(
            self._potlife_ring, alignment=Qt.AlignmentFlag.AlignCenter
        )

        # Time text
        self._lbl_potlife_remaining = QLabel("--:--:--")
        self._lbl_potlife_remaining.setStyleSheet(
            f"font-size: {F.HERO}px; font-weight: bold; color: {C.PRIMARY};"
        )
        self._lbl_potlife_remaining.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._lbl_potlife_remaining)

        # Progress bar
        self._progress_potlife = QProgressBar()
        self._progress_potlife.setRange(0, 100)
        self._progress_potlife.setValue(0)
        self._progress_potlife.setStyleSheet(
            f"QProgressBar {{"
            f"  background-color: {C.BG_INPUT}; border: none;"
            f"  border-radius: 6px; min-height: 12px; max-height: 12px;"
            f"}}"
            f"QProgressBar::chunk {{"
            f"  background-color: {C.SUCCESS}; border-radius: 6px;"
            f"}}"
        )
        lay.addWidget(self._progress_potlife)

        self._lbl_potlife_status = QLabel("Mix is usable")
        self._lbl_potlife_status.setStyleSheet(
            f"font-size: {F.BODY}px; color: {C.TEXT_SEC};"
        )
        self._lbl_potlife_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._lbl_potlife_status)

        lay.addStretch(1)

        btn = _gradient_btn(
            f"{Icon.OK}  DONE - COMPLETE SESSION", C.PRIMARY, C.SECONDARY,
            F.BODY, 48
        )
        btn.clicked.connect(self._on_complete)
        lay.addWidget(btn)

        return page

    # ══════════════════════════════════════════════════════
    # PAGE 6: SESSION COMPLETE
    # ══════════════════════════════════════════════════════

    def _build_complete_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(S.PAD * 2, S.PAD * 2, S.PAD * 2, S.PAD * 2)
        lay.setSpacing(S.PAD)

        lay.addStretch(1)

        # Success icon
        success_badge = icon_badge(
            Icon.OK, bg_color=C.SUCCESS_BG, fg_color=C.SUCCESS, size=56
        )
        lay.addWidget(success_badge, alignment=Qt.AlignmentFlag.AlignCenter)

        title = QLabel("SESSION COMPLETE")
        title.setStyleSheet(
            f"font-size: {F.H2}px; font-weight: bold; color: {C.SUCCESS};"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        # Summary card
        summary_card = _card_frame(C.SUCCESS)
        sc_lay = QVBoxLayout(summary_card)
        sc_lay.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
        sc_lay.setSpacing(S.GAP)

        self._lbl_summary = QLabel("")
        self._lbl_summary.setStyleSheet(
            f"font-size: {F.BODY}px; color: {C.TEXT};"
        )
        self._lbl_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_summary.setWordWrap(True)
        sc_lay.addWidget(self._lbl_summary)

        lay.addWidget(summary_card)

        lay.addStretch(1)

        btn = _gradient_btn(
            f"{Icon.HOME}  BACK TO HOME", C.PRIMARY, C.SECONDARY, F.H3
        )
        btn.clicked.connect(lambda: self.app.go_screen("home"))
        lay.addWidget(btn)

        return page

    # ══════════════════════════════════════════════════════
    # LIFECYCLE
    # ══════════════════════════════════════════════════════

    def on_enter(self):
        self._load_recipes()
        self._stack.setCurrentIndex(0)
        self._set_state_badge("IDLE", "muted")
        self._input_user.clear()

        # Check if PaintNow passed pre-calculated quantities
        pending = getattr(self.app, "pending_mix", None)
        if pending:
            self.app.pending_mix = None  # consume it
            self._auto_start_from_paint_now(pending)

    def on_leave(self):
        self._weight_timer.stop()
        self._pot_life_timer.stop()

    def _auto_start_from_paint_now(self, pending: dict):
        """Auto-start mixing session with pre-calculated quantities from PaintNow."""
        product_name = pending.get("product_name", "Paint")
        base_grams = pending.get("base_grams", 0)
        ratio_base = pending.get("ratio_base", 4.0)
        ratio_hardener = pending.get("ratio_hardener", 1.0)
        pot_life = pending.get("pot_life_minutes", 480)
        tolerance = pending.get("tolerance_pct", 5.0)
        area_name = pending.get("area_name", "")

        if base_grams <= 0:
            logger.warning("PaintNow pending_mix has no base_grams, ignoring")
            return

        # Create a recipe on-the-fly from PaintNow data
        recipe_id = f"paintnow_{product_name}_{int(time.time())}"
        recipe_name = f"{product_name}"
        if area_name:
            recipe_name = f"{product_name} - {area_name}"

        # Resolve real product_id from name via DB
        base_product_id = ""
        hardener_product_id = ""
        try:
            base_prod = self.app.db.get_product_by_name(product_name)
            if base_prod:
                base_product_id = base_prod.get("product_id", "")

            if base_product_id:
                recipe = self.app.db.find_recipe_by_product_name(product_name)
                if recipe:
                    hardener_product_id = recipe.get("hardener_product_id", "")

            if not hardener_product_id:
                hard_name = pending.get("hardener_name", "")
                if hard_name and hard_name != "Hardener":
                    hard_prod = self.app.db.get_product_by_name(hard_name)
                    if hard_prod:
                        hardener_product_id = hard_prod.get("product_id", "")

            if not hardener_product_id:
                products = self.app.db.get_products()
                for p in products:
                    if p.get("product_type") == "hardener":
                        pname = p.get("name", "").upper()
                        base_short = product_name.upper().replace("SIGMA", "S")
                        if base_short in pname or product_name.upper()[:6] in pname:
                            hardener_product_id = p.get("product_id", "")
                            break
        except Exception as e:
            logger.debug(f"Product lookup for PaintNow recipe: {e}")

        if not base_product_id:
            base_product_id = pending.get("product_name", "")
        if not hardener_product_id:
            hardener_product_id = pending.get("hardener_name", "")

        from core.models import MixingRecipe
        mr = MixingRecipe(
            recipe_id=recipe_id,
            name=recipe_name,
            base_product_id=base_product_id,
            hardener_product_id=hardener_product_id,
            ratio_base=ratio_base,
            ratio_hardener=ratio_hardener,
            tolerance_pct=tolerance,
            pot_life_minutes=pot_life,
        )

        self.app.mixing_engine.load_recipes({recipe_id: mr})
        self.app.mixing_engine.start_session(recipe_id, user_name="Crew")
        self.app.mixing_engine.show_recipe(base_grams)
        self.app.mixing_engine.tare_scale()

        session = self.app.mixing_engine.session
        if session:
            session.state = MixingState.WEIGH_BASE

        self._current_recipe = mr
        self._weighing_phase = "base"
        self._weight_target = base_grams
        self._last_buzzer_zone = ""
        self._tick_counter = 0

        # Update weigh page labels
        m2 = pending.get("m2", 0)
        liters = pending.get("base_liters", 0)
        info_text = f"POUR BASE - {product_name}"
        if m2 > 0:
            info_text = f"POUR BASE ({m2:.0f}m2 = {liters:.1f}L)"
        self._lbl_pour_title.setText(info_text)
        self._lbl_weight_target.setText(f"Target: {base_grams / 1000:.2f} kg")
        self._lbl_weight_current.setText("0.00 kg")
        self._progress_weight.setValue(0)
        self._lbl_weight_zone.setText("Place container, then pour...")

        self._barcode_verified_base = False
        self._barcode_verified_hardener = False

        # Jump directly to weigh page (page 2)
        self._stack.setCurrentIndex(2)
        self._set_state_badge("WEIGHING BASE", "primary")
        self._barcode_banner.setVisible(False)

        rfid_down = self._is_rfid_down()
        print(f"[MIXING] PaintNow auto-start: RFID down={rfid_down}")
        if rfid_down:
            self._show_barcode_required("BASE")
        else:
            self._weight_timer.start(300)

        logger.info(
            f"Auto-started mixing from PaintNow: {recipe_name} "
            f"base={base_grams:.0f}g target (rfid_down={rfid_down})"
        )

    # ══════════════════════════════════════════════════════
    # DATA LOADING
    # ══════════════════════════════════════════════════════

    def _load_recipes(self):
        self._combo_recipe.clear()
        self._recipes_list = []

        try:
            recipes = self.app.db.get_recipes()
            if recipes:
                for r in recipes:
                    name = r.get("name", "Unknown")
                    self._combo_recipe.addItem(name)
                    self._recipes_list.append(r)
        except Exception as e:
            logger.error(f"Failed to load recipes: {e}")

        if not self._recipes_list:
            self._combo_recipe.addItem("No recipes - sync with cloud first")

    # ══════════════════════════════════════════════════════
    # ACTIONS
    # ══════════════════════════════════════════════════════

    def _on_start(self):
        idx = self._combo_recipe.currentIndex()
        if idx < 0 or not self._recipes_list:
            return

        recipe = self._recipes_list[idx]
        recipe_id = recipe.get("recipe_id", recipe.get("name", ""))
        recipe_name = recipe.get("name", "Unknown")
        ratio_base = float(recipe.get("ratio_base", 4))
        ratio_hardener = float(recipe.get("ratio_hardener", 1))
        pot_life = int(recipe.get("pot_life_minutes", 480))
        tolerance = float(recipe.get("tolerance_pct", 5))

        from core.models import MixingRecipe
        mr = MixingRecipe(
            recipe_id=recipe_id,
            name=recipe_name,
            base_product_id=recipe.get("base_product_id", ""),
            hardener_product_id=recipe.get("hardener_product_id", ""),
            ratio_base=ratio_base,
            ratio_hardener=ratio_hardener,
            tolerance_pct=tolerance,
            pot_life_minutes=pot_life,
        )
        self.app.mixing_engine.load_recipes({recipe_id: mr})

        user = self._input_user.text().strip() or "Crew"
        self.app.mixing_engine.start_session(recipe_id, user_name=user)

        # Show recipe page
        self._lbl_recipe_name.setText(recipe_name)
        self._lbl_ratio.setText(f"{ratio_base}:{ratio_hardener}")
        self._lbl_potlife_info.setText(f"{pot_life} min")
        self._lbl_tolerance.setText(f"+/-{tolerance}%")
        self._input_amount.clear()
        self._lbl_calc_base.setText("")
        self._lbl_calc_hardener.setText("")

        self._current_recipe = mr
        self._stack.setCurrentIndex(1)
        self._set_state_badge("SELECT AMOUNT", "secondary")

        # Connect amount changes
        self._input_amount.textChanged.connect(self._on_amount_changed)

    def _on_amount_changed(self, text):
        try:
            base_g = float(text)
            hardener_g = base_g * (
                self._current_recipe.ratio_hardener
                / self._current_recipe.ratio_base
            )
            self._lbl_calc_base.setText(
                f"{Icon.WEIGHT} Base: {base_g / 1000:.2f} kg"
            )
            self._lbl_calc_hardener.setText(
                f"{Icon.WEIGHT} Hardener: {hardener_g / 1000:.2f} kg"
            )
        except (ValueError, AttributeError):
            self._lbl_calc_base.setText("")
            self._lbl_calc_hardener.setText("")

    def _is_rfid_down(self) -> bool:
        """Check if RFID is unavailable (fake driver or unhealthy)."""
        try:
            driver_status = getattr(self.app, "driver_status", {})
            rfid_drv = driver_status.get("rfid", "unknown")
            if rfid_drv == "fake":
                logger.info("[MIXING] RFID down: driver_status=fake")
                return True
            rfid = getattr(self.app, "rfid", None)
            if rfid and hasattr(rfid, "is_healthy"):
                healthy = rfid.is_healthy()
                logger.info(
                    f"[MIXING] RFID check: driver={rfid_drv}, is_healthy={healthy}"
                )
                return not healthy
            logger.info("[MIXING] RFID down: no driver or no is_healthy method")
            return True
        except Exception as e:
            logger.info(f"[MIXING] RFID down: exception {e}")
            return True

    def _on_tare_and_pour(self):
        try:
            base_g = float(self._input_amount.text())
        except ValueError:
            return

        engine = self.app.mixing_engine
        engine.show_recipe(base_g)
        engine.tare_scale()

        session = engine.session
        if session:
            session.state = MixingState.WEIGH_BASE

        self._barcode_verified_base = False
        self._barcode_verified_hardener = False

        self._weighing_phase = "base"
        self._weight_target = base_g
        self._lbl_pour_title.setText("POUR BASE")
        self._lbl_weight_target.setText(f"Target: {base_g / 1000:.2f} kg")
        self._lbl_weight_current.setText("0.00 kg")
        self._progress_weight.setValue(0)

        self._stack.setCurrentIndex(2)
        self._set_state_badge("WEIGHING BASE", "primary")
        self._barcode_banner.setVisible(False)

        rfid_down = self._is_rfid_down()
        print(f"[MIXING] RFID down={rfid_down}, requiring barcode={rfid_down}")
        if rfid_down:
            self._show_barcode_required("BASE")
        else:
            self._weight_timer.start(300)

    def _show_barcode_required(self, component: str):
        """Show barcode scan requirement banner and pause weighing."""
        self._barcode_banner.setVisible(True)
        self._barcode_banner.setStyleSheet(
            f"background-color: {C.ACCENT_BG}; border: 2px solid {C.ACCENT};"
            f"border-radius: 6px; padding: 8px;"
        )
        self._barcode_icon.setText(Icon.WARN)
        self._barcode_icon.setStyleSheet(
            f"color: {C.ACCENT}; font-weight: bold; font-size: {F.BODY}px;"
        )
        self._barcode_msg.setText(
            f"SCAN {component} BARCODE TO START POURING"
        )
        self._barcode_msg.setStyleSheet(
            f"font-size: {F.SMALL}px; font-weight: bold; color: {C.ACCENT};"
        )
        self._lbl_weight_zone.setText(f"Scan {component.lower()} barcode...")
        self._lbl_rfid_hint.setVisible(True)

    def _update_weight(self):
        """Timer callback: read weight, update ring/bar/zone/buzzer."""
        current = 0.0
        try:
            status = self.app.mixing_engine.check_weight_target()
            if status:
                current = status["current_g"]
            else:
                reading = self.app.weight.read_weight("mixing_scale")
                current = reading.grams
        except Exception as e:
            logger.error(f"Weight read error: {e}")
            return

        self._lbl_weight_current.setText(f"{current / 1000:.2f} kg")

        progress = (
            (current / self._weight_target * 100)
            if self._weight_target > 0 else 0
        )
        progress = min(100, max(0, progress))
        self._progress_weight.setValue(int(progress))

        # Determine zone (with audio-optimized thresholds)
        if progress < 85:
            zone = "pouring"
            color = C.PRIMARY
            zone_text = "Keep pouring..."
        elif progress < 98:
            zone = "approaching"
            color = C.WARNING
            zone_text = f"{Icon.WARN}  Slow down!"
        elif progress <= 100:
            zone = "in_range"
            color = C.SUCCESS
            zone_text = f"{Icon.OK}  STOP! Confirm pour"
        else:
            zone = "over"
            color = C.DANGER
            zone_text = f"{Icon.ERROR}  TOO MUCH!"

        # ── Buzzer feedback (audio guide for blind pouring) ──
        try:
            buzzer = self.app.buzzer
            self._tick_counter += 1

            if zone == "pouring" and current > 5:
                if self._tick_counter % 2 == 0:
                    buzzer.play(BuzzerPattern.POUR_STEADY)
            elif zone == "approaching":
                buzzer.play(BuzzerPattern.POUR_CLOSE)
            elif zone == "in_range":
                if self._tick_counter % 2 == 0:
                    buzzer.play(BuzzerPattern.POUR_TARGET)
            elif zone == "over":
                if self._last_buzzer_zone != "over":
                    buzzer.play(BuzzerPattern.ERROR)

            self._last_buzzer_zone = zone
        except Exception:
            pass  # Buzzer errors should never break weight display

        # Update weight text color
        self._lbl_weight_current.setStyleSheet(
            f"font-size: {F.HERO}px; font-weight: bold; color: {color};"
        )

        # Update zone label color
        self._lbl_weight_zone.setText(zone_text)
        self._lbl_weight_zone.setStyleSheet(
            f"font-size: {F.BODY}px; font-weight: bold; color: {color};"
        )

        # Update progress bar color
        self._progress_weight.setStyleSheet(
            f"QProgressBar {{"
            f"  background-color: {C.BG_INPUT}; border: none;"
            f"  border-radius: 8px; min-height: 16px; max-height: 16px;"
            f"}}"
            f"QProgressBar::chunk {{"
            f"  background-color: {color}; border-radius: 8px;"
            f"}}"
        )

        # Update circular progress ring
        self._pour_ring.set_value(progress / 100.0)
        self._pour_ring.set_color(color)

    def _on_confirm_pour(self):
        self._weight_timer.stop()
        engine = self.app.mixing_engine

        if self._weighing_phase == "base":
            engine.confirm_base_weighed()

            session = engine.session
            if session:
                session.state = MixingState.WEIGH_HARDENER
                hardener_target = session.hardener_weight_target_g

                self._weighing_phase = "hardener"
                self._weight_target = (
                    session.base_weight_actual_g + hardener_target
                )
                self._last_buzzer_zone = ""
                self._tick_counter = 0
                self._lbl_pour_title.setText("POUR HARDENER")
                self._lbl_weight_target.setText(
                    f"Target: +{hardener_target / 1000:.2f} kg "
                    f"(total {self._weight_target / 1000:.2f} kg)"
                )
                self._lbl_weight_current.setText(
                    f"{session.base_weight_actual_g / 1000:.2f} kg"
                )
                self._progress_weight.setValue(0)
                self._lbl_weight_zone.setText("Pour hardener...")

                self._set_state_badge("WEIGHING HARDENER", "accent")
                self._barcode_banner.setVisible(False)

                if self._is_rfid_down():
                    self._show_barcode_required("HARDENER")
                else:
                    self._barcode_verified_hardener = True
                    self._weight_timer.start(300)

        elif self._weighing_phase == "hardener":
            engine.confirm_hardener_weighed()

            session = engine.session
            if session:
                self._lbl_result_base.setText(
                    f"{Icon.WEIGHT}  Base: {session.base_weight_actual_g:.0f}g "
                    f"(target: {session.base_weight_target_g:.0f}g)"
                )
                self._lbl_result_hardener.setText(
                    f"{Icon.WEIGHT}  Hardener: {session.hardener_weight_actual_g:.0f}g "
                    f"(target: {session.hardener_weight_target_g:.0f}g)"
                )
                self._lbl_result_ratio.setText(
                    f"Ratio: {session.ratio_achieved:.2f}"
                )

                if session.ratio_in_spec:
                    self._lbl_result_spec.setText("IN SPEC")
                    self._lbl_result_spec.setStyleSheet(
                        f"background-color: {C.SUCCESS_BG}; color: {C.SUCCESS};"
                        f"border: 1px solid {C.SUCCESS}; border-radius: 4px;"
                        f"padding: 2px 8px; font-size: {F.TINY}px;"
                        f"font-weight: bold;"
                    )
                    self._lbl_result_ratio.setStyleSheet(
                        f"font-size: {F.H2}px; font-weight: bold;"
                        f"color: {C.SUCCESS};"
                    )
                else:
                    self._lbl_result_spec.setText("OUT OF SPEC!")
                    self._lbl_result_spec.setStyleSheet(
                        f"background-color: {C.DANGER_BG}; color: {C.DANGER};"
                        f"border: 1px solid {C.DANGER}; border-radius: 4px;"
                        f"padding: 2px 8px; font-size: {F.TINY}px;"
                        f"font-weight: bold;"
                    )
                    self._lbl_result_ratio.setStyleSheet(
                        f"font-size: {F.H2}px; font-weight: bold;"
                        f"color: {C.DANGER};"
                    )

                self._stack.setCurrentIndex(3)
                self._set_state_badge("CONFIRM MIX", "success")

    def _on_confirm_mix(self):
        self.app.mixing_engine.confirm_mix()
        self._stack.setCurrentIndex(4)
        self._set_state_badge("THINNER", "accent")

    def _on_thinner(self, method_str):
        method = {
            "brush": ApplicationMethod.BRUSH,
            "roller": ApplicationMethod.ROLLER,
            "spray": ApplicationMethod.SPRAY,
        }.get(method_str, ApplicationMethod.BRUSH)

        self.app.mixing_engine.add_thinner(method)
        self._start_potlife_display()

    def _on_skip_thinner(self):
        self.app.mixing_engine.skip_thinner()
        self._start_potlife_display()

    def _start_potlife_display(self):
        self._stack.setCurrentIndex(5)
        self._set_state_badge("POT LIFE", "warning")
        self._pot_life_timer.start(1000)
        self._update_pot_life()

    def _update_pot_life(self):
        status = self.app.mixing_engine.check_pot_life()
        if not status:
            return

        remaining = status["remaining_sec"]
        elapsed_pct = status["elapsed_pct"]

        hours = int(remaining // 3600)
        mins = int((remaining % 3600) // 60)
        secs = int(remaining % 60)
        self._lbl_potlife_remaining.setText(f"{hours:02d}:{mins:02d}:{secs:02d}")

        remaining_pct = max(0, 100 - elapsed_pct)
        self._progress_potlife.setValue(int(remaining_pct))
        self._potlife_ring.set_value(remaining_pct / 100.0)

        if status["expired"]:
            self._lbl_potlife_remaining.setStyleSheet(
                f"font-size: {F.HERO}px; font-weight: bold; color: {C.DANGER};"
            )
            self._lbl_potlife_status.setText(
                f"{Icon.ERROR}  EXPIRED! Discard the mix!"
            )
            self._lbl_potlife_status.setStyleSheet(
                f"font-size: {F.BODY}px; color: {C.DANGER}; font-weight: bold;"
            )
            self._potlife_ring.set_color(C.DANGER)
            self._progress_potlife.setStyleSheet(
                f"QProgressBar {{"
                f"  background-color: {C.BG_INPUT}; border: none;"
                f"  border-radius: 6px; min-height: 12px; max-height: 12px;"
                f"}}"
                f"QProgressBar::chunk {{"
                f"  background-color: {C.DANGER}; border-radius: 6px;"
                f"}}"
            )
        elif elapsed_pct >= 75:
            self._lbl_potlife_remaining.setStyleSheet(
                f"font-size: {F.HERO}px; font-weight: bold; color: {C.WARNING};"
            )
            self._lbl_potlife_status.setText(f"{Icon.WARN}  Use soon!")
            self._potlife_ring.set_color(C.WARNING)
            self._progress_potlife.setStyleSheet(
                f"QProgressBar {{"
                f"  background-color: {C.BG_INPUT}; border: none;"
                f"  border-radius: 6px; min-height: 12px; max-height: 12px;"
                f"}}"
                f"QProgressBar::chunk {{"
                f"  background-color: {C.WARNING}; border-radius: 6px;"
                f"}}"
            )
        else:
            self._lbl_potlife_remaining.setStyleSheet(
                f"font-size: {F.HERO}px; font-weight: bold; color: {C.PRIMARY};"
            )
            self._lbl_potlife_status.setText(f"{Icon.OK}  Mix is usable")
            self._potlife_ring.set_color(C.SUCCESS)

    def _on_complete(self):
        self._pot_life_timer.stop()

        session = self.app.mixing_engine.session
        if session:
            spec_text = "IN SPEC" if session.ratio_in_spec else "OUT OF SPEC"
            summary = (
                f"Base: {session.base_weight_actual_g:.0f}g  |  "
                f"Hardener: {session.hardener_weight_actual_g:.0f}g\n"
                f"Ratio: {session.ratio_achieved:.2f}  |  {spec_text}"
            )
            self._lbl_summary.setText(summary)

        self.app.mixing_engine.complete_session()
        self._stack.setCurrentIndex(6)
        self._set_state_badge("COMPLETE", "success")

    def _on_abort(self):
        self._weight_timer.stop()
        self._pot_life_timer.stop()
        self.app.mixing_engine.abort_session("User cancelled")
        self.app.go_back()

    def _on_back(self):
        engine = self.app.mixing_engine
        if engine.is_active:
            self._on_abort()
        else:
            self.app.go_back()

    # ══════════════════════════════════════════════════════
    # BARCODE VERIFICATION (called from app barcode handler)
    # ══════════════════════════════════════════════════════

    def on_barcode_verified(self, match: bool, component: str,
                            product_info: dict):
        """Called by app when barcode is scanned during mixing.

        Shows a banner on the weigh page indicating match/mismatch.
        If RFID is down and barcode matches, unlocks weighing.
        """
        name = product_info.get("product_name", "Unknown")
        self._barcode_banner.setVisible(True)

        if match:
            self._barcode_banner.setStyleSheet(
                f"background-color: {C.SUCCESS_BG};"
                f"border: 1px solid {C.SUCCESS};"
                f"border-radius: 6px;"
            )
            self._barcode_icon.setText(Icon.OK)
            self._barcode_icon.setStyleSheet(
                f"color: {C.SUCCESS}; font-weight: bold;"
                f"font-size: {F.BODY}px;"
            )
            self._barcode_msg.setText(f"CORRECT {component}: {name}")
            self._barcode_msg.setStyleSheet(
                f"font-size: {F.SMALL}px; font-weight: bold;"
                f"color: {C.SUCCESS};"
            )

            if component == "BASE" and not self._barcode_verified_base:
                self._barcode_verified_base = True
                self._lbl_rfid_hint.setVisible(False)
                self._weight_timer.start(300)
                QTimer.singleShot(
                    3000, lambda: self._barcode_banner.setVisible(False)
                )
                return
            elif component == "HARDENER" and not self._barcode_verified_hardener:
                self._barcode_verified_hardener = True
                self._lbl_rfid_hint.setVisible(False)
                self._weight_timer.start(300)
                QTimer.singleShot(
                    3000, lambda: self._barcode_banner.setVisible(False)
                )
                return
        else:
            self._barcode_banner.setStyleSheet(
                f"background-color: {C.DANGER_BG};"
                f"border: 2px solid {C.DANGER};"
                f"border-radius: 6px;"
            )
            self._barcode_icon.setText(Icon.ERROR)
            self._barcode_icon.setStyleSheet(
                f"color: {C.DANGER}; font-weight: bold;"
                f"font-size: {F.BODY}px;"
            )
            self._barcode_msg.setText(
                f"WARNING: {name} -- verify correct product!"
            )
            self._barcode_msg.setStyleSheet(
                f"font-size: {F.SMALL}px; font-weight: bold;"
                f"color: {C.DANGER};"
            )

            # Still unlock weighing even on mismatch
            if component == "BASE" and not self._barcode_verified_base:
                self._barcode_verified_base = True
                self._lbl_rfid_hint.setVisible(False)
                self._weight_timer.start(300)
            elif component == "HARDENER" and not self._barcode_verified_hardener:
                self._barcode_verified_hardener = True
                self._lbl_rfid_hint.setVisible(False)
                self._weight_timer.start(300)

        # Auto-hide after 8 seconds
        QTimer.singleShot(
            8000, lambda: self._barcode_banner.setVisible(False)
        )

    def _check_rfid_status(self):
        """Check if RFID is healthy and show hint if not."""
        try:
            rfid = getattr(self.app, "rfid", None)
            if rfid and hasattr(rfid, "is_healthy"):
                healthy = rfid.is_healthy()
                self._lbl_rfid_hint.setVisible(not healthy)
            else:
                driver_status = getattr(self.app, "driver_status", {})
                if driver_status.get("rfid") == "fake":
                    self._lbl_rfid_hint.setVisible(True)
        except Exception:
            pass
