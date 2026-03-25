"""
SmartLocker Shelf Map Screen

Grid display of all locker slots showing occupancy status,
product names, and color-coded indicators. Refreshes every 1.5 seconds.
"""

import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout,
)
from PyQt6.QtCore import Qt, QTimer

from ui_qt.theme import C, F, S

logger = logging.getLogger("smartlocker.ui.shelf_map")


class ShelfMapScreen(QWidget):
    """Grid view of all shelf slots with live occupancy status."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._slot_cards = []
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

        title = QLabel("SHELF MAP")
        title.setStyleSheet(
            f"font-size: {F.H2}px; font-weight: bold; color: {C.TEXT};"
        )
        h_layout.addWidget(title)

        h_layout.addStretch(1)

        self._summary_label = QLabel("--")
        self._summary_label.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.TEXT_SEC};"
        )
        h_layout.addWidget(self._summary_label)

        root.addWidget(header)

        # ── Grid container ──────────────────────────────
        grid_wrapper = QWidget()
        self._grid_layout = QGridLayout(grid_wrapper)
        self._grid_layout.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
        self._grid_layout.setSpacing(S.GAP)

        root.addWidget(grid_wrapper, stretch=1)

        # ── Bottom spacer ───────────────────────────────
        root.addStretch(0)

    # ══════════════════════════════════════════════════════════
    # DATA REFRESH
    # ══════════════════════════════════════════════════════════

    def _refresh(self):
        """Rebuild the slot grid from inventory engine data."""
        # Clear existing cards
        for w in self._slot_cards:
            self._grid_layout.removeWidget(w)
            w.deleteLater()
        self._slot_cards.clear()

        # Get slot data
        slots = []
        try:
            all_slots = self.app.inventory_engine.get_all_slots()
            slots = sorted(all_slots, key=lambda s: s.position)
        except Exception:
            pass

        # Fallback: generate empty slots based on slot_count
        slot_count = getattr(self.app, "slot_count", 4)
        if not slots:
            slots = self._make_placeholder_slots(slot_count)

        occupied = sum(1 for s in slots if self._is_occupied(s))
        total = len(slots)
        self._summary_label.setText(f"{occupied}/{total} occupied")

        # Build 4-column grid
        cols = 4 if total >= 4 else max(1, total)
        for i, slot in enumerate(slots):
            row = i // cols
            col = i % cols
            card = self._build_slot_card(i, slot)
            self._grid_layout.addWidget(card, row, col)
            self._slot_cards.append(card)

    def _is_occupied(self, slot) -> bool:
        """Check if a slot is occupied (works with Slot objects or dicts)."""
        if hasattr(slot, "status"):
            from core.models import SlotStatus
            return slot.status == SlotStatus.OCCUPIED
        return slot.get("occupied", False)

    def _make_placeholder_slots(self, count: int) -> list:
        """Generate placeholder slot dicts when no real data is available."""
        return [
            {"slot_id": f"S{i+1}", "position": i + 1, "occupied": False,
             "product_name": "", "status_text": "EMPTY"}
            for i in range(count)
        ]

    def _build_slot_card(self, index: int, slot) -> QFrame:
        """Build a single slot card showing number, status, and product."""
        card = QFrame()
        card.setObjectName("card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(S.PAD_CARD, S.PAD_CARD, S.PAD_CARD, S.PAD_CARD)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Determine slot info
        if hasattr(slot, "slot_id"):
            # Real Slot object
            slot_label = f"S{slot.position}"
            from core.models import SlotStatus
            is_occ = slot.status == SlotStatus.OCCUPIED
            product = slot.current_product_id or ""
            status_text = slot.status.value.upper()
        else:
            # Dict placeholder
            slot_label = slot.get("slot_id", f"S{index + 1}")
            is_occ = slot.get("occupied", False)
            product = slot.get("product_name", "")
            status_text = slot.get("status_text", "EMPTY")

        # Accent color
        if is_occ:
            accent = C.PRIMARY
            status_color = C.PRIMARY
            border_color = C.PRIMARY
        else:
            accent = C.TEXT_MUTED
            status_color = C.TEXT_MUTED
            border_color = C.BORDER

        card.setStyleSheet(
            f"QFrame#card {{ border-top: 3px solid {accent};"
            f"border-color: {border_color}; }}"
        )

        # Slot number
        lbl_num = QLabel(slot_label)
        lbl_num.setStyleSheet(
            f"font-size: {F.H1}px; font-weight: bold; color: {accent};"
        )
        lbl_num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_num)

        # Status indicator
        lbl_status = QLabel(status_text)
        lbl_status.setStyleSheet(
            f"font-size: {F.TINY}px; font-weight: bold; color: {status_color};"
        )
        lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_status)

        # Product name (if occupied)
        if is_occ and product:
            # Try to resolve product name from DB
            display_name = product
            try:
                products = self.app.db.get_products()
                for p in products:
                    pid = p.get("product_id", p.get("id", ""))
                    if pid == product:
                        display_name = p.get("name", p.get("product_name", product))
                        break
            except Exception:
                pass

            lbl_prod = QLabel(display_name)
            lbl_prod.setStyleSheet(
                f"font-size: {F.SMALL}px; color: {C.TEXT_SEC};"
            )
            lbl_prod.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_prod.setWordWrap(True)
            layout.addWidget(lbl_prod)
        elif not is_occ:
            lbl_empty = QLabel("--")
            lbl_empty.setStyleSheet(
                f"font-size: {F.SMALL}px; color: {C.TEXT_MUTED};"
            )
            lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl_empty)

        return card

    # ══════════════════════════════════════════════════════════
    # LIFECYCLE
    # ══════════════════════════════════════════════════════════

    def on_enter(self):
        self._refresh()
        self._timer.start(1500)

    def on_leave(self):
        self._timer.stop()
