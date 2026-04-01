"""
SmartLocker Chart Viewer Screen

Displays the vessel maintenance chart with areas and paint layers
in a scrollable card layout with clear visual hierarchy.
"""

import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea,
)
from PyQt6.QtCore import Qt

from ui_qt.theme import C, F, S, enable_touch_scroll
from ui_qt.icons import (
    Icon, icon_badge, icon_label, status_dot, type_badge, section_header,
    screen_header,
)

logger = logging.getLogger("smartlocker.ui.chart_viewer")

# Product type -> badge variant
_LAYER_TYPE_VARIANT = {
    "BASE_PAINT": "primary",
    "BASE":       "primary",
    "HARDENER":   "accent",
    "THINNER":    "secondary",
    "PRIMER":     "success",
}


class ChartViewerScreen(QWidget):
    """Maintenance chart browser showing areas and their paint layers."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._card_widgets = []
        self._build_ui()

    # ------------------------------------------------------------------
    # UI BUILD
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # -- Header (standard screen_header) --
        header_frame, header_layout = screen_header(
            self.app, "MAINTENANCE CHART", Icon.CHART, C.SECONDARY,
        )

        # Chart name label in header
        self._chart_name_label = QLabel("")
        self._chart_name_label.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.SECONDARY}; font-weight: bold;"
        )
        header_layout.addWidget(self._chart_name_label)

        root.addWidget(header_frame)

        # -- Scroll area for area cards --
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self._scroll_content = QWidget()
        self._cards_layout = QVBoxLayout(self._scroll_content)
        self._cards_layout.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
        self._cards_layout.setSpacing(S.GAP)
        self._cards_layout.addStretch(1)

        scroll.setWidget(self._scroll_content)
        enable_touch_scroll(scroll)
        root.addWidget(scroll, stretch=1)

    # ------------------------------------------------------------------
    # DATA REFRESH
    # ------------------------------------------------------------------

    def _refresh(self):
        """Rebuild area cards from maintenance chart data."""
        # Clear old cards
        for w in self._card_widgets:
            self._cards_layout.removeWidget(w)
            w.deleteLater()
        self._card_widgets.clear()

        chart = getattr(self.app, "maintenance_chart", None)

        if not chart:
            self._chart_name_label.setText("")
            self._show_empty_state()
            return

        # Chart name
        chart_name = chart.get("name", "Unnamed Chart")
        self._chart_name_label.setText(chart_name)

        areas = chart.get("areas", [])
        if not areas:
            msg = QLabel("Chart loaded but no areas defined.")
            msg.setStyleSheet(
                f"font-size: {F.BODY}px; color: {C.TEXT_MUTED};"
            )
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            idx = self._cards_layout.count() - 1
            self._cards_layout.insertWidget(idx, msg)
            self._card_widgets.append(msg)
            return

        for i, area in enumerate(areas):
            card = self._build_area_card(i, area)
            idx = self._cards_layout.count() - 1
            self._cards_layout.insertWidget(idx, card)
            self._card_widgets.append(card)

    def _show_empty_state(self):
        """Centered empty-state placeholder with icon badge."""
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wrapper_layout.setSpacing(S.GAP)

        badge = icon_badge(
            Icon.CHART, C.BG_CARD_ALT, C.TEXT_MUTED, size=48,
        )
        wrapper_layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignCenter)

        lbl = QLabel("No maintenance chart loaded")
        lbl.setStyleSheet(
            f"font-size: {F.BODY}px; color: {C.TEXT_MUTED}; font-weight: bold;"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wrapper_layout.addWidget(lbl)

        sub = QLabel(
            "Pair this device with the cloud platform\n"
            "to receive the vessel maintenance chart."
        )
        sub.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.TEXT_MUTED};"
        )
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        wrapper_layout.addWidget(sub)

        idx = self._cards_layout.count() - 1
        self._cards_layout.insertWidget(idx, wrapper)
        self._card_widgets.append(wrapper)

    def _build_area_card(self, index: int, area: dict) -> QFrame:
        """Build a card for a single area showing its layers with clear
        visual hierarchy: area badge, name, separator, layer rows."""

        card = QFrame()
        card.setObjectName("area_card")
        card.setStyleSheet(
            f"QFrame#area_card {{"
            f"  background-color: {C.BG_CARD};"
            f"  border: 1px solid {C.BORDER};"
            f"  border-left: 4px solid {C.SECONDARY};"
            f"  border-radius: {S.RADIUS}px;"
            f"}}"
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(
            S.PAD_CARD + 4, S.PAD_CARD, S.PAD_CARD, S.PAD_CARD,
        )
        layout.setSpacing(S.GAP)

        # -- Area header row --
        area_name = area.get("name", f"Area {index + 1}")
        layers = area.get("layers", [])

        header_row = QHBoxLayout()
        header_row.setSpacing(S.GAP)

        # Area number badge
        num_badge = icon_badge(
            f"A{index + 1}",
            bg_color=C.SECONDARY_BG, fg_color=C.SECONDARY, size=28,
        )
        header_row.addWidget(num_badge)

        # Area name
        lbl_name = QLabel(area_name)
        lbl_name.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.TEXT};"
        )
        header_row.addWidget(lbl_name, stretch=1)

        # Layer count badge
        count_badge = QLabel(f"{len(layers)} layers")
        count_badge.setStyleSheet(
            f"background-color: {C.BG_CARD_ALT}; color: {C.TEXT_SEC};"
            f"border: 1px solid {C.BORDER}; border-radius: 8px;"
            f"padding: 2px 8px; font-size: {F.TINY}px; font-weight: bold;"
        )
        header_row.addWidget(count_badge)

        layout.addLayout(header_row)

        # -- Separator line --
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {C.BORDER};")
        layout.addWidget(sep)

        # -- Layer rows --
        if not layers:
            no_layers = QLabel("No layers defined")
            no_layers.setStyleSheet(
                f"font-size: {F.SMALL}px; color: {C.TEXT_MUTED};"
            )
            layout.addWidget(no_layers)
        else:
            for j, layer in enumerate(layers):
                layer_row = self._build_layer_row(j, layer)
                layout.addLayout(layer_row)

        return card

    def _build_layer_row(self, index: int, layer: dict) -> QHBoxLayout:
        """Build a single layer row: number badge + product + type badge + color dot."""
        row = QHBoxLayout()
        row.setSpacing(S.GAP)
        row.setContentsMargins(0, 2, 0, 2)

        # Layer number badge
        num_badge = icon_badge(
            f"L{index + 1}",
            bg_color=C.PRIMARY_BG, fg_color=C.PRIMARY, size=24,
        )
        row.addWidget(num_badge)

        # Product name
        product = layer.get("product_name", layer.get("product", "Unknown"))
        lbl_product = QLabel(product)
        lbl_product.setStyleSheet(
            f"font-size: {F.BODY}px; color: {C.TEXT};"
        )
        lbl_product.setWordWrap(True)
        row.addWidget(lbl_product, stretch=1)

        # Product type badge (if available)
        ptype = (layer.get("product_type", "") or "").upper()
        if ptype:
            variant = _LAYER_TYPE_VARIANT.get(ptype, "muted")
            ptype_display = ptype.replace("_", " ")
            tbadge = type_badge(ptype_display, variant)
            tbadge.setFixedHeight(20)
            row.addWidget(tbadge)

        # Color dot (if available)
        color = layer.get("color", "")
        color_hex = layer.get("color_hex", "")
        if color or color_hex:
            dot_hex = color_hex if color_hex else "#999"
            dot = QLabel()
            dot.setFixedSize(14, 14)
            dot.setStyleSheet(
                f"background-color: {dot_hex};"
                f"border-radius: 7px;"
                f"border: 1px solid {C.BORDER};"
            )
            dot.setToolTip(color)
            row.addWidget(dot)

        return row

    # ------------------------------------------------------------------
    # LIFECYCLE
    # ------------------------------------------------------------------

    def on_enter(self):
        self._refresh()

    def on_leave(self):
        pass
