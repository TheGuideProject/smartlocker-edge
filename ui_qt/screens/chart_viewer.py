"""
SmartLocker Chart Viewer Screen

Displays the vessel maintenance chart with areas and paint layers
in a scrollable card layout.
"""

import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea,
)
from PyQt6.QtCore import Qt

from ui_qt.theme import C, F, S, enable_touch_scroll

logger = logging.getLogger("smartlocker.ui.chart_viewer")


class ChartViewerScreen(QWidget):
    """Maintenance chart browser showing areas and their paint layers."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._card_widgets = []
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

        btn_back = QPushButton("< BACK")
        btn_back.setObjectName("ghost")
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back.clicked.connect(lambda: self.app.go_back())
        h_layout.addWidget(btn_back)

        title = QLabel("MAINTENANCE CHART")
        title.setStyleSheet(
            f"font-size: {F.H2}px; font-weight: bold; color: {C.TEXT};"
        )
        h_layout.addWidget(title)

        h_layout.addStretch(1)

        self._chart_name_label = QLabel("")
        self._chart_name_label.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.TEXT_SEC};"
        )
        h_layout.addWidget(self._chart_name_label)

        root.addWidget(header)

        # ── Scroll area for area cards ──────────────────
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

    # ══════════════════════════════════════════════════════════
    # DATA REFRESH
    # ══════════════════════════════════════════════════════════

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
            empty = QLabel(
                "No maintenance chart loaded.\n\n"
                "Pair this device with the cloud platform\n"
                "to receive the vessel maintenance chart."
            )
            empty.setStyleSheet(
                f"font-size: {F.BODY}px; color: {C.TEXT_MUTED};"
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setWordWrap(True)
            idx = self._cards_layout.count() - 1
            self._cards_layout.insertWidget(idx, empty)
            self._card_widgets.append(empty)
            return

        # Chart name
        chart_name = chart.get("name", "Unnamed Chart")
        self._chart_name_label.setText(chart_name)

        areas = chart.get("areas", [])
        if not areas:
            msg = QLabel("Chart loaded but no areas defined.")
            msg.setStyleSheet(f"font-size: {F.BODY}px; color: {C.TEXT_MUTED};")
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

    def _build_area_card(self, index: int, area: dict) -> QFrame:
        """Build a card for a single area showing its layers."""
        card = QFrame()
        card.setObjectName("card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(S.PAD_CARD, S.PAD_CARD, S.PAD_CARD, S.PAD_CARD)
        layout.setSpacing(6)

        # Area header with accent bar
        area_name = area.get("name", f"Area {index + 1}")
        header_row = QHBoxLayout()
        header_row.setSpacing(S.GAP)

        # Number badge
        num_badge = QLabel(f"A{index + 1}")
        num_badge.setStyleSheet(
            f"background-color: {C.SECONDARY_BG}; color: {C.SECONDARY};"
            f"border: 1px solid {C.SECONDARY}; border-radius: 4px;"
            f"padding: 2px 8px; font-size: {F.TINY}px; font-weight: bold;"
        )
        num_badge.setFixedHeight(22)
        header_row.addWidget(num_badge)

        lbl_name = QLabel(area_name)
        lbl_name.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.TEXT};"
        )
        header_row.addWidget(lbl_name, stretch=1)

        layers = area.get("layers", [])
        lbl_count = QLabel(f"{len(layers)} layers")
        lbl_count.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.TEXT_SEC};"
        )
        header_row.addWidget(lbl_count)

        layout.addLayout(header_row)

        # Separator line
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {C.BORDER};")
        layout.addWidget(sep)

        # Layer rows
        if not layers:
            no_layers = QLabel("No layers defined")
            no_layers.setStyleSheet(
                f"font-size: {F.SMALL}px; color: {C.TEXT_MUTED};"
            )
            layout.addWidget(no_layers)
        else:
            for j, layer in enumerate(layers):
                row = QHBoxLayout()
                row.setSpacing(S.GAP)

                # Layer number
                lbl_num = QLabel(f"L{j + 1}")
                lbl_num.setStyleSheet(
                    f"font-size: {F.SMALL}px; font-weight: bold;"
                    f"color: {C.PRIMARY};"
                )
                lbl_num.setFixedWidth(30)
                row.addWidget(lbl_num)

                # Product name
                product = layer.get(
                    "product_name", layer.get("product", "Unknown")
                )
                lbl_product = QLabel(product)
                lbl_product.setStyleSheet(
                    f"font-size: {F.BODY}px; color: {C.TEXT};"
                )
                lbl_product.setWordWrap(True)
                row.addWidget(lbl_product, stretch=1)

                # Color label
                color = layer.get("color", "")
                if color:
                    lbl_color = QLabel(color)
                    lbl_color.setStyleSheet(
                        f"font-size: {F.SMALL}px; color: {C.TEXT_SEC};"
                        f"font-style: italic;"
                    )
                    row.addWidget(lbl_color)

                layout.addLayout(row)

        return card

    # ══════════════════════════════════════════════════════════
    # LIFECYCLE
    # ══════════════════════════════════════════════════════════

    def on_enter(self):
        self._refresh()

    def on_leave(self):
        pass
