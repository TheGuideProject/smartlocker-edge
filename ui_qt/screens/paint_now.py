"""
SmartLocker Paint Now Screen

4-step wizard: SELECT_AREA -> VIEW_LAYERS -> ENTER_M2 -> SHOW_QUANTITIES
Guides the user through selecting an area, viewing its paint layers,
entering surface area, and seeing calculated paint quantities.
"""

import logging
from enum import Enum, auto

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QLineEdit, QSizePolicy, QGridLayout,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDoubleValidator

from ui_qt.theme import C, F, S

logger = logging.getLogger("smartlocker.ui.paint_now")


class WizardStep(Enum):
    SELECT_AREA = auto()
    VIEW_LAYERS = auto()
    ENTER_M2 = auto()
    SHOW_QUANTITIES = auto()


STEP_LABELS = {
    WizardStep.SELECT_AREA: "Select Area",
    WizardStep.VIEW_LAYERS: "View Layers",
    WizardStep.ENTER_M2: "Enter Surface",
    WizardStep.SHOW_QUANTITIES: "Quantities",
}

DEFAULT_COVERAGE = 8.0  # liters per m2 default


class PaintNowScreen(QWidget):
    """4-step paint calculation wizard."""

    def __init__(self, app):
        super().__init__()
        self.app = app

        self._step = WizardStep.SELECT_AREA
        self._selected_area = None       # dict from chart
        self._selected_area_idx = -1
        self._selected_layer = None      # dict from area layers
        self._m2_value = 0.0
        self._quantities = []

        self._build_ui()

    # ══════════════════════════════════════════════════════════
    # UI BUILD
    # ══════════════════════════════════════════════════════════

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ──────────────────────────────────────
        header = QFrame()
        header.setStyleSheet(
            f"background-color: {C.BG_STATUS};"
            f"border-bottom: 1px solid {C.BORDER};"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(S.PAD, 8, S.PAD, 8)
        h_layout.setSpacing(S.GAP)

        self._btn_back = QPushButton("< BACK")
        self._btn_back.setObjectName("ghost")
        self._btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_back.clicked.connect(self._go_back)
        h_layout.addWidget(self._btn_back)

        self._title_label = QLabel("PAINT NOW")
        self._title_label.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.TEXT};"
        )
        h_layout.addWidget(self._title_label)

        h_layout.addStretch(1)

        self._step_label = QLabel("Step 1/4")
        self._step_label.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.TEXT_SEC};"
        )
        h_layout.addWidget(self._step_label)

        root.addWidget(header)

        # ── Step indicator dots ─────────────────────────
        dot_bar = QFrame()
        dot_bar.setStyleSheet(f"background-color: {C.BG_DARK};")
        dot_layout = QHBoxLayout(dot_bar)
        dot_layout.setContentsMargins(S.PAD, 6, S.PAD, 6)
        dot_layout.setSpacing(8)
        dot_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._dots = []
        for i in range(4):
            dot = QLabel("o")
            dot.setFixedWidth(24)
            dot.setFixedHeight(24)
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot_layout.addWidget(dot)
            self._dots.append(dot)

        root.addWidget(dot_bar)

        # ── Body scroll area ───────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self._body_widget = QWidget()
        self._body_layout = QVBoxLayout(self._body_widget)
        self._body_layout.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
        self._body_layout.setSpacing(S.GAP)

        scroll.setWidget(self._body_widget)
        root.addWidget(scroll, stretch=1)

    # ══════════════════════════════════════════════════════════
    # STEP NAVIGATION
    # ══════════════════════════════════════════════════════════

    def _set_step(self, step: WizardStep):
        self._step = step
        step_num = list(WizardStep).index(step) + 1
        self._step_label.setText(f"Step {step_num}/4")

        # Update dots
        for i, dot in enumerate(self._dots):
            if i < step_num:
                dot.setStyleSheet(
                    f"background-color: {C.PRIMARY}; color: {C.BG_DARK};"
                    f"border-radius: 12px; font-weight: bold;"
                    f"font-size: {F.TINY}px;"
                )
                dot.setText(str(i + 1))
            else:
                dot.setStyleSheet(
                    f"background-color: {C.BG_CARD}; color: {C.TEXT_MUTED};"
                    f"border-radius: 12px; border: 1px solid {C.BORDER};"
                    f"font-size: {F.TINY}px;"
                )
                dot.setText(str(i + 1))

        self._rebuild_body()

    def _go_back(self):
        steps = list(WizardStep)
        idx = steps.index(self._step)
        if idx > 0:
            self._set_step(steps[idx - 1])
        else:
            self.app.go_back()

    # ══════════════════════════════════════════════════════════
    # BODY REBUILD
    # ══════════════════════════════════════════════════════════

    def _clear_body(self):
        while self._body_layout.count():
            item = self._body_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _rebuild_body(self):
        self._clear_body()

        if self._step == WizardStep.SELECT_AREA:
            self._build_step_select_area()
        elif self._step == WizardStep.VIEW_LAYERS:
            self._build_step_view_layers()
        elif self._step == WizardStep.ENTER_M2:
            self._build_step_enter_m2()
        elif self._step == WizardStep.SHOW_QUANTITIES:
            self._build_step_show_quantities()

    # ── Step 1: Select Area ─────────────────────────────

    def _build_step_select_area(self):
        chart = getattr(self.app, "maintenance_chart", None)

        lbl = QLabel("Select vessel area to paint:")
        lbl.setStyleSheet(
            f"font-size: {F.H3}px; color: {C.TEXT_SEC};"
        )
        self._body_layout.addWidget(lbl)

        if not chart or not chart.get("areas"):
            msg = QLabel(
                "No maintenance chart loaded.\n"
                "Pair with cloud to receive the vessel chart."
            )
            msg.setStyleSheet(f"font-size: {F.BODY}px; color: {C.TEXT_MUTED};")
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            msg.setWordWrap(True)
            self._body_layout.addWidget(msg)
            self._body_layout.addStretch(1)
            return

        areas = chart.get("areas", [])
        for i, area in enumerate(areas):
            btn = QPushButton(area.get("name", f"Area {i+1}"))
            btn.setObjectName("nav_tile")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(40)
            btn.setStyleSheet(
                f"QPushButton {{ font-size: {F.BODY}px; font-weight: bold;"
                f"text-align: left; padding-left: 16px;"
                f"border-left: 4px solid {C.SECONDARY}; }}"
            )
            idx = i  # capture
            btn.clicked.connect(lambda checked=False, a=idx: self._on_area_selected(a))
            self._body_layout.addWidget(btn)

        self._body_layout.addStretch(1)

    def _on_area_selected(self, area_idx: int):
        chart = getattr(self.app, "maintenance_chart", None)
        if not chart:
            return
        areas = chart.get("areas", [])
        if area_idx < len(areas):
            self._selected_area = areas[area_idx]
            self._selected_area_idx = area_idx
            self._set_step(WizardStep.VIEW_LAYERS)

    # ── Step 2: View Layers ─────────────────────────────

    def _build_step_view_layers(self):
        if not self._selected_area:
            self._set_step(WizardStep.SELECT_AREA)
            return

        area_name = self._selected_area.get("name", "Selected Area")
        lbl = QLabel(f"Layers for: {area_name}")
        lbl.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.TEXT};"
        )
        self._body_layout.addWidget(lbl)

        layers = self._selected_area.get("layers", [])
        if not layers:
            msg = QLabel("No layers defined for this area.")
            msg.setStyleSheet(f"font-size: {F.BODY}px; color: {C.TEXT_MUTED};")
            self._body_layout.addWidget(msg)
            self._body_layout.addStretch(1)
            return

        for i, layer in enumerate(layers):
            card = QFrame()
            card.setObjectName("card")
            c_layout = QHBoxLayout(card)
            c_layout.setContentsMargins(S.PAD_CARD, S.PAD_CARD, S.PAD_CARD, S.PAD_CARD)
            c_layout.setSpacing(S.GAP)

            # Layer number
            num = QLabel(f"L{i+1}")
            num.setStyleSheet(
                f"font-size: {F.H3}px; font-weight: bold; color: {C.SECONDARY};"
            )
            num.setFixedWidth(36)
            c_layout.addWidget(num)

            # Product name and color
            info_layout = QVBoxLayout()
            info_layout.setSpacing(2)

            product = layer.get("product_name", layer.get("product", "Unknown"))
            lbl_prod = QLabel(product)
            lbl_prod.setStyleSheet(
                f"font-size: {F.BODY}px; font-weight: bold; color: {C.TEXT};"
            )
            lbl_prod.setWordWrap(True)
            info_layout.addWidget(lbl_prod)

            color = layer.get("color", "")
            if color:
                lbl_color = QLabel(f"Color: {color}")
                lbl_color.setStyleSheet(
                    f"font-size: {F.SMALL}px; color: {C.TEXT_SEC};"
                )
                info_layout.addWidget(lbl_color)

            c_layout.addLayout(info_layout, stretch=1)

            # Select button
            btn = QPushButton("SELECT")
            btn.setObjectName("secondary")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedWidth(90)
            layer_idx = i
            btn.clicked.connect(
                lambda checked=False, li=layer_idx: self._on_layer_selected(li)
            )
            c_layout.addWidget(btn)

            self._body_layout.addWidget(card)

        self._body_layout.addStretch(1)

    def _on_layer_selected(self, layer_idx: int):
        layers = self._selected_area.get("layers", [])
        if layer_idx < len(layers):
            self._selected_layer = layers[layer_idx]
            self._set_step(WizardStep.ENTER_M2)

    # ── Step 3: Enter m2 ────────────────────────────────

    def _build_step_enter_m2(self):
        product = ""
        if self._selected_layer:
            product = self._selected_layer.get(
                "product_name", self._selected_layer.get("product", "")
            )

        lbl = QLabel(f"Enter surface area (m2) for: {product}")
        lbl.setStyleSheet(
            f"font-size: {F.H3}px; color: {C.TEXT};"
        )
        lbl.setWordWrap(True)
        self._body_layout.addWidget(lbl)

        # Input field
        self._m2_input = QLineEdit()
        self._m2_input.setPlaceholderText("Enter m2...")
        self._m2_input.setValidator(QDoubleValidator(0.1, 9999.0, 1))
        self._m2_input.setStyleSheet(
            f"font-size: {F.H3}px; padding: 8px; min-height: 36px;"
        )
        self._m2_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._body_layout.addWidget(self._m2_input)

        # Preset buttons row
        preset_label = QLabel("Quick presets:")
        preset_label.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.TEXT_SEC};"
        )
        self._body_layout.addWidget(preset_label)

        presets_row = QHBoxLayout()
        presets_row.setSpacing(S.GAP)

        for val in [10, 25, 50, 100]:
            btn = QPushButton(str(val))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(36)
            btn.setStyleSheet(
                f"font-size: {F.BODY}px; font-weight: bold;"
            )
            btn.clicked.connect(
                lambda checked=False, v=val: self._set_m2_preset(v)
            )
            presets_row.addWidget(btn)

        preset_wrapper = QWidget()
        preset_wrapper.setLayout(presets_row)
        self._body_layout.addWidget(preset_wrapper)

        self._body_layout.addStretch(1)

        # Calculate button
        btn_calc = QPushButton("CALCULATE")
        btn_calc.setObjectName("primary")
        btn_calc.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_calc.setMinimumHeight(44)
        btn_calc.clicked.connect(self._on_calculate)
        self._body_layout.addWidget(btn_calc)

    def _set_m2_preset(self, val: int):
        self._m2_input.setText(str(val))

    def _on_calculate(self):
        text = self._m2_input.text().strip()
        try:
            self._m2_value = float(text)
        except (ValueError, TypeError):
            self._m2_value = 0.0

        if self._m2_value <= 0:
            return

        self._calculate_quantities()
        self._set_step(WizardStep.SHOW_QUANTITIES)

    def _calculate_quantities(self):
        """Compute paint quantities for the selected layer and area."""
        self._quantities = []
        if not self._selected_layer:
            return

        product = self._selected_layer.get(
            "product_name", self._selected_layer.get("product", "Unknown")
        )

        # Try to find coverage from maintenance chart products
        coverage = DEFAULT_COVERAGE
        chart = getattr(self.app, "maintenance_chart", None)
        if chart:
            for p in chart.get("products", []):
                if p.get("name", "") == product:
                    coverage = p.get("coverage_m2_per_liter", DEFAULT_COVERAGE)
                    break

        if coverage <= 0:
            coverage = DEFAULT_COVERAGE

        liters_needed = self._m2_value / coverage

        self._quantities.append({
            "product": product,
            "type": "BASE",
            "liters": round(liters_needed, 2),
        })

        # Check for hardener ratio from chart
        if chart:
            for p in chart.get("products", []):
                if p.get("name", "") == product and p.get("is_bicomponent"):
                    ratio_base = p.get("ratio_base", 4.0)
                    ratio_hard = p.get("ratio_hardener", 1.0)
                    hardener_name = p.get("hardener_name", "Hardener")
                    hardener_liters = liters_needed * (ratio_hard / ratio_base)
                    self._quantities.append({
                        "product": hardener_name,
                        "type": "HARDENER",
                        "liters": round(hardener_liters, 2),
                    })
                    break

    # ── Step 4: Show Quantities ────────────────────────

    def _build_step_show_quantities(self):
        area_name = self._selected_area.get("name", "") if self._selected_area else ""

        lbl = QLabel(f"Paint required for {self._m2_value:.0f} m2 - {area_name}")
        lbl.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.TEXT};"
        )
        lbl.setWordWrap(True)
        self._body_layout.addWidget(lbl)

        if not self._quantities:
            msg = QLabel("No quantities calculated.")
            msg.setStyleSheet(f"font-size: {F.BODY}px; color: {C.TEXT_MUTED};")
            self._body_layout.addWidget(msg)
        else:
            for q in self._quantities:
                card = QFrame()
                card.setObjectName("card")
                c_layout = QHBoxLayout(card)
                c_layout.setContentsMargins(
                    S.PAD_CARD, S.PAD_CARD, S.PAD_CARD, S.PAD_CARD
                )
                c_layout.setSpacing(S.GAP)

                # Type badge
                ptype = q.get("type", "BASE")
                badge = QLabel(ptype)
                badge_map = {
                    "BASE": (C.PRIMARY_BG, C.PRIMARY, C.PRIMARY),
                    "HARDENER": (C.ACCENT_BG, C.ACCENT, C.ACCENT),
                    "THINNER": (C.SECONDARY_BG, C.SECONDARY, C.SECONDARY),
                }
                bg, fg, bd = badge_map.get(
                    ptype, (C.BG_CARD_ALT, C.TEXT_MUTED, C.TEXT_MUTED)
                )
                badge.setStyleSheet(
                    f"background-color: {bg}; color: {fg};"
                    f"border: 1px solid {bd}; border-radius: 4px;"
                    f"padding: 2px 8px; font-size: {F.TINY}px; font-weight: bold;"
                )
                badge.setFixedHeight(22)
                c_layout.addWidget(badge)

                # Product name
                lbl_name = QLabel(q.get("product", ""))
                lbl_name.setStyleSheet(
                    f"font-size: {F.BODY}px; color: {C.TEXT};"
                )
                lbl_name.setWordWrap(True)
                c_layout.addWidget(lbl_name, stretch=1)

                # Amount
                lbl_amt = QLabel(f"{q.get('liters', 0):.2f} L")
                lbl_amt.setStyleSheet(
                    f"font-size: {F.H3}px; font-weight: bold; color: {C.PRIMARY};"
                )
                c_layout.addWidget(lbl_amt)

                self._body_layout.addWidget(card)

        self._body_layout.addStretch(1)

        # Start Mixing button
        btn_mix = QPushButton("START MIXING")
        btn_mix.setObjectName("primary")
        btn_mix.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_mix.setMinimumHeight(44)
        btn_mix.clicked.connect(self._on_start_mixing)
        self._body_layout.addWidget(btn_mix)

    # ══════════════════════════════════════════════════════════
    # LIFECYCLE
    # ══════════════════════════════════════════════════════════

    def on_enter(self):
        self._step = WizardStep.SELECT_AREA
        self._selected_area = None
        self._selected_area_idx = -1
        self._selected_layer = None
        self._m2_value = 0.0
        self._quantities = []
        self._set_step(WizardStep.SELECT_AREA)

    def _on_start_mixing(self):
        """Pass calculated quantities to mixing screen automatically."""
        if not self._quantities:
            return

        # Convert liters to grams (paint density ~1.3 kg/L average)
        DENSITY_G_PER_L = 1300.0

        base_q = None
        hardener_q = None
        for q in self._quantities:
            if q.get("type") == "BASE":
                base_q = q
            elif q.get("type") == "HARDENER":
                hardener_q = q

        if not base_q:
            return

        base_grams = base_q["liters"] * DENSITY_G_PER_L

        # Find ratio info from chart
        product_name = base_q.get("product", "Unknown")
        ratio_base = 4.0
        ratio_hardener = 1.0
        pot_life = 480
        tolerance = 5.0
        hardener_name = "Hardener"

        chart = getattr(self.app, "maintenance_chart", None)
        if chart:
            for p in chart.get("products", []):
                if p.get("name", "") == product_name and p.get("is_bicomponent"):
                    ratio_base = p.get("ratio_base", 4.0)
                    ratio_hardener = p.get("ratio_hardener", 1.0)
                    pot_life = p.get("pot_life_minutes", 480)
                    tolerance = p.get("tolerance_pct", 5.0)
                    hardener_name = p.get("hardener_name", "Hardener")
                    break

        hardener_grams = base_grams * (ratio_hardener / ratio_base)

        # Store pending mix data on app for the mixing screen to pick up
        self.app.pending_mix = {
            "product_name": product_name,
            "hardener_name": hardener_name,
            "base_grams": round(base_grams, 0),
            "hardener_grams": round(hardener_grams, 0),
            "base_liters": base_q["liters"],
            "hardener_liters": hardener_q["liters"] if hardener_q else 0,
            "ratio_base": ratio_base,
            "ratio_hardener": ratio_hardener,
            "pot_life_minutes": pot_life,
            "tolerance_pct": tolerance,
            "area_name": self._selected_area.get("name", "") if self._selected_area else "",
            "m2": self._m2_value,
        }

        logger.info(
            f"PaintNow -> Mixing: {product_name} "
            f"base={base_grams:.0f}g hardener={hardener_grams:.0f}g "
            f"ratio={ratio_base}:{ratio_hardener}"
        )

        self.app.go_screen("mixing")

    def on_leave(self):
        pass
