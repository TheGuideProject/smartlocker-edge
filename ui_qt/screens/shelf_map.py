"""
SmartLocker Shelf Map Screen

Grid display of all locker slots. Tap a slot to assign a product via
barcode scan (RFID backup). Refreshes every 1.5 seconds.
"""

import json
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout, QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from ui_qt.theme import C, F, S
from ui_qt.icons import (
    Icon, icon_badge, icon_label, status_dot, type_badge, section_header,
    screen_header,
)

logger = logging.getLogger("smartlocker.ui.shelf_map")


class ClickableSlotCard(QFrame):
    """A slot card that responds to taps."""

    def __init__(self, index: int, parent_screen):
        super().__init__()
        self.index = index
        self._parent_screen = parent_screen
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        self._parent_screen._on_slot_tapped(self.index)
        super().mousePressEvent(event)


class ShelfMapScreen(QWidget):
    """Grid view of all shelf slots with live occupancy status and barcode assignment."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._slot_cards = []
        self._selected_slot = None  # Index of slot waiting for barcode
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # -- Header (standard screen_header) --
        header_frame, header_layout = screen_header(
            self.app, "SHELF MAP", Icon.SHELF, C.SECONDARY,
        )

        # Summary count badge
        self._summary_label = QLabel("--")
        self._summary_label.setStyleSheet(
            f"background-color: {C.SECONDARY_BG}; color: {C.SECONDARY};"
            f"border: 1px solid {C.SECONDARY}; border-radius: 10px;"
            f"padding: 2px 10px; font-size: {F.TINY}px; font-weight: bold;"
        )
        header_layout.addWidget(self._summary_label)

        root.addWidget(header_frame)

        # -- Status bar (barcode scanning prompt) --
        self._status_bar = QFrame()
        self._status_bar.setFixedHeight(38)
        self._status_bar.setStyleSheet(
            f"background-color: {C.ACCENT_BG};"
            f"border-bottom: 1px solid {C.ACCENT};"
        )
        status_layout = QHBoxLayout(self._status_bar)
        status_layout.setContentsMargins(S.PAD, 0, S.PAD, 0)
        status_layout.setSpacing(S.GAP)

        status_icon = icon_label(Icon.TAG, color=C.ACCENT, size=18)
        status_layout.addWidget(status_icon)

        self._status_text = QLabel("")
        self._status_text.setStyleSheet(
            f"font-size: {F.BODY}px; font-weight: bold; color: {C.ACCENT};"
        )
        status_layout.addWidget(self._status_text, stretch=1)

        self._status_bar.hide()
        root.addWidget(self._status_bar)

        # -- Grid container --
        grid_wrapper = QWidget()
        self._grid_layout = QGridLayout(grid_wrapper)
        self._grid_layout.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
        self._grid_layout.setSpacing(S.GAP)

        root.addWidget(grid_wrapper, stretch=1)
        root.addStretch(0)

    # ================================================================
    # DATA REFRESH
    # ================================================================

    def _refresh(self):
        """Rebuild the slot grid from inventory engine + assignments."""
        # Clear existing cards
        for w in self._slot_cards:
            self._grid_layout.removeWidget(w)
            w.deleteLater()
        self._slot_cards.clear()

        # Get slot data from inventory engine
        slots = []
        try:
            all_slots = self.app.inventory_engine.get_all_slots()
            slots = sorted(all_slots, key=lambda s: s.position)
        except Exception:
            pass

        slot_count = getattr(self.app, "slot_count", 4)
        if not slots:
            slots = self._make_placeholder_slots(slot_count)

        # Load barcode slot assignments from DB
        assignments = {}
        try:
            assignments = self.app.db.get_slot_assignments()
        except Exception:
            pass

        occupied = sum(
            1 for i, s in enumerate(slots)
            if self._is_occupied(s) or i in assignments
        )
        total = len(slots)
        self._summary_label.setText(f"{occupied}/{total} occupied")

        # Build grid (4 columns)
        cols = 4 if total >= 4 else max(1, total)
        for i, slot in enumerate(slots):
            row = i // cols
            col = i % cols
            assignment = assignments.get(i)
            card = self._build_slot_card(i, slot, assignment)
            self._grid_layout.addWidget(card, row, col)
            self._slot_cards.append(card)

    def _is_occupied(self, slot) -> bool:
        if hasattr(slot, "status"):
            from core.models import SlotStatus
            return slot.status == SlotStatus.OCCUPIED
        return slot.get("occupied", False)

    def _make_placeholder_slots(self, count: int) -> list:
        return [
            {
                "slot_id": f"S{i+1}", "position": i + 1, "occupied": False,
                "product_name": "", "status_text": "EMPTY",
            }
            for i in range(count)
        ]

    def _build_slot_card(self, index: int, slot, assignment=None) -> QFrame:
        """Build a single slot card with top accent border, large number,
        status icon + text, and product/tag info."""

        card = ClickableSlotCard(index, self)

        # -- Determine slot info from RFID --
        if hasattr(slot, "slot_id"):
            slot_label = f"S{slot.position}"
            from core.models import SlotStatus
            is_rfid_occupied = slot.status == SlotStatus.OCCUPIED
            rfid_product = slot.current_product_id or ""
            rfid_tag_uid = slot.current_tag_id or ""
            status_text = slot.status.value.upper()
        else:
            slot_label = slot.get("slot_id", f"S{index + 1}")
            is_rfid_occupied = slot.get("occupied", False)
            rfid_product = slot.get("product_name", "")
            rfid_tag_uid = slot.get("tag_id", "")
            status_text = slot.get("status_text", "EMPTY")

        # -- Determine display state --
        is_selected = self._selected_slot == index
        has_assignment = assignment is not None

        if is_selected:
            accent = C.ACCENT
            border_color = C.ACCENT
            status_text = "SCANNING..."
            status_color = C.ACCENT
            status_icon = Icon.TAG
        elif is_rfid_occupied:
            accent = C.PRIMARY
            border_color = C.PRIMARY
            status_color = C.PRIMARY
            status_icon = Icon.OCCUPIED
        elif has_assignment:
            accent = C.SUCCESS
            border_color = C.SUCCESS
            status_text = "ASSIGNED"
            status_color = C.SUCCESS
            status_icon = Icon.OK
        else:
            accent = C.TEXT_MUTED
            border_color = C.BORDER
            status_color = C.TEXT_MUTED
            status_icon = Icon.EMPTY

        card.setObjectName("slot_card")
        card.setStyleSheet(
            f"QFrame#slot_card {{"
            f"  background-color: {C.BG_CARD};"
            f"  border: 1px solid {C.BORDER};"
            f"  border-top: 3px solid {accent};"
            f"  border-radius: {S.RADIUS}px;"
            f"  padding: {S.PAD_CARD}px;"
            f"}}"
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(S.PAD_CARD, S.PAD_CARD, S.PAD_CARD, S.PAD_CARD)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # -- Top: large slot number --
        lbl_num = QLabel(slot_label)
        lbl_num.setStyleSheet(
            f"font-size: {F.H1}px; font-weight: bold; color: {accent};"
        )
        lbl_num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_num)

        # -- Middle: status icon + status text --
        status_row = QHBoxLayout()
        status_row.setSpacing(4)
        status_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        s_icon = icon_label(status_icon, color=status_color, size=14)
        status_row.addWidget(s_icon)

        lbl_status = QLabel(status_text)
        lbl_status.setStyleSheet(
            f"font-size: {F.TINY}px; font-weight: bold; color: {status_color};"
        )
        status_row.addWidget(lbl_status)

        layout.addLayout(status_row)

        # -- Bottom: product name / tag / placeholder --
        display_name = ""
        if is_rfid_occupied and rfid_product:
            display_name = self._resolve_product_name(rfid_product)
        elif is_rfid_occupied and rfid_tag_uid:
            display_name = self._resolve_name_from_tag(rfid_tag_uid)
        elif has_assignment:
            display_name = assignment.get("product_name", "")

        if display_name:
            lbl_prod = QLabel(display_name)
            lbl_prod.setStyleSheet(
                f"font-size: {F.SMALL}px; color: {C.TEXT_SEC};"
            )
            lbl_prod.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_prod.setWordWrap(True)
            layout.addWidget(lbl_prod)

            # Color swatch dot if available
            colors_json = ""
            if has_assignment:
                colors_json = assignment.get("colors_json", "[]")
            if colors_json and colors_json not in ("[]", "null", ""):
                try:
                    colors = (
                        json.loads(colors_json)
                        if isinstance(colors_json, str) else colors_json
                    )
                    if colors and isinstance(colors, list):
                        first = colors[0]
                        hex_c = first.get("hex", "#999")
                        name_c = first.get("name", "")

                        dot_row = QHBoxLayout()
                        dot_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        dot_row.setSpacing(4)

                        dot = QLabel()
                        dot.setFixedSize(12, 12)
                        dot.setStyleSheet(
                            f"background-color: {hex_c};"
                            f"border-radius: 6px;"
                            f"border: 1px solid {C.BORDER};"
                        )
                        dot_row.addWidget(dot)

                        if name_c:
                            clbl = QLabel(name_c)
                            clbl.setStyleSheet(
                                f"font-size: {F.TINY}px; color: {C.TEXT_MUTED};"
                            )
                            dot_row.addWidget(clbl)

                        layout.addLayout(dot_row)
                except Exception:
                    pass

        elif is_selected:
            lbl_scan = QLabel("Scan barcode...")
            lbl_scan.setStyleSheet(
                f"font-size: {F.SMALL}px; color: {C.ACCENT}; font-style: italic;"
            )
            lbl_scan.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl_scan)
        else:
            lbl_empty = QLabel("--")
            lbl_empty.setStyleSheet(
                f"font-size: {F.SMALL}px; color: {C.TEXT_MUTED};"
            )
            lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl_empty)

        return card

    def _resolve_product_name(self, product_id: str) -> str:
        """Try to resolve product_id to a human-readable name."""
        try:
            products = self.app.db.get_products()
            for p in products:
                pid = p.get("product_id", p.get("id", ""))
                if pid == product_id:
                    return p.get("name", p.get("product_name", product_id))
        except Exception:
            pass
        return product_id

    def _resolve_name_from_tag(self, tag_uid: str) -> str:
        """Try to resolve tag UID to product name via rfid_tag table.
        Falls back to showing the tag UID if no mapping found."""
        try:
            tag_info = self.app.db.get_rfid_tag_info(tag_uid)
            if tag_info:
                name = tag_info.get("product_name") or ""
                if name:
                    return name
                pid = tag_info.get("product_id") or ""
                if pid:
                    return self._resolve_product_name(pid)
        except Exception:
            pass
        # Fallback: show abbreviated tag UID
        short_uid = tag_uid[-8:] if len(tag_uid) > 8 else tag_uid
        return f"Tag: {short_uid}"

    # ================================================================
    # SLOT TAP HANDLING
    # ================================================================

    def _on_slot_tapped(self, index: int):
        """Handle tap on a slot card."""
        # Check if this slot has an assignment
        assignments = {}
        try:
            assignments = self.app.db.get_slot_assignments()
        except Exception:
            pass

        if index in assignments:
            # Slot is assigned -- ask remove or replace
            product_name = assignments[index].get("product_name", "Unknown")
            reply = QMessageBox.question(
                self,
                f"Slot S{index + 1}",
                f"{product_name}\n\nRemove from this slot?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.app.db.clear_slot_assignment(index)
                logger.info(f"Slot S{index + 1} cleared")
                try:
                    from hal.interfaces import BuzzerPattern
                    self.app.buzzer.play(BuzzerPattern.CONFIRM)
                except Exception:
                    pass
                self._selected_slot = None
                self._status_bar.hide()
                self._refresh()
            return

        # Empty slot -- select it for barcode scanning
        if self._selected_slot == index:
            # Deselect
            self._selected_slot = None
            self._status_bar.hide()
        else:
            self._selected_slot = index
            self._status_text.setText(
                f"Scan barcode for S{index + 1}..."
            )
            self._status_bar.show()

        self._refresh()

    # ================================================================
    # BARCODE ASSIGNMENT (called from app.py)
    # ================================================================

    def on_barcode_for_slot(self, product_info: dict):
        """Assign a scanned product to the selected slot."""
        if self._selected_slot is None:
            return

        slot_index = self._selected_slot

        # Get colors from product catalog if not in product_info
        colors_json = product_info.get("colors_json", "[]")
        if not colors_json or colors_json in ("[]", "null"):
            try:
                pid = product_info.get("product_id", "")
                if pid:
                    p = self.app.db.get_product_by_id(pid)
                    if p:
                        colors_json = p.get("colors_json", "[]")
            except Exception:
                pass

        assignment = {
            "product_id": product_info.get("product_id", ""),
            "product_name": product_info.get("product_name", ""),
            "ppg_code": product_info.get("ppg_code", ""),
            "color": product_info.get("color", ""),
            "colors_json": colors_json if isinstance(colors_json, str) else "[]",
        }

        self.app.db.set_slot_assignment(slot_index, assignment)
        logger.info(
            f"Slot S{slot_index + 1} assigned: {assignment['product_name']} "
            f"(ppg={assignment['ppg_code']})"
        )

        # Feedback
        try:
            from hal.interfaces import BuzzerPattern
            self.app.buzzer.play(BuzzerPattern.CONFIRM)
        except Exception:
            pass

        # Clear selection
        self._selected_slot = None
        self._status_bar.hide()
        self._refresh()

    # ================================================================
    # LIFECYCLE
    # ================================================================

    def on_enter(self):
        self._selected_slot = None
        self._status_bar.hide()
        self._refresh()
        self._timer.start(1500)

    def on_leave(self):
        self._timer.stop()
        self._selected_slot = None
        self._status_bar.hide()
