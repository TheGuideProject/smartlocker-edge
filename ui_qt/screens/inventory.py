"""
SmartLocker Inventory Screen

ScrollArea with product cards showing stock levels, type badges,
color swatches, and color-coded progress bars. Auto-refreshes every 2 seconds.
"""

import json
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QProgressBar, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer

from ui_qt.theme import C, F, S, enable_touch_scroll
from ui_qt.icons import (
    Icon, icon_badge, icon_label, status_dot, type_badge, section_header,
    screen_header,
)

logger = logging.getLogger("smartlocker.ui.inventory")


# Maximum liters per product for progress bar calculation
MAX_LITERS = 20.0

# Product type -> (border color, badge variant)
_TYPE_STYLE = {
    "BASE_PAINT": (C.PRIMARY,   "primary"),
    "BASE":       (C.PRIMARY,   "primary"),
    "HARDENER":   (C.ACCENT,    "accent"),
    "THINNER":    (C.SECONDARY, "secondary"),
    "PRIMER":     (C.SUCCESS,   "success"),
}


class InventoryScreen(QWidget):
    """Inventory browser showing all vessel stock with fill-level bars."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
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
            self.app, "INVENTORY", Icon.INVENTORY, C.SUCCESS,
        )

        # Product count badge in header
        self._count_label = QLabel("--")
        self._count_label.setStyleSheet(
            f"background-color: {C.SUCCESS_BG}; color: {C.SUCCESS};"
            f"border: 1px solid {C.SUCCESS}; border-radius: 10px;"
            f"padding: 2px 10px; font-size: {F.TINY}px; font-weight: bold;"
        )
        header_layout.addWidget(self._count_label)

        root.addWidget(header_frame)

        # -- Scroll area for cards --
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

        # -- Bottom bar --
        bottom = QFrame()
        bottom.setStyleSheet(
            f"background-color: {C.BG_STATUS};"
            f"border-top: 1px solid {C.BORDER};"
        )
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(S.PAD, 6, S.PAD, 6)
        bottom_layout.setSpacing(S.GAP)

        btn_shelves = QPushButton(f"{Icon.SHELF}  CHECK SHELVES")
        btn_shelves.setObjectName("secondary")
        btn_shelves.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_shelves.clicked.connect(lambda: self.app.go_screen("shelf_map"))
        bottom_layout.addWidget(btn_shelves)

        bottom_layout.addStretch(1)

        root.addWidget(bottom)

    # ------------------------------------------------------------------
    # DATA REFRESH
    # ------------------------------------------------------------------

    def _refresh(self):
        """Reload stock data and rebuild cards."""
        try:
            stock = self.app.db.get_vessel_stock()
        except Exception:
            stock = []

        # If vessel_stock is empty, fall back to product catalog
        if not stock:
            try:
                products = self.app.db.get_products()
                stock = [
                    {
                        "product_name": p.get("name", p.get("product_name", "Unknown")),
                        "product_type": p.get("product_type", "BASE"),
                        "quantity_liters": 0.0,
                    }
                    for p in products
                ]
            except Exception:
                stock = []

        self._count_label.setText(f"{len(stock)} products")

        # Clear old cards
        for w in self._card_widgets:
            self._cards_layout.removeWidget(w)
            w.deleteLater()
        self._card_widgets.clear()

        if not stock:
            self._show_empty_state()
            return

        # Build a card for each product
        for item in stock:
            card = self._build_product_card(item)
            idx = self._cards_layout.count() - 1
            self._cards_layout.insertWidget(idx, card)
            self._card_widgets.append(card)

    def _show_empty_state(self):
        """Centered empty-state placeholder."""
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wrapper_layout.setSpacing(S.GAP)

        badge = icon_badge(Icon.INVENTORY, C.BG_CARD_ALT, C.TEXT_MUTED, size=48)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wrapper_layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignCenter)

        lbl = QLabel("No products in inventory")
        lbl.setStyleSheet(
            f"font-size: {F.BODY}px; color: {C.TEXT_MUTED}; font-weight: bold;"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wrapper_layout.addWidget(lbl)

        sub = QLabel("Pair with cloud to sync products.")
        sub.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.TEXT_MUTED};"
        )
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wrapper_layout.addWidget(sub)

        idx = self._cards_layout.count() - 1
        self._cards_layout.insertWidget(idx, wrapper)
        self._card_widgets.append(wrapper)

    def _build_product_card(self, item: dict) -> QFrame:
        """Build a single product card with left accent border, type badge,
        color swatches, quantity, and progress bar."""

        ptype = (item.get("product_type", "BASE") or "BASE").upper()
        border_color, badge_variant = _TYPE_STYLE.get(
            ptype, (C.TEXT_MUTED, "muted")
        )

        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(
            f"QFrame#card {{"
            f"  background-color: {C.BG_CARD};"
            f"  border: 1px solid {C.BORDER};"
            f"  border-left: 4px solid {border_color};"
            f"  border-radius: {S.RADIUS}px;"
            f"}}"
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(S.PAD_CARD + 4, S.PAD_CARD, S.PAD_CARD, S.PAD_CARD)
        layout.setSpacing(6)

        # -- Row 1: type badge + product name + delete icon --
        row1 = QHBoxLayout()
        row1.setSpacing(S.GAP)

        ptype_display = ptype.replace("_", " ") if ptype else "BASE"
        badge = type_badge(ptype_display, badge_variant)
        badge.setFixedHeight(22)
        row1.addWidget(badge)

        name = item.get("product_name", "Unknown")
        lbl_name = QLabel(name)
        lbl_name.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.TEXT};"
        )
        lbl_name.setWordWrap(True)
        row1.addWidget(lbl_name, stretch=1)

        product_id = item.get("product_id", "")
        btn_del = QPushButton()
        btn_del.setFixedSize(32, 32)
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.setStyleSheet(
            f"background-color: {C.DANGER_BG}; color: {C.DANGER};"
            f"font-weight: bold; font-size: 16px;"
            f"border: 1px solid {C.DANGER}; border-radius: 6px;"
            f"padding: 0px;"
        )
        btn_del.setText(Icon.DELETE)
        btn_del.clicked.connect(
            lambda checked, pid=product_id: self._delete_item(pid)
        )
        row1.addWidget(btn_del)

        layout.addLayout(row1)

        # -- Row 2: color swatches --
        colors_json = item.get("colors_json", "[]")
        if isinstance(colors_json, str):
            try:
                colors = json.loads(colors_json)
            except Exception:
                colors = []
        else:
            colors = colors_json or []

        if colors:
            color_row = QHBoxLayout()
            color_row.setSpacing(S.GAP)

            for color_entry in colors[:4]:
                if isinstance(color_entry, dict):
                    cname = color_entry.get("name", "")
                    chex = color_entry.get("hex", "#888888")
                else:
                    cname = str(color_entry)
                    chex = "#888888"

                dot = QLabel()
                dot.setFixedSize(20, 20)
                dot.setStyleSheet(
                    f"background-color: {chex}; border-radius: 4px;"
                    f"border: 2px solid {C.BORDER};"
                )
                color_row.addWidget(dot)

                if cname:
                    clbl = QLabel(cname)
                    clbl.setStyleSheet(
                        f"font-size: {F.SMALL}px; color: {C.TEXT_SEC};"
                    )
                    color_row.addWidget(clbl)

            color_row.addStretch()
            layout.addLayout(color_row)

        # -- Row 3: quantity --
        qty = float(
            item.get("current_liters", 0) or item.get("quantity_liters", 0)
        )
        density = float(item.get("density_g_per_ml", 1.3) or 1.3)
        weight_kg = qty * density

        qty_row = QHBoxLayout()
        qty_row.setSpacing(4)

        lbl_vol = QLabel(f"{qty:.1f}")
        lbl_vol.setStyleSheet(
            f"font-size: {F.BODY}px; font-weight: bold; color: {C.TEXT};"
        )
        qty_row.addWidget(lbl_vol)

        lbl_vol_unit = QLabel("L")
        lbl_vol_unit.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.TEXT_MUTED};"
        )
        qty_row.addWidget(lbl_vol_unit)

        sep_lbl = QLabel("|")
        sep_lbl.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.BORDER}; padding: 0 4px;"
        )
        qty_row.addWidget(sep_lbl)

        lbl_wt = QLabel(f"{weight_kg:.1f}")
        lbl_wt.setStyleSheet(
            f"font-size: {F.BODY}px; font-weight: bold; color: {C.TEXT};"
        )
        qty_row.addWidget(lbl_wt)

        lbl_wt_unit = QLabel("kg")
        lbl_wt_unit.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.TEXT_MUTED};"
        )
        qty_row.addWidget(lbl_wt_unit)

        qty_row.addStretch()
        layout.addLayout(qty_row)

        # -- Row 4: progress bar --
        pct = (
            min(100, max(0, int((qty / MAX_LITERS) * 100)))
            if MAX_LITERS > 0
            else 0
        )

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(pct)
        bar.setTextVisible(False)
        bar.setFixedHeight(12)

        if pct > 50:
            chunk_color = C.SUCCESS
        elif pct > 25:
            chunk_color = C.WARNING
        else:
            chunk_color = C.DANGER

        bar.setStyleSheet(
            f"QProgressBar {{"
            f"  background-color: {C.BG_INPUT};"
            f"  border: none; border-radius: 6px;"
            f"}}"
            f"QProgressBar::chunk {{"
            f"  background-color: {chunk_color};"
            f"  border-radius: 6px;"
            f"}}"
        )
        layout.addWidget(bar)

        return card

    # ------------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------------

    def _delete_item(self, product_id: str):
        """Delete a product from vessel_stock."""
        try:
            deleted = self.app.db.delete_vessel_stock_item(product_id)
            if deleted:
                logger.info(f"Deleted vessel_stock item: {product_id}")
            self._refresh()
        except Exception as e:
            logger.error(f"Failed to delete vessel_stock item: {e}")

    # ------------------------------------------------------------------
    # LIFECYCLE
    # ------------------------------------------------------------------

    def on_enter(self):
        self._refresh()
        self._timer.start(2000)

    def on_leave(self):
        self._timer.stop()
