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

from ui_qt.theme import C, F, S, enable_touch_scroll
from ui_qt.icons import (
    Icon, icon_badge, icon_label, status_dot, type_badge, section_header,
    screen_header,
)

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

STEP_ICONS = {
    WizardStep.SELECT_AREA: Icon.CHART,
    WizardStep.VIEW_LAYERS: Icon.SHELF,
    WizardStep.ENTER_M2: Icon.EDIT,
    WizardStep.SHOW_QUANTITIES: Icon.WEIGHT,
}

DEFAULT_COVERAGE = 8.0  # liters per m2 default


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
# PAINT NOW SCREEN
# ═════════════════════════════════════════════════════════

class PaintNowScreen(QWidget):
    """4-step paint calculation wizard."""

    def __init__(self, app):
        super().__init__()
        self.app = app

        self._step = WizardStep.SELECT_AREA
        self._selected_area = None
        self._selected_area_idx = -1
        self._selected_layer = None
        self._m2_value = 0.0
        self._quantities = []

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
            self.app, "PAINT NOW", Icon.MIXING, C.PRIMARY
        )

        # Step badge in header
        self._step_badge = type_badge("Step 1/4", "muted")
        h_layout.addWidget(self._step_badge)

        root.addWidget(header)

        # ── Step indicator: 4 connected circles ──
        self._step_bar = QFrame()
        self._step_bar.setStyleSheet(
            f"background-color: {C.BG_STATUS};"
            f"border-bottom: 1px solid {C.BORDER};"
        )
        self._step_bar.setFixedHeight(52)

        step_layout = QHBoxLayout(self._step_bar)
        step_layout.setContentsMargins(S.PAD * 2, 6, S.PAD * 2, 6)
        step_layout.setSpacing(0)
        step_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._step_circles = []
        self._step_lines = []
        self._step_labels_ui = []

        steps = list(WizardStep)
        for i, ws in enumerate(steps):
            if i > 0:
                # Connecting line
                line = QFrame()
                line.setFixedHeight(2)
                line.setMinimumWidth(40)
                line.setSizePolicy(
                    QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
                )
                line.setStyleSheet(f"background-color: {C.BORDER};")
                step_layout.addWidget(line)
                self._step_lines.append(line)

            # Circle + label column
            col = QVBoxLayout()
            col.setSpacing(2)
            col.setAlignment(Qt.AlignmentFlag.AlignCenter)

            circle = QLabel(str(i + 1))
            circle.setFixedSize(28, 28)
            circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
            circle.setStyleSheet(
                f"background-color: {C.BG_CARD}; color: {C.TEXT_MUTED};"
                f"border-radius: 14px; border: 2px solid {C.BORDER};"
                f"font-size: {F.TINY}px; font-weight: bold;"
            )
            col.addWidget(circle, alignment=Qt.AlignmentFlag.AlignCenter)

            lbl = QLabel(STEP_LABELS[ws])
            lbl.setStyleSheet(
                f"font-size: 10px; color: {C.TEXT_MUTED};"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(lbl)

            wrapper = QWidget()
            wrapper.setLayout(col)
            wrapper.setFixedWidth(80)
            step_layout.addWidget(wrapper)

            self._step_circles.append(circle)
            self._step_labels_ui.append(lbl)

        root.addWidget(self._step_bar)

        # ── Body scroll area ──
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
        enable_touch_scroll(scroll)
        root.addWidget(scroll, stretch=1)

    # ══════════════════════════════════════════════════════
    # STEP NAVIGATION
    # ══════════════════════════════════════════════════════

    def _set_step(self, step: WizardStep):
        self._step = step
        step_num = list(WizardStep).index(step) + 1

        # Update step badge
        self._step_badge.setText(f"Step {step_num}/4")
        colors = {
            1: ("muted",),
            2: ("secondary",),
            3: ("accent",),
            4: ("success",),
        }
        variant = colors.get(step_num, ("muted",))[0]
        badge_colors = {
            "primary": (C.PRIMARY_BG, C.PRIMARY, C.PRIMARY),
            "secondary": (C.SECONDARY_BG, C.SECONDARY, C.SECONDARY),
            "accent": (C.ACCENT_BG, C.ACCENT, C.ACCENT),
            "success": (C.SUCCESS_BG, C.SUCCESS, C.SUCCESS),
            "muted": (C.BG_CARD_ALT, C.TEXT_MUTED, C.TEXT_MUTED),
        }
        bg, fg, bd = badge_colors.get(variant, badge_colors["muted"])
        self._step_badge.setStyleSheet(
            f"background-color: {bg}; color: {fg};"
            f"border: 1px solid {bd}; border-radius: 4px;"
            f"padding: 2px 8px; font-size: {F.TINY}px; font-weight: bold;"
        )

        # Update step indicator circles + lines
        for i, circle in enumerate(self._step_circles):
            lbl = self._step_labels_ui[i]
            if i < step_num - 1:
                # Completed step
                circle.setText(Icon.OK)
                circle.setStyleSheet(
                    f"background-color: {C.PRIMARY}; color: {C.BG_DARK};"
                    f"border-radius: 14px; border: 2px solid {C.PRIMARY};"
                    f"font-size: {F.TINY}px; font-weight: bold;"
                )
                lbl.setStyleSheet(
                    f"font-size: 10px; color: {C.PRIMARY}; font-weight: bold;"
                )
            elif i == step_num - 1:
                # Current step -- highlighted
                circle.setText(str(i + 1))
                circle.setStyleSheet(
                    f"background-color: {C.PRIMARY_BG}; color: {C.PRIMARY};"
                    f"border-radius: 14px; border: 2px solid {C.PRIMARY};"
                    f"font-size: {F.TINY}px; font-weight: bold;"
                )
                lbl.setStyleSheet(
                    f"font-size: 10px; color: {C.PRIMARY}; font-weight: bold;"
                )
            else:
                # Future step
                circle.setText(str(i + 1))
                circle.setStyleSheet(
                    f"background-color: {C.BG_CARD}; color: {C.TEXT_MUTED};"
                    f"border-radius: 14px; border: 2px solid {C.BORDER};"
                    f"font-size: {F.TINY}px; font-weight: bold;"
                )
                lbl.setStyleSheet(
                    f"font-size: 10px; color: {C.TEXT_MUTED};"
                )

        # Update connecting lines
        for i, line in enumerate(self._step_lines):
            if i < step_num - 1:
                line.setStyleSheet(f"background-color: {C.PRIMARY};")
            else:
                line.setStyleSheet(f"background-color: {C.BORDER};")

        self._rebuild_body()

    def _go_back(self):
        steps = list(WizardStep)
        idx = steps.index(self._step)
        if idx > 0:
            self._set_step(steps[idx - 1])
        else:
            self.app.go_back()

    # ══════════════════════════════════════════════════════
    # BODY REBUILD
    # ══════════════════════════════════════════════════════

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

    # ── Step 1: Select Area ──────────────────────────────

    def _build_step_select_area(self):
        chart = getattr(self.app, "maintenance_chart", None)

        # Section header
        hdr = section_header(Icon.CHART, "SELECT VESSEL AREA", C.SECONDARY)
        self._body_layout.addWidget(hdr)

        if not chart or not chart.get("areas"):
            msg_card = _card_frame(C.TEXT_MUTED)
            mc_lay = QVBoxLayout(msg_card)
            mc_lay.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
            mc_lay.setSpacing(S.GAP)

            no_icon = icon_badge(Icon.CLOUD, bg_color=C.BG_CARD_ALT,
                                 fg_color=C.TEXT_MUTED, size=36)
            mc_lay.addWidget(no_icon, alignment=Qt.AlignmentFlag.AlignCenter)

            msg = QLabel(
                "No maintenance chart loaded.\n"
                "Pair with cloud to receive the vessel chart."
            )
            msg.setStyleSheet(
                f"font-size: {F.BODY}px; color: {C.TEXT_MUTED};"
            )
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            msg.setWordWrap(True)
            mc_lay.addWidget(msg)

            self._body_layout.addWidget(msg_card)
            self._body_layout.addStretch(1)
            return

        # Area color cycling for visual variety
        area_colors = [C.SECONDARY, C.PRIMARY, C.ACCENT, C.SUCCESS]
        area_icons = [Icon.CHART, Icon.SHELF, Icon.INVENTORY, Icon.SENSORS]

        areas = chart.get("areas", [])
        for i, area in enumerate(areas):
            accent = area_colors[i % len(area_colors)]
            area_icon = area_icons[i % len(area_icons)]

            btn_card = QFrame()
            btn_card.setStyleSheet(
                f"QFrame {{"
                f"  background-color: {C.BG_CARD};"
                f"  border: 1px solid {C.BORDER};"
                f"  border-left: 4px solid {accent};"
                f"  border-radius: {S.RADIUS}px;"
                f"}}"
                f"QFrame:hover {{ border-color: {accent}; }}"
            )
            bc_lay = QHBoxLayout(btn_card)
            bc_lay.setContentsMargins(S.PAD_CARD, S.PAD_CARD,
                                      S.PAD_CARD, S.PAD_CARD)
            bc_lay.setSpacing(S.GAP)

            badge = icon_badge(area_icon, bg_color=C.BG_CARD_ALT,
                               fg_color=accent, size=32)
            bc_lay.addWidget(badge)

            area_name = area.get("name", f"Area {i+1}")
            lbl = QLabel(area_name)
            lbl.setStyleSheet(
                f"font-size: {F.BODY}px; font-weight: bold; color: {C.TEXT};"
            )
            bc_lay.addWidget(lbl, stretch=1)

            arrow = icon_label(Icon.FORWARD, color=accent, size=16)
            bc_lay.addWidget(arrow)

            # Make the whole card clickable via overlay button
            btn = QPushButton()
            btn.setStyleSheet(
                "background: transparent; border: none;"
            )
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedSize(1, 1)  # invisible
            idx = i
            btn.clicked.connect(
                lambda checked=False, a=idx: self._on_area_selected(a)
            )

            # We use a click handler on the card frame directly
            btn_card.mousePressEvent = (
                lambda event, a=i: self._on_area_selected(a)
            )
            btn_card.setCursor(Qt.CursorShape.PointingHandCursor)

            self._body_layout.addWidget(btn_card)

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

    # ── Step 2: View Layers ──────────────────────────────

    def _build_step_view_layers(self):
        if not self._selected_area:
            self._set_step(WizardStep.SELECT_AREA)
            return

        area_name = self._selected_area.get("name", "Selected Area")

        # Section header
        hdr = section_header(Icon.SHELF, f"LAYERS: {area_name}", C.SECONDARY)
        self._body_layout.addWidget(hdr)

        layers = self._selected_area.get("layers", [])
        if not layers:
            msg = QLabel("No layers defined for this area.")
            msg.setStyleSheet(
                f"font-size: {F.BODY}px; color: {C.TEXT_MUTED};"
            )
            self._body_layout.addWidget(msg)
            self._body_layout.addStretch(1)
            return

        for i, layer in enumerate(layers):
            card = _card_frame(C.SECONDARY)
            c_layout = QHBoxLayout(card)
            c_layout.setContentsMargins(
                S.PAD_CARD, S.PAD_CARD, S.PAD_CARD, S.PAD_CARD
            )
            c_layout.setSpacing(S.GAP)

            # Layer number badge
            layer_badge = icon_badge(
                f"L{i+1}", bg_color=C.SECONDARY_BG,
                fg_color=C.SECONDARY, size=36
            )
            c_layout.addWidget(layer_badge)

            # Product info column
            info_layout = QVBoxLayout()
            info_layout.setSpacing(2)

            product = layer.get(
                "product_name", layer.get("product", "Unknown")
            )
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

            # Type badge if product type available
            ptype = layer.get("type", "")
            if ptype:
                tbadge = type_badge(ptype.upper(), "primary")
                info_layout.addWidget(tbadge)

            c_layout.addLayout(info_layout, stretch=1)

            # Select button
            btn = QPushButton(f"{Icon.FORWARD}  SELECT")
            btn.setObjectName("secondary")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedWidth(100)
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

    # ── Step 3: Enter m2 ─────────────────────────────────

    def _build_step_enter_m2(self):
        product = ""
        if self._selected_layer:
            product = self._selected_layer.get(
                "product_name", self._selected_layer.get("product", "")
            )

        # Section header
        hdr = section_header(
            Icon.EDIT, f"SURFACE AREA (m2): {product}", C.SECONDARY
        )
        self._body_layout.addWidget(hdr)

        # Input card
        input_card = _card_frame(C.ACCENT)
        ic_lay = QVBoxLayout(input_card)
        ic_lay.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
        ic_lay.setSpacing(S.GAP)

        lbl = QLabel("AREA (m2)")
        lbl.setStyleSheet(
            f"font-size: {F.SMALL}px; font-weight: bold; color: {C.TEXT_SEC};"
        )
        ic_lay.addWidget(lbl)

        self._m2_input = QLineEdit()
        self._m2_input.setPlaceholderText("Enter m2...")
        self._m2_input.setValidator(QDoubleValidator(0.1, 9999.0, 1))
        self._m2_input.setStyleSheet(
            f"font-size: {F.H2}px; padding: 10px;"
            f"min-height: 44px; text-align: center;"
            f"background-color: {C.BG_INPUT}; color: {C.TEXT};"
            f"border: 1px solid {C.BORDER}; border-radius: 8px;"
        )
        self._m2_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic_lay.addWidget(self._m2_input)

        # Quick presets
        preset_lbl = QLabel("QUICK PRESETS")
        preset_lbl.setStyleSheet(
            f"font-size: {F.TINY}px; color: {C.TEXT_MUTED}; font-weight: bold;"
        )
        ic_lay.addWidget(preset_lbl)

        presets_row = QHBoxLayout()
        presets_row.setSpacing(S.GAP)

        for val in [10, 25, 50, 100]:
            btn = QPushButton(f"{val} m2")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(40)
            btn.setStyleSheet(
                f"background-color: {C.BG_CARD_ALT}; color: {C.TEXT};"
                f"border: 1px solid {C.BORDER}; border-radius: 6px;"
                f"font-size: {F.BODY}px; font-weight: bold;"
            )
            btn.clicked.connect(
                lambda checked=False, v=val: self._set_m2_preset(v)
            )
            presets_row.addWidget(btn)

        preset_wrapper = QWidget()
        preset_wrapper.setLayout(presets_row)
        ic_lay.addWidget(preset_wrapper)

        self._body_layout.addWidget(input_card)

        self._body_layout.addStretch(1)

        # Calculate button
        btn_calc = _gradient_btn(
            f"{Icon.FORWARD}  CALCULATE", C.PRIMARY, C.SECONDARY, F.H3
        )
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

        coverage = DEFAULT_COVERAGE
        chart = getattr(self.app, "maintenance_chart", None)
        if chart:
            for p in chart.get("products", []):
                if p.get("name", "") == product:
                    coverage = p.get(
                        "coverage_m2_per_liter", DEFAULT_COVERAGE
                    )
                    break

        if coverage <= 0:
            coverage = DEFAULT_COVERAGE

        liters_needed = self._m2_value / coverage

        self._quantities.append({
            "product": product,
            "type": "BASE",
            "liters": round(liters_needed, 2),
        })

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

    # ── Step 4: Show Quantities ──────────────────────────

    def _build_step_show_quantities(self):
        area_name = (
            self._selected_area.get("name", "")
            if self._selected_area else ""
        )

        # Section header
        hdr = section_header(
            Icon.WEIGHT,
            f"REQUIRED: {self._m2_value:.0f} m2 - {area_name}",
            C.SUCCESS,
        )
        self._body_layout.addWidget(hdr)

        if not self._quantities:
            msg = QLabel("No quantities calculated.")
            msg.setStyleSheet(
                f"font-size: {F.BODY}px; color: {C.TEXT_MUTED};"
            )
            self._body_layout.addWidget(msg)
        else:
            for q in self._quantities:
                ptype = q.get("type", "BASE")

                # Choose card accent by type
                accent_map = {
                    "BASE": C.PRIMARY,
                    "HARDENER": C.ACCENT,
                    "THINNER": C.SECONDARY,
                }
                accent = accent_map.get(ptype, C.TEXT_MUTED)

                card = _card_frame(accent)
                c_layout = QHBoxLayout(card)
                c_layout.setContentsMargins(
                    S.PAD_CARD, S.PAD_CARD, S.PAD_CARD, S.PAD_CARD
                )
                c_layout.setSpacing(S.GAP)

                # Type badge
                badge_variant = {
                    "BASE": "primary",
                    "HARDENER": "accent",
                    "THINNER": "secondary",
                }
                tbadge = type_badge(
                    ptype, badge_variant.get(ptype, "muted")
                )
                c_layout.addWidget(tbadge)

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
                    f"font-size: {F.H3}px; font-weight: bold; color: {accent};"
                )
                c_layout.addWidget(lbl_amt)

                self._body_layout.addWidget(card)

        self._body_layout.addStretch(1)

        # Start Mixing button
        btn_mix = _gradient_btn(
            f"{Icon.PLAY}  START MIXING", C.PRIMARY, C.SECONDARY, F.H3
        )
        btn_mix.clicked.connect(self._on_start_mixing)
        self._body_layout.addWidget(btn_mix)

    # ══════════════════════════════════════════════════════
    # LIFECYCLE
    # ══════════════════════════════════════════════════════

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

        product_name = base_q.get("product", "Unknown")
        ratio_base = 4.0
        ratio_hardener = 1.0
        pot_life = 480
        tolerance = 5.0
        hardener_name = "Hardener"

        chart = getattr(self.app, "maintenance_chart", None)
        if chart:
            for p in chart.get("products", []):
                if (p.get("name", "") == product_name
                        and p.get("is_bicomponent")):
                    ratio_base = p.get("ratio_base", 4.0)
                    ratio_hardener = p.get("ratio_hardener", 1.0)
                    pot_life = p.get("pot_life_minutes", 480)
                    tolerance = p.get("tolerance_pct", 5.0)
                    hardener_name = p.get("hardener_name", "Hardener")
                    break

        hardener_grams = base_grams * (ratio_hardener / ratio_base)

        self.app.pending_mix = {
            "product_name": product_name,
            "hardener_name": hardener_name,
            "base_grams": round(base_grams, 0),
            "hardener_grams": round(hardener_grams, 0),
            "base_liters": base_q["liters"],
            "hardener_liters": (
                hardener_q["liters"] if hardener_q else 0
            ),
            "ratio_base": ratio_base,
            "ratio_hardener": ratio_hardener,
            "pot_life_minutes": pot_life,
            "tolerance_pct": tolerance,
            "area_name": (
                self._selected_area.get("name", "")
                if self._selected_area else ""
            ),
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
