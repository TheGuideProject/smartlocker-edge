"""
SmartLocker Inventory Screen

ScrollArea with product cards showing stock levels, type badges,
and color-coded progress bars. Auto-refreshes every 2 seconds.
"""

import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QProgressBar, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer

from ui_qt.theme import C, F, S, enable_touch_scroll

logger = logging.getLogger("smartlocker.ui.inventory")


# Maximum liters per product for progress bar calculation
MAX_LITERS = 20.0


class InventoryScreen(QWidget):
    """Inventory browser showing all vessel stock with fill-level bars."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._card_widgets = []
        self._build_ui()

    # ══════════════════════════════════════════════════════════
    # UI BUILD
    # ══════════════════════════════════════════════════════════

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header bar ──────────────────────────────────
        header = QFrame()
        header.setStyleSheet(
            f"background-color: {C.BG_STATUS};"
            f"border-bottom: 1px solid {C.BORDER};"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(S.PAD, 8, S.PAD, 8)
        header_layout.setSpacing(S.GAP)

        btn_back = QPushButton("< BACK")
        btn_back.setObjectName("ghost")
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back.clicked.connect(lambda: self.app.go_back())
        header_layout.addWidget(btn_back)

        title = QLabel("INVENTORY")
        title.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.TEXT};"
        )
        header_layout.addWidget(title)

        header_layout.addStretch(1)

        self._count_label = QLabel("--")
        self._count_label.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.TEXT_SEC};"
        )
        header_layout.addWidget(self._count_label)

        root.addWidget(header)

        # ── Scroll area for cards ───────────────────────
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

        # ── Bottom bar ──────────────────────────────────
        bottom = QFrame()
        bottom.setStyleSheet(
            f"background-color: {C.BG_STATUS};"
            f"border-top: 1px solid {C.BORDER};"
        )
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(S.PAD, 6, S.PAD, 6)
        bottom_layout.setSpacing(S.GAP)

        btn_shelves = QPushButton("CHECK SHELVES")
        btn_shelves.setObjectName("secondary")
        btn_shelves.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_shelves.clicked.connect(lambda: self.app.go_screen("shelf_map"))
        bottom_layout.addWidget(btn_shelves)

        bottom_layout.addStretch(1)

        root.addWidget(bottom)

    # ══════════════════════════════════════════════════════════
    # DATA REFRESH
    # ══════════════════════════════════════════════════════════

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
            empty = QLabel("No inventory data available.\nPair with cloud to sync products.")
            empty.setStyleSheet(
                f"font-size: {F.BODY}px; color: {C.TEXT_MUTED};"
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setWordWrap(True)
            self._cards_layout.insertWidget(0, empty)
            self._card_widgets.append(empty)
            return

        # Build a card for each product
        for item in stock:
            card = self._build_product_card(item)
            # Insert before the stretch
            idx = self._cards_layout.count() - 1
            self._cards_layout.insertWidget(idx, card)
            self._card_widgets.append(card)

    def _build_product_card(self, item: dict) -> QFrame:
        """Build a single product card with name, type badge, and progress bar."""
        card = QFrame()
        card.setObjectName("card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(S.PAD_CARD, S.PAD_CARD, S.PAD_CARD, S.PAD_CARD)
        layout.setSpacing(6)

        # ── Top row: product name + type badge ──
        top = QHBoxLayout()
        top.setSpacing(S.GAP)

        name = item.get("product_name", "Unknown")
        lbl_name = QLabel(name)
        lbl_name.setStyleSheet(
            f"font-size: {F.BODY}px; font-weight: bold; color: {C.TEXT};"
        )
        lbl_name.setWordWrap(True)
        top.addWidget(lbl_name, stretch=1)

        ptype = item.get("product_type", "BASE").upper()
        # Normalize display name
        ptype_display = ptype.replace("_", " ") if ptype else "BASE"
        badge = QLabel(ptype_display)
        badge_colors = {
            "BASE_PAINT": (C.PRIMARY_BG, C.PRIMARY, C.PRIMARY),
            "BASE": (C.PRIMARY_BG, C.PRIMARY, C.PRIMARY),
            "HARDENER": (C.ACCENT_BG, C.ACCENT, C.ACCENT),
            "THINNER": (C.SECONDARY_BG, C.SECONDARY, C.SECONDARY),
            "PRIMER": (C.PRIMARY_BG, C.PRIMARY, C.PRIMARY),
        }
        bg, fg, border_c = badge_colors.get(ptype, (C.BG_CARD_ALT, C.TEXT_MUTED, C.TEXT_MUTED))
        badge.setStyleSheet(
            f"background-color: {bg}; color: {fg};"
            f"border: 1px solid {border_c}; border-radius: 4px;"
            f"padding: 2px 8px; font-size: {F.TINY}px; font-weight: bold;"
        )
        badge.setFixedHeight(22)
        top.addWidget(badge)

        # Delete button
        product_id = item.get("product_id", "")
        btn_del = QPushButton("X")
        btn_del.setFixedSize(28, 28)
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.setStyleSheet(
            f"background-color: transparent; color: {C.DANGER};"
            f"font-weight: bold; font-size: 14px; border: 1px solid {C.DANGER};"
            f"border-radius: 4px;"
        )
        btn_del.clicked.connect(lambda checked, pid=product_id: self._delete_item(pid))
        top.addWidget(btn_del)

        layout.addLayout(top)

        # ── Color row (if available) ──
        colors_json = item.get("colors_json", "[]")
        if isinstance(colors_json, str):
            try:
                import json
                colors = json.loads(colors_json)
            except Exception:
                colors = []
        else:
            colors = colors_json or []

        if colors:
            color_row = QHBoxLayout()
            color_row.setSpacing(6)
            for color_entry in colors[:4]:  # Max 4 colors
                if isinstance(color_entry, dict):
                    cname = color_entry.get("name", "")
                    chex = color_entry.get("hex", "#888888")
                else:
                    cname = str(color_entry)
                    chex = "#888888"

                dot = QLabel()
                dot.setFixedSize(14, 14)
                dot.setStyleSheet(
                    f"background-color: {chex}; border-radius: 7px;"
                    f"border: 1px solid {C.BORDER};"
                )
                color_row.addWidget(dot)

                if cname:
                    clbl = QLabel(cname)
                    clbl.setStyleSheet(
                        f"font-size: {F.TINY}px; color: {C.TEXT_SEC};"
                    )
                    color_row.addWidget(clbl)

            color_row.addStretch()
            layout.addLayout(color_row)

        # ── Quantity row ──
        qty = float(item.get("current_liters", 0) or item.get("quantity_liters", 0))
        density = float(item.get("density_g_per_ml", 1.3) or 1.3)
        weight_kg = qty * density  # liters * kg/L
        lbl_qty = QLabel(f"{qty:.1f} L  ({weight_kg:.1f} kg)")
        lbl_qty.setStyleSheet(
            f"font-size: {F.BODY}px; font-weight: bold; color: {C.TEXT_SEC};"
        )
        layout.addWidget(lbl_qty)

        # ── Progress bar ──
        pct = min(100, max(0, int((qty / MAX_LITERS) * 100))) if MAX_LITERS > 0 else 0

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(pct)
        bar.setTextVisible(False)
        bar.setFixedHeight(10)

        # Color based on fill level
        if pct > 50:
            chunk_color = C.PRIMARY
        elif pct > 25:
            chunk_color = C.WARNING
        else:
            chunk_color = C.DANGER

        bar.setStyleSheet(
            f"QProgressBar {{ background-color: {C.BG_INPUT};"
            f"border: none; border-radius: 4px; }}"
            f"QProgressBar::chunk {{ background-color: {chunk_color};"
            f"border-radius: 4px; }}"
        )
        layout.addWidget(bar)

        return card

    # ══════════════════════════════════════════════════════════
    # ACTIONS
    # ══════════════════════════════════════════════════════════

    def _delete_item(self, product_id: str):
        """Delete a product from vessel_stock."""
        try:
            deleted = self.app.db.delete_vessel_stock_item(product_id)
            if deleted:
                logger.info(f"Deleted vessel_stock item: {product_id}")
            self._refresh()
        except Exception as e:
            logger.error(f"Failed to delete vessel_stock item: {e}")

    # ══════════════════════════════════════════════════════════
    # LIFECYCLE
    # ══════════════════════════════════════════════════════════

    def on_enter(self):
        self._refresh()
        self._timer.start(2000)

    def on_leave(self):
        self._timer.stop()
