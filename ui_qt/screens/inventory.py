"""
SmartLocker Inventory Screen — v2

Two-tier inventory view:
  1. Cloud stock (vessel_stock) = total expected quantities
  2. NFC-verified stock (rfid_tag + slot_state) = confirmed on-shelf cans

Product cards are expandable: tap to reveal per-color breakdown with
shelf positions, batch numbers, and verified/unverified status.
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

# Progress bar max
MAX_LITERS = 20.0

# Product type -> (border color, badge variant)
_TYPE_STYLE = {
    "BASE_PAINT": (C.PRIMARY,   "primary"),
    "BASE":       (C.PRIMARY,   "primary"),
    "HARDENER":   (C.ACCENT,    "accent"),
    "THINNER":    (C.SECONDARY, "secondary"),
    "PRIMER":     (C.SUCCESS,   "success"),
}

# Map color names to approximate hex (fallback if not in product catalog)
_COLOR_HEX_FALLBACK = {
    "RED": "#E53E3E", "REDBROWN": "#A0522D", "BROWN": "#8B4513",
    "GREEN": "#38A169", "YELLOW-GREEN": "#A6FF00", "YELLOW": "#ECC94B",
    "BLUE": "#3182CE", "NAVY": "#001F3F", "BLACK": "#1A202C",
    "WHITE": "#F7FAFC", "GREY": "#A0AEC0", "GRAY": "#A0AEC0",
    "ORANGE": "#ED8936", "PEARL": "#E5E4E2", "CREAM": "#FFFDD0",
}


def _color_hex(name: str, product_colors: list = None) -> str:
    """Resolve a color name to a hex code."""
    upper = (name or "").upper().strip()
    # Check product catalog colors first
    if product_colors:
        for c in product_colors:
            if isinstance(c, dict) and (c.get("name", "").upper() == upper):
                return c.get("hex", "#888888")
    # Fallback map
    return _COLOR_HEX_FALLBACK.get(upper, "#888888")


def _slot_label(slot_id: str) -> str:
    """Convert 'shelf1_slot3' to 'S3'."""
    if "slot" in slot_id:
        try:
            return f"S{slot_id.split('slot')[-1]}"
        except Exception:
            pass
    return slot_id


class InventoryScreen(QWidget):
    """Inventory browser with verified vs cloud stock + expandable cards."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._card_widgets = []
        self._expanded = set()  # product_ids that are expanded
        self._build_ui()

    # ------------------------------------------------------------------
    # UI BUILD
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # -- Header --
        header_frame, header_layout = screen_header(
            self.app, "INVENTORY", Icon.INVENTORY, C.SUCCESS,
        )

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
        """Reload stock data, merge cloud + RFID, rebuild cards."""
        # 1. Cloud vessel_stock
        try:
            vessel = self.app.db.get_vessel_stock()
        except Exception:
            vessel = []

        # 2. NFC-verified shelf inventory
        try:
            shelf_items = self.app.db.get_shelf_inventory_details()
        except Exception:
            shelf_items = []

        # 3. Build merged product list
        products = self._merge_data(vessel, shelf_items)

        # If no data at all, fall back to product catalog
        if not products:
            try:
                catalog = self.app.db.get_products()
                products = {
                    p.get("product_id", ""): {
                        "product_id": p.get("product_id", ""),
                        "product_name": p.get("name", p.get("product_name", "Unknown")),
                        "product_type": p.get("product_type", "BASE"),
                        "current_liters": 0.0,
                        "density_g_per_ml": p.get("density_g_per_ml", 1.0),
                        "colors_json": p.get("colors_json", "[]"),
                        "shelf_cans": [],
                    }
                    for p in catalog
                }
            except Exception:
                products = {}

        total_products = len(products)
        verified_count = sum(
            1 for p in products.values() if p.get("shelf_cans")
        )
        self._count_label.setText(
            f"{verified_count} verified / {total_products} total"
        )

        # Clear old cards
        for w in self._card_widgets:
            self._cards_layout.removeWidget(w)
            w.deleteLater()
        self._card_widgets.clear()

        if not products:
            self._show_empty_state()
            return

        # Sort: verified products first, then alphabetical
        sorted_products = sorted(
            products.values(),
            key=lambda p: (0 if p.get("shelf_cans") else 1, p.get("product_name", "")),
        )

        for item in sorted_products:
            card = self._build_product_card(item)
            idx = self._cards_layout.count() - 1
            self._cards_layout.insertWidget(idx, card)
            self._card_widgets.append(card)

    def _merge_data(self, vessel: list, shelf_items: list) -> dict:
        """Merge vessel_stock (cloud) with shelf_inventory (NFC-verified).
        Returns dict keyed by product_id."""
        products = {}

        # First: cloud vessel_stock
        for v in vessel:
            pid = v.get("product_id", "")
            if not pid:
                continue
            products[pid] = {
                "product_id": pid,
                "product_name": v.get("product_name", "Unknown"),
                "product_type": v.get("product_type", "BASE"),
                "current_liters": float(v.get("current_liters", 0) or 0),
                "density_g_per_ml": float(v.get("density_g_per_ml", 1.0) or 1.0),
                "colors_json": v.get("colors_json", "[]"),
                "shelf_cans": [],
            }

        # Second: NFC-verified cans on shelf
        for s in shelf_items:
            pid = s.get("product_id", "")
            slot_id = s.get("slot_id", "")
            tag_color = s.get("tag_color", "") or ""
            batch = s.get("batch_number", "") or ""
            can_ml = s.get("can_size_ml", 0) or 0
            weight_g = s.get("weight_current_g", 0) or 0

            can_info = {
                "slot_id": slot_id,
                "slot_label": _slot_label(slot_id),
                "color": tag_color,
                "batch": batch,
                "can_size_ml": can_ml,
                "weight_g": weight_g,
                "tag_uid": s.get("current_tag_id", ""),
            }

            if pid and pid in products:
                products[pid]["shelf_cans"].append(can_info)
            elif pid:
                # Product on shelf but NOT in vessel_stock (NFC-only discovery)
                products[pid] = {
                    "product_id": pid,
                    "product_name": s.get("product_name", "Unknown"),
                    "product_type": s.get("product_type", "BASE"),
                    "current_liters": 0.0,
                    "density_g_per_ml": 1.0,
                    "colors_json": s.get("product_colors_json", "[]"),
                    "shelf_cans": [can_info],
                }
            elif slot_id:
                # Tag on shelf, unknown product — group under slot name
                unknown_key = f"_unknown_{slot_id}"
                if unknown_key not in products:
                    products[unknown_key] = {
                        "product_id": unknown_key,
                        "product_name": s.get("product_name") or f"Unknown ({_slot_label(slot_id)})",
                        "product_type": "BASE",
                        "current_liters": 0.0,
                        "density_g_per_ml": 1.0,
                        "colors_json": "[]",
                        "shelf_cans": [can_info],
                    }
                else:
                    products[unknown_key]["shelf_cans"].append(can_info)

        return products

    def _show_empty_state(self):
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

        sub = QLabel("Pair with cloud or place tagged cans on shelf.")
        sub.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.TEXT_MUTED};"
        )
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wrapper_layout.addWidget(sub)

        idx = self._cards_layout.count() - 1
        self._cards_layout.insertWidget(idx, wrapper)
        self._card_widgets.append(wrapper)

    # ------------------------------------------------------------------
    # PRODUCT CARD
    # ------------------------------------------------------------------

    def _build_product_card(self, item: dict) -> QFrame:
        """Build a product card with verified/unverified sections."""
        pid = item.get("product_id", "")
        ptype = (item.get("product_type", "BASE") or "BASE").upper()
        border_color, badge_variant = _TYPE_STYLE.get(
            ptype, (C.TEXT_MUTED, "muted")
        )
        is_expanded = pid in self._expanded
        shelf_cans = item.get("shelf_cans", [])
        has_verified = len(shelf_cans) > 0

        # Parse product catalog colors
        colors_json = item.get("colors_json", "[]")
        if isinstance(colors_json, str):
            try:
                catalog_colors = json.loads(colors_json)
            except Exception:
                catalog_colors = []
        else:
            catalog_colors = colors_json or []

        # Card frame
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
        card.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(S.PAD_CARD + 4, S.PAD_CARD, S.PAD_CARD, S.PAD_CARD)
        layout.setSpacing(6)

        # -- Row 1: type badge + name + verified badge + expand arrow --
        row1 = QHBoxLayout()
        row1.setSpacing(S.GAP)

        ptype_display = ptype.replace("_", " ")
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

        # Expand/collapse arrow
        arrow = QPushButton(Icon.ARROW_DOWN if not is_expanded else Icon.ARROW_UP)
        arrow.setFixedSize(32, 32)
        arrow.setCursor(Qt.CursorShape.PointingHandCursor)
        arrow.setStyleSheet(
            f"background-color: transparent; color: {C.TEXT_MUTED};"
            f"font-size: 18px; border: none;"
        )
        arrow.clicked.connect(lambda _, p=pid: self._toggle_expand(p))
        row1.addWidget(arrow)

        layout.addLayout(row1)

        # -- Row 2: verified count + cloud stock --
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        if has_verified:
            ver_lbl = QLabel(f"{Icon.OK}  {len(shelf_cans)} on shelf")
            ver_lbl.setStyleSheet(
                f"font-size: {F.SMALL}px; color: {C.SUCCESS}; font-weight: bold;"
                f"background-color: {C.SUCCESS_BG}; border-radius: 4px;"
                f"padding: 2px 8px;"
            )
            row2.addWidget(ver_lbl)
        else:
            ver_lbl = QLabel("not verified")
            ver_lbl.setStyleSheet(
                f"font-size: {F.SMALL}px; color: {C.TEXT_MUTED};"
                f"background-color: {C.BG_INPUT}; border-radius: 4px;"
                f"padding: 2px 8px;"
            )
            row2.addWidget(ver_lbl)

        qty = float(item.get("current_liters", 0) or 0)
        if qty > 0:
            density = float(item.get("density_g_per_ml", 1.0) or 1.0)
            weight_kg = qty * density
            cloud_lbl = QLabel(f"{qty:.1f} L  |  {weight_kg:.1f} kg (cloud)")
            cloud_lbl.setStyleSheet(
                f"font-size: {F.SMALL}px; color: {C.TEXT_SEC};"
            )
            row2.addWidget(cloud_lbl)

        row2.addStretch()
        layout.addLayout(row2)

        # -- Row 3: color swatches (compact) --
        # Collect all colors: from shelf cans + catalog
        all_color_names = set()
        for can in shelf_cans:
            c = (can.get("color") or "").strip()
            if c and c.upper() != "NONE":
                all_color_names.add(c.upper())
        for cc in catalog_colors:
            if isinstance(cc, dict):
                all_color_names.add(cc.get("name", "").upper())

        if all_color_names:
            color_row = QHBoxLayout()
            color_row.setSpacing(6)
            for cname in sorted(all_color_names):
                chex = _color_hex(cname, catalog_colors)
                dot = QLabel()
                dot.setFixedSize(16, 16)
                dot.setStyleSheet(
                    f"background-color: {chex}; border-radius: 3px;"
                    f"border: 2px solid {C.BORDER};"
                )
                color_row.addWidget(dot)

                clbl = QLabel(cname)
                clbl.setStyleSheet(
                    f"font-size: {F.TINY}px; color: {C.TEXT_SEC};"
                )
                color_row.addWidget(clbl)
            color_row.addStretch()
            layout.addLayout(color_row)

        # -- Row 4: progress bar --
        pct = min(100, max(0, int((qty / MAX_LITERS) * 100))) if MAX_LITERS > 0 else 0
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(pct)
        bar.setTextVisible(False)
        bar.setFixedHeight(10)

        if pct > 50:
            chunk_color = C.SUCCESS
        elif pct > 25:
            chunk_color = C.WARNING
        else:
            chunk_color = C.DANGER

        bar.setStyleSheet(
            f"QProgressBar {{"
            f"  background-color: {C.BG_INPUT}; border: none; border-radius: 5px;"
            f"}}"
            f"QProgressBar::chunk {{"
            f"  background-color: {chunk_color}; border-radius: 5px;"
            f"}}"
        )
        layout.addWidget(bar)

        # ══════════════════════════════════════════════════════
        # EXPANDED SECTION (per-color cans on shelf)
        # ══════════════════════════════════════════════════════
        if is_expanded:
            # Separator
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background-color: {C.BORDER};")
            layout.addWidget(sep)

            if shelf_cans:
                # -- ON SHELF section --
                hdr_on = QLabel(f"{Icon.OK}  ON SHELF  (NFC Verified)")
                hdr_on.setStyleSheet(
                    f"font-size: {F.SMALL}px; font-weight: bold;"
                    f"color: {C.SUCCESS}; padding-top: 4px;"
                )
                layout.addWidget(hdr_on)

                for can in shelf_cans:
                    can_row = QHBoxLayout()
                    can_row.setSpacing(6)
                    can_row.setContentsMargins(8, 2, 0, 2)

                    # Color dot
                    c_name = (can.get("color") or "NONE").upper()
                    c_hex = _color_hex(c_name, catalog_colors)
                    cdot = QLabel()
                    cdot.setFixedSize(14, 14)
                    cdot.setStyleSheet(
                        f"background-color: {c_hex}; border-radius: 3px;"
                        f"border: 1px solid {C.BORDER};"
                    )
                    can_row.addWidget(cdot)

                    # Color name
                    cn_lbl = QLabel(c_name if c_name != "NONE" else "No color")
                    cn_lbl.setStyleSheet(
                        f"font-size: {F.SMALL}px; font-weight: bold; color: {C.TEXT};"
                    )
                    cn_lbl.setMinimumWidth(100)
                    can_row.addWidget(cn_lbl)

                    # Slot position
                    slot_lbl = QLabel(can.get("slot_label", "?"))
                    slot_lbl.setStyleSheet(
                        f"font-size: {F.SMALL}px; font-weight: bold;"
                        f"color: {C.PRIMARY}; background-color: {C.PRIMARY_BG};"
                        f"border-radius: 4px; padding: 1px 6px;"
                    )
                    can_row.addWidget(slot_lbl)

                    # Can size
                    can_ml = can.get("can_size_ml", 0) or 0
                    if can_ml:
                        size_lbl = QLabel(f"{can_ml}ml")
                        size_lbl.setStyleSheet(
                            f"font-size: {F.TINY}px; color: {C.TEXT_SEC};"
                        )
                        can_row.addWidget(size_lbl)

                    # Batch
                    batch = can.get("batch", "") or ""
                    if batch and batch != "00000000":
                        batch_lbl = QLabel(f"Batch: {batch}")
                        batch_lbl.setStyleSheet(
                            f"font-size: {F.TINY}px; color: {C.TEXT_MUTED};"
                        )
                        can_row.addWidget(batch_lbl)

                    # Weight
                    w_g = can.get("weight_g", 0) or 0
                    if w_g > 0:
                        w_lbl = QLabel(f"{w_g:.0f}g")
                        w_lbl.setStyleSheet(
                            f"font-size: {F.TINY}px; color: {C.TEXT_MUTED};"
                        )
                        can_row.addWidget(w_lbl)

                    can_row.addStretch()
                    layout.addLayout(can_row)
            else:
                no_shelf = QLabel("No cans verified on shelf")
                no_shelf.setStyleSheet(
                    f"font-size: {F.SMALL}px; color: {C.TEXT_MUTED};"
                    f"padding: 4px 8px;"
                )
                layout.addWidget(no_shelf)

            # -- CATALOG COLORS section --
            if catalog_colors:
                sep2 = QFrame()
                sep2.setFixedHeight(1)
                sep2.setStyleSheet(f"background-color: {C.BORDER};")
                layout.addWidget(sep2)

                hdr_cat = QLabel(f"{Icon.INVENTORY}  CATALOG COLORS")
                hdr_cat.setStyleSheet(
                    f"font-size: {F.SMALL}px; font-weight: bold;"
                    f"color: {C.TEXT_SEC}; padding-top: 4px;"
                )
                layout.addWidget(hdr_cat)

                # Which colors are verified on shelf?
                verified_colors = set()
                for can in shelf_cans:
                    c = (can.get("color") or "").strip().upper()
                    if c and c != "NONE":
                        verified_colors.add(c)

                for cc in catalog_colors:
                    if isinstance(cc, dict):
                        cname = cc.get("name", "")
                        chex = cc.get("hex", "#888888")
                    else:
                        cname = str(cc)
                        chex = "#888888"

                    cat_row = QHBoxLayout()
                    cat_row.setSpacing(6)
                    cat_row.setContentsMargins(8, 2, 0, 2)

                    cdot = QLabel()
                    cdot.setFixedSize(14, 14)
                    cdot.setStyleSheet(
                        f"background-color: {chex}; border-radius: 3px;"
                        f"border: 1px solid {C.BORDER};"
                    )
                    cat_row.addWidget(cdot)

                    cn_lbl = QLabel(cname)
                    cn_lbl.setStyleSheet(
                        f"font-size: {F.SMALL}px; color: {C.TEXT};"
                    )
                    cat_row.addWidget(cn_lbl)

                    # Verified badge
                    if cname.upper() in verified_colors:
                        ok_lbl = QLabel(f"{Icon.OK} on shelf")
                        ok_lbl.setStyleSheet(
                            f"font-size: {F.TINY}px; color: {C.SUCCESS};"
                        )
                        cat_row.addWidget(ok_lbl)
                    else:
                        miss_lbl = QLabel("not on shelf")
                        miss_lbl.setStyleSheet(
                            f"font-size: {F.TINY}px; color: {C.TEXT_MUTED};"
                        )
                        cat_row.addWidget(miss_lbl)

                    cat_row.addStretch()
                    layout.addLayout(cat_row)

            # -- DELETE button at bottom of expanded --
            del_row = QHBoxLayout()
            del_row.addStretch()
            btn_del = QPushButton(f"{Icon.DELETE}  Remove from inventory")
            btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_del.setStyleSheet(
                f"background-color: {C.DANGER_BG}; color: {C.DANGER};"
                f"font-weight: bold; font-size: {F.SMALL}px;"
                f"border: 1px solid {C.DANGER}; border-radius: 6px;"
                f"padding: 4px 12px;"
            )
            btn_del.clicked.connect(
                lambda _, p=pid: self._delete_item(p)
            )
            del_row.addWidget(btn_del)
            layout.addLayout(del_row)

        # Make entire card clickable to expand/collapse
        card.mousePressEvent = lambda event, p=pid: self._toggle_expand(p)

        return card

    # ------------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------------

    def _toggle_expand(self, product_id: str):
        """Toggle expand/collapse for a product card."""
        if product_id in self._expanded:
            self._expanded.discard(product_id)
        else:
            self._expanded.add(product_id)
        self._refresh()

    def _delete_item(self, product_id: str):
        """Delete a product from vessel_stock."""
        try:
            deleted = self.app.db.delete_vessel_stock_item(product_id)
            if deleted:
                logger.info(f"Deleted vessel_stock item: {product_id}")
            self._expanded.discard(product_id)
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
