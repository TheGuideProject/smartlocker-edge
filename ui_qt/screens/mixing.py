"""
SmartLocker Mixing Screen

Full mixing workflow: select recipe -> weigh base -> weigh hardener -> confirm -> pot life.
Optimized for 800x480 4.3" touch display.
"""

import logging
import time
import threading

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox, QLineEdit, QProgressBar, QApplication,
    QStackedWidget, QGridLayout,
)
from PyQt6.QtCore import Qt, QTimer

from ui_qt.theme import C, F, S
from core.models import MixingState, ApplicationMethod
from hal.interfaces import BuzzerPattern

logger = logging.getLogger("smartlocker.ui.mixing")

_PAD = 8
_GAP = 6
_F_BIG = 28
_F_MED = 16
_F_SM = 12


class MixingScreen(QWidget):
    """Mixing workflow wizard."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._weight_timer = QTimer()
        self._weight_timer.timeout.connect(self._update_weight)
        self._pot_life_timer = QTimer()
        self._pot_life_timer.timeout.connect(self._update_pot_life)
        self._last_buzzer_zone = ""   # Track zone changes for buzzer
        self._tick_counter = 0        # For periodic tick while pouring
        self._barcode_verified_base = False
        self._barcode_verified_hardener = False
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QFrame()
        header.setStyleSheet(
            f"background-color: {C.BG_STATUS}; border-bottom: 1px solid {C.BORDER};"
        )
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(_PAD, 4, _PAD, 4)

        btn_back = QPushButton("< BACK")
        btn_back.setObjectName("ghost")
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back.clicked.connect(self._on_back)
        h_lay.addWidget(btn_back)

        self._title = QLabel("MIXING")
        self._title.setStyleSheet(f"font-size: {F.H3}px; font-weight: bold;")
        h_lay.addWidget(self._title)
        h_lay.addStretch(1)

        self._state_badge = QLabel("IDLE")
        self._state_badge.setStyleSheet(
            f"font-size: {_F_SM}px; color: {C.TEXT_MUTED};"
        )
        h_lay.addWidget(self._state_badge)

        root.addWidget(header)

        # Stacked pages
        self._stack = QStackedWidget()
        root.addWidget(self._stack, stretch=1)

        # Page 0: Select Recipe
        self._page_select = self._build_select_page()
        self._stack.addWidget(self._page_select)

        # Page 1: Show Recipe / Enter Amount
        self._page_recipe = self._build_recipe_page()
        self._stack.addWidget(self._page_recipe)

        # Page 2: Weighing (base or hardener)
        self._page_weigh = self._build_weigh_page()
        self._stack.addWidget(self._page_weigh)

        # Page 3: Confirm Mix
        self._page_confirm = self._build_confirm_page()
        self._stack.addWidget(self._page_confirm)

        # Page 4: Thinner
        self._page_thinner = self._build_thinner_page()
        self._stack.addWidget(self._page_thinner)

        # Page 5: Pot Life Active
        self._page_potlife = self._build_potlife_page()
        self._stack.addWidget(self._page_potlife)

        # Page 6: Complete
        self._page_complete = self._build_complete_page()
        self._stack.addWidget(self._page_complete)

    # ══════════════════════════════════════════════════════
    # PAGE BUILDERS
    # ══════════════════════════════════════════════════════

    def _build_select_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(_PAD * 2, _PAD * 2, _PAD * 2, _PAD * 2)
        lay.setSpacing(_PAD)

        lbl = QLabel("SELECT RECIPE")
        lbl.setStyleSheet(f"font-size: {_F_BIG}px; font-weight: bold; color: {C.PRIMARY};")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl)

        self._combo_recipe = QComboBox()
        self._combo_recipe.setStyleSheet(
            f"QComboBox {{ background-color: {C.BG_INPUT}; color: {C.TEXT};"
            f"border: 1px solid {C.BORDER}; border-radius: 6px;"
            f"padding: 8px 12px; font-size: {_F_MED}px; min-height: 36px; }}"
            f"QComboBox QAbstractItemView {{ background-color: {C.BG_CARD}; color: {C.TEXT};"
            f"border: 1px solid {C.BORDER}; font-size: {_F_MED}px; }}"
        )
        lay.addWidget(self._combo_recipe)

        # User name
        row = QHBoxLayout()
        row.setSpacing(_GAP)
        lbl_user = QLabel("OPERATOR:")
        lbl_user.setStyleSheet(f"font-size: {_F_SM}px; color: {C.TEXT_SEC};")
        row.addWidget(lbl_user)
        self._input_user = QLineEdit()
        self._input_user.setPlaceholderText("Name (optional)")
        self._input_user.setStyleSheet(
            f"background-color: {C.BG_INPUT}; color: {C.TEXT};"
            f"border: 1px solid {C.BORDER}; border-radius: 6px;"
            f"padding: 6px 10px; font-size: {_F_MED}px; min-height: 32px;"
        )
        row.addWidget(self._input_user, stretch=1)
        lay.addLayout(row)

        lay.addStretch(1)

        btn_start = QPushButton("START MIXING")
        btn_start.setStyleSheet(
            f"background-color: {C.PRIMARY}; color: {C.BG_DARK};"
            f"border: none; border-radius: 8px; font-size: {F.H3}px;"
            f"font-weight: bold; min-height: 56px;"
        )
        btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_start.clicked.connect(self._on_start)
        lay.addWidget(btn_start)

        return page

    def _build_recipe_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(_PAD * 2, _PAD, _PAD * 2, _PAD)
        lay.setSpacing(_PAD)

        self._lbl_recipe_name = QLabel("Recipe")
        self._lbl_recipe_name.setStyleSheet(
            f"font-size: {_F_BIG}px; font-weight: bold; color: {C.PRIMARY};"
        )
        self._lbl_recipe_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._lbl_recipe_name)

        # Recipe info card
        card = QFrame()
        card.setObjectName("card")
        card_lay = QGridLayout(card)
        card_lay.setContentsMargins(_PAD, _PAD, _PAD, _PAD)
        card_lay.setSpacing(_GAP)

        self._lbl_ratio = QLabel("Ratio: --")
        self._lbl_ratio.setStyleSheet(f"font-size: {_F_MED}px; color: {C.TEXT};")
        card_lay.addWidget(self._lbl_ratio, 0, 0)

        self._lbl_potlife_info = QLabel("Pot life: --")
        self._lbl_potlife_info.setStyleSheet(f"font-size: {_F_MED}px; color: {C.TEXT};")
        card_lay.addWidget(self._lbl_potlife_info, 0, 1)

        self._lbl_tolerance = QLabel("Tolerance: --")
        self._lbl_tolerance.setStyleSheet(f"font-size: {_F_MED}px; color: {C.TEXT_SEC};")
        card_lay.addWidget(self._lbl_tolerance, 1, 0)

        lay.addWidget(card)

        # Amount input
        lbl_amount = QLabel("BASE AMOUNT (kg)")
        lbl_amount.setStyleSheet(f"font-size: {_F_SM}px; font-weight: bold; color: {C.SECONDARY};")
        lay.addWidget(lbl_amount)

        amount_row = QHBoxLayout()
        amount_row.setSpacing(_GAP)
        self._input_amount = QLineEdit()
        self._input_amount.setPlaceholderText("e.g. 500")
        self._input_amount.setStyleSheet(
            f"background-color: {C.BG_INPUT}; color: {C.TEXT};"
            f"border: 1px solid {C.BORDER}; border-radius: 6px;"
            f"padding: 8px 12px; font-size: {_F_BIG}px; min-height: 40px;"
        )
        amount_row.addWidget(self._input_amount, stretch=1)

        for preset in ["250", "500", "1000", "2000"]:
            btn = QPushButton(f"{preset}g")
            btn.setStyleSheet(
                f"background-color: {C.BG_CARD}; color: {C.TEXT_SEC};"
                f"border: 1px solid {C.BORDER}; border-radius: 4px;"
                f"padding: 4px 8px; font-size: {_F_SM}px; min-height: 32px;"
            )
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, v=preset: self._input_amount.setText(v))
            amount_row.addWidget(btn)
        lay.addLayout(amount_row)

        # Calculated values
        self._lbl_calc_base = QLabel("")
        self._lbl_calc_base.setStyleSheet(f"font-size: {_F_MED}px; color: {C.TEXT};")
        lay.addWidget(self._lbl_calc_base)

        self._lbl_calc_hardener = QLabel("")
        self._lbl_calc_hardener.setStyleSheet(f"font-size: {_F_MED}px; color: {C.ACCENT};")
        lay.addWidget(self._lbl_calc_hardener)

        lay.addStretch(1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(_GAP)

        btn_cancel = QPushButton("CANCEL")
        btn_cancel.setObjectName("danger")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setMinimumHeight(44)
        btn_cancel.clicked.connect(self._on_abort)
        btn_row.addWidget(btn_cancel)

        btn_next = QPushButton("TARE & START POURING")
        btn_next.setStyleSheet(
            f"background-color: {C.PRIMARY}; color: {C.BG_DARK};"
            f"border: none; border-radius: 8px; font-size: {_F_MED}px;"
            f"font-weight: bold; min-height: 44px;"
        )
        btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_next.clicked.connect(self._on_tare_and_pour)
        btn_row.addWidget(btn_next, stretch=1)

        lay.addLayout(btn_row)

        return page

    def _build_weigh_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(_PAD * 2, _PAD, _PAD * 2, _PAD)
        lay.setSpacing(_PAD)

        self._lbl_pour_title = QLabel("POUR BASE")
        self._lbl_pour_title.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.PRIMARY};"
        )
        self._lbl_pour_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._lbl_pour_title)

        # Weight display - large
        weight_card = QFrame()
        weight_card.setObjectName("card")
        wc_lay = QVBoxLayout(weight_card)
        wc_lay.setContentsMargins(_PAD, _PAD, _PAD, _PAD)
        wc_lay.setSpacing(4)

        self._lbl_weight_current = QLabel("0.00 kg")
        self._lbl_weight_current.setStyleSheet(
            f"font-size: 48px; font-weight: bold; color: {C.PRIMARY};"
        )
        self._lbl_weight_current.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wc_lay.addWidget(self._lbl_weight_current)

        self._lbl_weight_target = QLabel("Target: --- kg")
        self._lbl_weight_target.setStyleSheet(
            f"font-size: {_F_MED}px; color: {C.TEXT_SEC};"
        )
        self._lbl_weight_target.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wc_lay.addWidget(self._lbl_weight_target)

        # Progress bar
        self._progress_weight = QProgressBar()
        self._progress_weight.setRange(0, 100)
        self._progress_weight.setValue(0)
        self._progress_weight.setStyleSheet(
            f"QProgressBar {{ background-color: {C.BG_INPUT}; border: none;"
            f"border-radius: 6px; min-height: 16px; max-height: 16px; }}"
            f"QProgressBar::chunk {{ background-color: {C.PRIMARY}; border-radius: 6px; }}"
        )
        wc_lay.addWidget(self._progress_weight)

        self._lbl_weight_zone = QLabel("Start pouring...")
        self._lbl_weight_zone.setStyleSheet(
            f"font-size: {_F_SM}px; color: {C.TEXT_MUTED};"
        )
        self._lbl_weight_zone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wc_lay.addWidget(self._lbl_weight_zone)

        # Barcode verification banner (hidden until scan)
        self._barcode_banner = QFrame()
        self._barcode_banner.setVisible(False)
        bb_lay = QHBoxLayout(self._barcode_banner)
        bb_lay.setContentsMargins(8, 6, 8, 6)
        bb_lay.setSpacing(6)
        self._barcode_icon = QLabel()
        self._barcode_icon.setFixedWidth(24)
        self._barcode_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bb_lay.addWidget(self._barcode_icon)
        self._barcode_msg = QLabel("")
        self._barcode_msg.setStyleSheet(f"font-size: {_F_SM}px; font-weight: bold;")
        bb_lay.addWidget(self._barcode_msg, stretch=1)
        wc_lay.addWidget(self._barcode_banner)

        # RFID hint when RFID is down
        rfid_status = getattr(self, '_app_rfid_ok', True)
        self._lbl_rfid_hint = QLabel("RFID unavailable — scan barcode to verify product")
        self._lbl_rfid_hint.setStyleSheet(
            f"font-size: {_F_SM}px; color: {C.WARNING}; font-style: italic;"
        )
        self._lbl_rfid_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_rfid_hint.setVisible(False)
        wc_lay.addWidget(self._lbl_rfid_hint)

        lay.addWidget(weight_card, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(_GAP)

        btn_abort = QPushButton("ABORT")
        btn_abort.setObjectName("danger")
        btn_abort.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_abort.setMinimumHeight(44)
        btn_abort.clicked.connect(self._on_abort)
        btn_row.addWidget(btn_abort)

        self._btn_confirm_pour = QPushButton("CONFIRM POUR")
        self._btn_confirm_pour.setStyleSheet(
            f"background-color: {C.SUCCESS}; color: {C.BG_DARK};"
            f"border: none; border-radius: 8px; font-size: {_F_MED}px;"
            f"font-weight: bold; min-height: 44px;"
        )
        self._btn_confirm_pour.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_confirm_pour.clicked.connect(self._on_confirm_pour)
        btn_row.addWidget(self._btn_confirm_pour, stretch=1)

        lay.addLayout(btn_row)

        return page

    def _build_confirm_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(_PAD * 2, _PAD * 2, _PAD * 2, _PAD)
        lay.setSpacing(_PAD)

        lbl = QLabel("MIX RESULT")
        lbl.setStyleSheet(f"font-size: {_F_BIG}px; font-weight: bold; color: {C.PRIMARY};")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl)

        card = QFrame()
        card.setObjectName("card")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(_PAD, _PAD, _PAD, _PAD)
        card_lay.setSpacing(_GAP)

        self._lbl_result_base = QLabel("Base: ---")
        self._lbl_result_base.setStyleSheet(f"font-size: {_F_MED}px; color: {C.TEXT};")
        card_lay.addWidget(self._lbl_result_base)

        self._lbl_result_hardener = QLabel("Hardener: ---")
        self._lbl_result_hardener.setStyleSheet(f"font-size: {_F_MED}px; color: {C.TEXT};")
        card_lay.addWidget(self._lbl_result_hardener)

        self._lbl_result_ratio = QLabel("Ratio: ---")
        self._lbl_result_ratio.setStyleSheet(f"font-size: {_F_BIG}px; font-weight: bold; color: {C.SUCCESS};")
        self._lbl_result_ratio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(self._lbl_result_ratio)

        self._lbl_result_spec = QLabel("")
        self._lbl_result_spec.setStyleSheet(f"font-size: {_F_MED}px; font-weight: bold;")
        self._lbl_result_spec.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(self._lbl_result_spec)

        lay.addWidget(card)
        lay.addStretch(1)

        btn = QPushButton("CONFIRM MIX")
        btn.setStyleSheet(
            f"background-color: {C.SUCCESS}; color: {C.BG_DARK};"
            f"border: none; border-radius: 8px; font-size: {F.H3}px;"
            f"font-weight: bold; min-height: 56px;"
        )
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self._on_confirm_mix)
        lay.addWidget(btn)

        return page

    def _build_thinner_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(_PAD * 2, _PAD * 2, _PAD * 2, _PAD)
        lay.setSpacing(_PAD)

        lbl = QLabel("ADD THINNER?")
        lbl.setStyleSheet(f"font-size: {_F_BIG}px; font-weight: bold; color: {C.PRIMARY};")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl)

        lbl2 = QLabel("Select application method:")
        lbl2.setStyleSheet(f"font-size: {_F_MED}px; color: {C.TEXT_SEC};")
        lbl2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl2)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(_PAD)

        for method, label in [("brush", "BRUSH"), ("roller", "ROLLER"), ("spray", "SPRAY")]:
            btn = QPushButton(label)
            btn.setStyleSheet(
                f"background-color: {C.BG_CARD}; color: {C.TEXT};"
                f"border: 1px solid {C.BORDER}; border-radius: 8px;"
                f"font-size: {_F_MED}px; font-weight: bold; min-height: 56px;"
            )
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, m=method: self._on_thinner(m))
            btn_row.addWidget(btn)
        lay.addLayout(btn_row)

        lay.addStretch(1)

        btn_skip = QPushButton("SKIP - NO THINNER")
        btn_skip.setObjectName("secondary")
        btn_skip.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_skip.setMinimumHeight(48)
        btn_skip.clicked.connect(self._on_skip_thinner)
        lay.addWidget(btn_skip)

        return page

    def _build_potlife_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(_PAD * 2, _PAD, _PAD * 2, _PAD)
        lay.setSpacing(_PAD)

        lbl = QLabel("POT LIFE ACTIVE")
        lbl.setStyleSheet(f"font-size: {F.H3}px; font-weight: bold; color: {C.SUCCESS};")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl)

        self._lbl_potlife_remaining = QLabel("--:--:--")
        self._lbl_potlife_remaining.setStyleSheet(
            f"font-size: 52px; font-weight: bold; color: {C.PRIMARY};"
        )
        self._lbl_potlife_remaining.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._lbl_potlife_remaining)

        self._progress_potlife = QProgressBar()
        self._progress_potlife.setRange(0, 100)
        self._progress_potlife.setValue(0)
        self._progress_potlife.setStyleSheet(
            f"QProgressBar {{ background-color: {C.BG_INPUT}; border: none;"
            f"border-radius: 6px; min-height: 12px; max-height: 12px; }}"
            f"QProgressBar::chunk {{ background-color: {C.SUCCESS}; border-radius: 6px; }}"
        )
        lay.addWidget(self._progress_potlife)

        self._lbl_potlife_status = QLabel("Mix is usable")
        self._lbl_potlife_status.setStyleSheet(f"font-size: {_F_MED}px; color: {C.TEXT_SEC};")
        self._lbl_potlife_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._lbl_potlife_status)

        lay.addStretch(1)

        btn = QPushButton("DONE - COMPLETE SESSION")
        btn.setStyleSheet(
            f"background-color: {C.PRIMARY}; color: {C.BG_DARK};"
            f"border: none; border-radius: 8px; font-size: {_F_MED}px;"
            f"font-weight: bold; min-height: 48px;"
        )
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self._on_complete)
        lay.addWidget(btn)

        return page

    def _build_complete_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(_PAD * 2, _PAD * 2, _PAD * 2, _PAD * 2)
        lay.setSpacing(_PAD)

        lbl = QLabel("SESSION COMPLETE")
        lbl.setStyleSheet(f"font-size: {_F_BIG}px; font-weight: bold; color: {C.SUCCESS};")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl)

        self._lbl_summary = QLabel("")
        self._lbl_summary.setStyleSheet(f"font-size: {_F_MED}px; color: {C.TEXT};")
        self._lbl_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_summary.setWordWrap(True)
        lay.addWidget(self._lbl_summary)

        lay.addStretch(1)

        btn = QPushButton("BACK TO HOME")
        btn.setStyleSheet(
            f"background-color: {C.PRIMARY}; color: {C.BG_DARK};"
            f"border: none; border-radius: 8px; font-size: {F.H3}px;"
            f"font-weight: bold; min-height: 56px;"
        )
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self.app.go_screen("home"))
        lay.addWidget(btn)

        return page

    # ══════════════════════════════════════════════════════
    # LIFECYCLE
    # ══════════════════════════════════════════════════════

    def on_enter(self):
        self._load_recipes()
        self._stack.setCurrentIndex(0)
        self._state_badge.setText("IDLE")
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

        from core.models import MixingRecipe
        mr = MixingRecipe(
            recipe_id=recipe_id,
            name=recipe_name,
            base_product_id=pending.get("product_name", ""),
            hardener_product_id=pending.get("hardener_name", ""),
            ratio_base=ratio_base,
            ratio_hardener=ratio_hardener,
            tolerance_pct=tolerance,
            pot_life_minutes=pot_life,
        )

        # Load recipe and start session
        self.app.mixing_engine.load_recipes({recipe_id: mr})
        self.app.mixing_engine.start_session(recipe_id, user_name="Crew")

        # Set amounts via engine
        self.app.mixing_engine.show_recipe(base_grams)

        # Tare the mixing scale
        self.app.mixing_engine.tare_scale()

        # Skip to weighing (bypass recipe selection + amount entry pages)
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

        # Track barcode verification state
        self._barcode_verified_base = False
        self._barcode_verified_hardener = False

        # Jump directly to weigh page (page 2)
        self._stack.setCurrentIndex(2)
        self._state_badge.setText("WEIGHING BASE")
        self._barcode_banner.setVisible(False)

        # If RFID is down, require barcode scan before pouring
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
        self._lbl_ratio.setText(f"Ratio: {ratio_base}:{ratio_hardener}")
        self._lbl_potlife_info.setText(f"Pot life: {pot_life} min")
        self._lbl_tolerance.setText(f"Tolerance: +/-{tolerance}%")
        self._input_amount.clear()
        self._lbl_calc_base.setText("")
        self._lbl_calc_hardener.setText("")

        self._current_recipe = mr
        self._stack.setCurrentIndex(1)
        self._state_badge.setText("SELECT AMOUNT")

        # Connect amount changes
        self._input_amount.textChanged.connect(self._on_amount_changed)

    def _on_amount_changed(self, text):
        try:
            base_g = float(text)
            hardener_g = base_g * (self._current_recipe.ratio_hardener / self._current_recipe.ratio_base)
            self._lbl_calc_base.setText(f"Base: {base_g / 1000:.2f} kg")
            self._lbl_calc_hardener.setText(f"Hardener: {hardener_g / 1000:.2f} kg")
        except (ValueError, AttributeError):
            self._lbl_calc_base.setText("")
            self._lbl_calc_hardener.setText("")

    def _is_rfid_down(self) -> bool:
        """Check if RFID is unavailable (fake driver or unhealthy)."""
        try:
            # Check driver_status FIRST — fake driver means no real RFID
            driver_status = getattr(self.app, "driver_status", {})
            rfid_drv = driver_status.get("rfid", "unknown")
            if rfid_drv == "fake":
                logger.info("[MIXING] RFID down: driver_status=fake")
                return True
            # Then check actual hardware health
            rfid = getattr(self.app, "rfid", None)
            if rfid and hasattr(rfid, "is_healthy"):
                healthy = rfid.is_healthy()
                logger.info(f"[MIXING] RFID check: driver={rfid_drv}, is_healthy={healthy}")
                return not healthy
            logger.info(f"[MIXING] RFID down: no driver or no is_healthy method")
            return True  # No RFID driver at all
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

        # Tare the mixing scale
        engine.tare_scale()

        # Skip pick phases, go straight to weighing
        session = engine.session
        if session:
            session.state = MixingState.WEIGH_BASE

        # Track barcode verification state
        self._barcode_verified_base = False
        self._barcode_verified_hardener = False

        self._weighing_phase = "base"
        self._weight_target = base_g
        self._lbl_pour_title.setText("POUR BASE")
        self._lbl_weight_target.setText(f"Target: {base_g / 1000:.2f} kg")
        self._lbl_weight_current.setText("0.00 kg")
        self._progress_weight.setValue(0)

        self._stack.setCurrentIndex(2)
        self._state_badge.setText("WEIGHING BASE")
        self._barcode_banner.setVisible(False)

        # If RFID is down, require barcode scan before pouring
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
        self._barcode_icon.setText(">>")
        self._barcode_icon.setStyleSheet(
            f"color: {C.ACCENT}; font-weight: bold; font-size: {_F_MED}px;"
        )
        self._barcode_msg.setText(
            f"SCAN {component} BARCODE TO START POURING"
        )
        self._barcode_msg.setStyleSheet(
            f"font-size: {_F_SM}px; font-weight: bold; color: {C.ACCENT};"
        )
        self._lbl_weight_zone.setText(f"Scan {component.lower()} barcode...")
        self._lbl_rfid_hint.setVisible(True)

    def _update_weight(self):
        # Read weight in try/except with logging
        current = 0.0
        try:
            status = self.app.mixing_engine.check_weight_target()
            if status:
                current = status["current_g"]
            else:
                # Fallback: read scale directly
                reading = self.app.weight.read_weight("mixing_scale")
                current = reading.grams
        except Exception as e:
            logger.error(f"Weight read error: {e}")
            return

        self._lbl_weight_current.setText(f"{current / 1000:.2f} kg")

        progress = (current / self._weight_target * 100) if self._weight_target > 0 else 0
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
            zone_text = "Slow down!"
        elif progress <= 100:
            zone = "in_range"
            color = C.SUCCESS
            zone_text = "STOP! Confirm pour"
        else:
            zone = "over"
            color = C.DANGER
            zone_text = "TOO MUCH!"

        # ── Buzzer feedback (audio guide for blind pouring) ──
        # Timer runs every 300ms. Beep frequencies:
        #   Pouring (<85%):     every 2 ticks = ~0.6s
        #   Approaching (85-98%): every tick = ~0.3s
        #   Target (98-100%):   continuous tone
        #   Over (>100%):       error buzz once
        try:
            buzzer = self.app.buzzer
            self._tick_counter += 1

            if zone == "pouring" and current > 5:
                # Steady beep every ~0.6s while pouring
                if self._tick_counter % 2 == 0:
                    buzzer.play(BuzzerPattern.POUR_STEADY)
            elif zone == "approaching":
                # Fast beep every tick (~0.3s) when close
                buzzer.play(BuzzerPattern.POUR_CLOSE)
            elif zone == "in_range":
                # Continuous tone at target — play sustained beep
                if self._tick_counter % 2 == 0:
                    buzzer.play(BuzzerPattern.POUR_TARGET)
            elif zone == "over":
                # Error once when entering over zone
                if self._last_buzzer_zone != "over":
                    buzzer.play(BuzzerPattern.ERROR)

            self._last_buzzer_zone = zone
        except Exception:
            pass  # Buzzer errors should never break weight display

        self._lbl_weight_current.setStyleSheet(
            f"font-size: 48px; font-weight: bold; color: {color};"
        )
        self._lbl_weight_zone.setText(zone_text)

        # Update progress bar color
        self._progress_weight.setStyleSheet(
            f"QProgressBar {{ background-color: {C.BG_INPUT}; border: none;"
            f"border-radius: 6px; min-height: 16px; max-height: 16px; }}"
            f"QProgressBar::chunk {{ background-color: {color}; border-radius: 6px; }}"
        )

    def _on_confirm_pour(self):
        self._weight_timer.stop()
        engine = self.app.mixing_engine

        if self._weighing_phase == "base":
            engine.confirm_base_weighed()

            # Move to hardener
            session = engine.session
            if session:
                session.state = MixingState.WEIGH_HARDENER
                hardener_target = session.hardener_weight_target_g

                self._weighing_phase = "hardener"
                self._weight_target = session.base_weight_actual_g + hardener_target
                self._last_buzzer_zone = ""
                self._tick_counter = 0
                self._lbl_pour_title.setText("POUR HARDENER")
                self._lbl_weight_target.setText(
                    f"Target: +{hardener_target / 1000:.2f} kg (total {self._weight_target / 1000:.2f} kg)"
                )
                self._lbl_weight_current.setText(f"{session.base_weight_actual_g / 1000:.2f} kg")
                self._progress_weight.setValue(0)
                self._lbl_weight_zone.setText("Pour hardener...")

                self._state_badge.setText("WEIGHING HARDENER")
                self._barcode_banner.setVisible(False)

                # If RFID is down, require barcode scan for hardener too
                if self._is_rfid_down():
                    self._show_barcode_required("HARDENER")
                else:
                    self._weight_timer.start(300)

        elif self._weighing_phase == "hardener":
            engine.confirm_hardener_weighed()

            session = engine.session
            if session:
                # Show confirm page
                self._lbl_result_base.setText(
                    f"Base: {session.base_weight_actual_g:.0f}g (target: {session.base_weight_target_g:.0f}g)"
                )
                self._lbl_result_hardener.setText(
                    f"Hardener: {session.hardener_weight_actual_g:.0f}g (target: {session.hardener_weight_target_g:.0f}g)"
                )
                self._lbl_result_ratio.setText(f"Ratio: {session.ratio_achieved:.2f}")

                if session.ratio_in_spec:
                    self._lbl_result_spec.setText("IN SPEC")
                    self._lbl_result_spec.setStyleSheet(
                        f"font-size: {_F_MED}px; font-weight: bold; color: {C.SUCCESS};"
                    )
                    self._lbl_result_ratio.setStyleSheet(
                        f"font-size: {_F_BIG}px; font-weight: bold; color: {C.SUCCESS};"
                    )
                else:
                    self._lbl_result_spec.setText("OUT OF SPEC!")
                    self._lbl_result_spec.setStyleSheet(
                        f"font-size: {_F_MED}px; font-weight: bold; color: {C.DANGER};"
                    )
                    self._lbl_result_ratio.setStyleSheet(
                        f"font-size: {_F_BIG}px; font-weight: bold; color: {C.DANGER};"
                    )

                self._stack.setCurrentIndex(3)
                self._state_badge.setText("CONFIRM MIX")

    def _on_confirm_mix(self):
        self.app.mixing_engine.confirm_mix()
        self._stack.setCurrentIndex(4)
        self._state_badge.setText("THINNER")

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
        self._state_badge.setText("POT LIFE")
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

        self._progress_potlife.setValue(int(100 - elapsed_pct))

        if status["expired"]:
            self._lbl_potlife_remaining.setStyleSheet(
                f"font-size: 52px; font-weight: bold; color: {C.DANGER};"
            )
            self._lbl_potlife_status.setText("EXPIRED! Discard the mix!")
            self._lbl_potlife_status.setStyleSheet(f"font-size: {_F_MED}px; color: {C.DANGER};")
            self._progress_potlife.setStyleSheet(
                f"QProgressBar {{ background-color: {C.BG_INPUT}; border: none;"
                f"border-radius: 6px; min-height: 12px; max-height: 12px; }}"
                f"QProgressBar::chunk {{ background-color: {C.DANGER}; border-radius: 6px; }}"
            )
        elif elapsed_pct >= 75:
            self._lbl_potlife_remaining.setStyleSheet(
                f"font-size: 52px; font-weight: bold; color: {C.WARNING};"
            )
            self._lbl_potlife_status.setText("Use soon!")
            self._progress_potlife.setStyleSheet(
                f"QProgressBar {{ background-color: {C.BG_INPUT}; border: none;"
                f"border-radius: 6px; min-height: 12px; max-height: 12px; }}"
                f"QProgressBar::chunk {{ background-color: {C.WARNING}; border-radius: 6px; }}"
            )
        else:
            self._lbl_potlife_remaining.setStyleSheet(
                f"font-size: 52px; font-weight: bold; color: {C.PRIMARY};"
            )
            self._lbl_potlife_status.setText("Mix is usable")

    def _on_complete(self):
        self._pot_life_timer.stop()

        session = self.app.mixing_engine.session
        if session:
            summary = (
                f"Base: {session.base_weight_actual_g:.0f}g | "
                f"Hardener: {session.hardener_weight_actual_g:.0f}g\n"
                f"Ratio: {session.ratio_achieved:.2f} | "
                f"{'IN SPEC' if session.ratio_in_spec else 'OUT OF SPEC'}"
            )
            self._lbl_summary.setText(summary)

        self.app.mixing_engine.complete_session()
        self._stack.setCurrentIndex(6)
        self._state_badge.setText("COMPLETE")

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

    def on_barcode_verified(self, match: bool, component: str, product_info: dict):
        """Called by app when barcode is scanned during mixing.

        Shows a banner on the weigh page indicating match/mismatch.
        If RFID is down and barcode matches, unlocks weighing.
        """
        name = product_info.get("product_name", "Unknown")
        self._barcode_banner.setVisible(True)

        if match:
            self._barcode_banner.setStyleSheet(
                f"background-color: {C.SUCCESS_BG}; border: 1px solid {C.SUCCESS};"
                f"border-radius: 6px;"
            )
            self._barcode_icon.setText("OK")
            self._barcode_icon.setStyleSheet(
                f"color: {C.SUCCESS}; font-weight: bold; font-size: {_F_MED}px;"
            )
            self._barcode_msg.setText(f"CORRECT {component}: {name}")
            self._barcode_msg.setStyleSheet(
                f"font-size: {_F_SM}px; font-weight: bold; color: {C.SUCCESS};"
            )

            # Unlock weighing if barcode was required (RFID down)
            if component == "BASE" and not self._barcode_verified_base:
                self._barcode_verified_base = True
                self._lbl_rfid_hint.setVisible(False)
                self._weight_timer.start(300)  # Start weighing
                QTimer.singleShot(3000, lambda: self._barcode_banner.setVisible(False))
                return
            elif component == "HARDENER" and not self._barcode_verified_hardener:
                self._barcode_verified_hardener = True
                self._lbl_rfid_hint.setVisible(False)
                self._weight_timer.start(300)  # Resume weighing
                QTimer.singleShot(3000, lambda: self._barcode_banner.setVisible(False))
                return
        else:
            self._barcode_banner.setStyleSheet(
                f"background-color: {C.DANGER_BG}; border: 2px solid {C.DANGER};"
                f"border-radius: 6px;"
            )
            self._barcode_icon.setText("!!")
            self._barcode_icon.setStyleSheet(
                f"color: {C.DANGER}; font-weight: bold; font-size: {_F_MED}px;"
            )
            self._barcode_msg.setText(f"WRONG PRODUCT! Scanned: {name}")
            self._barcode_msg.setStyleSheet(
                f"font-size: {_F_SM}px; font-weight: bold; color: {C.DANGER};"
            )

        # Auto-hide after 8 seconds
        QTimer.singleShot(8000, lambda: self._barcode_banner.setVisible(False))

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
