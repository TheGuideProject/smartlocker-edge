"""
SmartLocker Tag Writer Screen

Select a product from the local database, enter batch info,
then write the data to an NFC tag via PN532 USB.
Also registers the tag->product mapping in the local DB.
"""

import logging
import threading

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QLineEdit, QComboBox, QApplication,
)
from PyQt6.QtCore import Qt, QTimer

from ui_qt.theme import C, F, S
from ui_qt.icons import (
    Icon, icon_badge, icon_label, status_dot, type_badge, section_header,
    screen_header,
)

logger = logging.getLogger("smartlocker.ui.tag_writer")


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


def _styled_combo() -> QComboBox:
    """Return a consistently styled QComboBox."""
    combo = QComboBox()
    combo.setStyleSheet(
        f"QComboBox {{"
        f"  background-color: {C.BG_INPUT}; color: {C.TEXT};"
        f"  border: 1px solid {C.BORDER}; border-radius: 8px;"
        f"  padding: 8px 12px; font-size: {F.BODY}px; min-height: 40px;"
        f"}}"
        f"QComboBox::drop-down {{ border: none; width: 28px; }}"
        f"QComboBox QAbstractItemView {{"
        f"  background-color: {C.BG_CARD}; color: {C.TEXT};"
        f"  border: 1px solid {C.BORDER};"
        f"  selection-background-color: {C.PRIMARY_BG};"
        f"  font-size: {F.BODY}px;"
        f"}}"
    )
    return combo


def _styled_input(placeholder: str = "", font_size: int = F.BODY) -> QLineEdit:
    """Return a consistently styled QLineEdit."""
    inp = QLineEdit()
    inp.setPlaceholderText(placeholder)
    inp.setStyleSheet(
        f"background-color: {C.BG_INPUT}; color: {C.TEXT};"
        f"border: 1px solid {C.BORDER}; border-radius: 8px;"
        f"padding: 8px 12px; font-size: {font_size}px; min-height: 40px;"
    )
    return inp


def _label_above(text: str) -> QLabel:
    """Small label styled for placement above an input field."""
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"font-size: {F.SMALL}px; font-weight: bold;"
        f"color: {C.SECONDARY}; letter-spacing: 1px;"
    )
    return lbl


# ═════════════════════════════════════════════════════════
# TAG WRITER SCREEN
# ═════════════════════════════════════════════════════════

class TagWriterScreen(QWidget):
    """Write product data to NFC tags from the product database."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._products = []
        self._last_uid = None
        self._writing = False
        self._scan_busy = False
        self._tags_written = 0
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
            self.app, "TAG WRITER", Icon.TAG, C.ACCENT
        )

        self._status_badge = type_badge("READY", "muted")
        h_layout.addWidget(self._status_badge)

        root.addWidget(header)

        # ── Body: Two-column layout (50/50) ──
        body = QHBoxLayout()
        body.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
        body.setSpacing(S.PAD)

        # ────────────────────────────────────────────
        # LEFT COLUMN: Write Data
        # ────────────────────────────────────────────
        left_frame = QFrame()
        left_frame.setStyleSheet(
            f"QFrame {{ background-color: transparent; }}"
        )
        left = QVBoxLayout(left_frame)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(S.GAP)

        # Section header
        left_hdr = section_header(Icon.EDIT, "WRITE DATA", C.ACCENT)
        left.addWidget(left_hdr)

        # Reader/Slot selector (which PN532 to write on)
        left.addWidget(_label_above("WRITE ON READER"))
        self._combo_reader = _styled_combo()
        left.addWidget(self._combo_reader)

        # Product dropdown
        left.addWidget(_label_above("PRODUCT"))
        self._combo_product = _styled_combo()
        self._combo_product.currentIndexChanged.connect(
            self._on_product_changed
        )
        left.addWidget(self._combo_product)

        # Batch number
        left.addWidget(_label_above("BATCH NUMBER"))
        self._input_batch = _styled_input("e.g. 80008800")
        left.addWidget(self._input_batch)

        # Color dropdown (populated from product's colors_json)
        left.addWidget(_label_above("COLOR"))
        self._combo_color = _styled_combo()
        left.addWidget(self._combo_color)

        # Can size with presets
        left.addWidget(_label_above("CAN SIZE (ml)"))

        can_row = QHBoxLayout()
        can_row.setSpacing(S.GAP)

        self._input_can_size = _styled_input("5000")
        can_row.addWidget(self._input_can_size, stretch=1)

        for size in ["1000", "5000", "20000"]:
            btn = QPushButton(size)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"background-color: {C.BG_CARD_ALT}; color: {C.TEXT_SEC};"
                f"border: 1px solid {C.BORDER}; border-radius: 6px;"
                f"padding: 6px 10px; font-size: {F.SMALL}px;"
                f"font-weight: bold; min-height: 36px;"
            )
            btn.clicked.connect(
                lambda checked, s=size: self._input_can_size.setText(s)
            )
            can_row.addWidget(btn)

        can_wrapper = QWidget()
        can_wrapper.setLayout(can_row)
        left.addWidget(can_wrapper)

        left.addStretch(1)

        # WRITE TAG button
        self._btn_write = QPushButton(f"{Icon.SAVE}  WRITE TAG")
        self._btn_write.setObjectName("primary")
        self._btn_write.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_write.setMinimumHeight(S.BTN_H)
        self._btn_write.setStyleSheet(
            f"QPushButton {{"
            f"  background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"    stop:0 {C.ACCENT}, stop:1 {C.PRIMARY});"
            f"  color: {C.BG_DARK}; border: none;"
            f"  border-radius: {S.RADIUS}px;"
            f"  font-size: {F.H3}px; font-weight: bold;"
            f"  min-height: {S.BTN_H}px; padding: 8px 16px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"    stop:0 {C.PRIMARY_DIM}, stop:1 {C.ACCENT});"
            f"}}"
        )
        self._btn_write.clicked.connect(self._on_write_tag)
        left.addWidget(self._btn_write)

        body.addWidget(left_frame, stretch=1)

        # ────────────────────────────────────────────
        # RIGHT COLUMN: Tag Status
        # ────────────────────────────────────────────
        right_frame = QFrame()
        right_frame.setStyleSheet(
            f"QFrame {{ background-color: transparent; }}"
        )
        right = QVBoxLayout(right_frame)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(S.GAP)

        # Section header
        right_hdr = section_header(Icon.TAG, "TAG STATUS", C.ACCENT)
        right.addWidget(right_hdr)

        # ── Tag detection card ──
        tag_card = _card_frame(C.ACCENT)
        tc_lay = QVBoxLayout(tag_card)
        tc_lay.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
        tc_lay.setSpacing(S.GAP)

        # Status row: dot + status text
        tag_status_row = QHBoxLayout()
        tag_status_row.setSpacing(S.GAP)

        self._tag_dot = status_dot(active=False, size=12)
        tag_status_row.addWidget(self._tag_dot)

        self._lbl_tag_status = QLabel("No tag detected")
        self._lbl_tag_status.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.TEXT_MUTED};"
        )
        tag_status_row.addWidget(self._lbl_tag_status, stretch=1)

        tc_lay.addLayout(tag_status_row)

        self._lbl_tag_uid = QLabel("")
        self._lbl_tag_uid.setStyleSheet(
            f"font-size: {F.BODY}px; color: {C.TEXT_SEC};"
        )
        self._lbl_tag_uid.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tc_lay.addWidget(self._lbl_tag_uid)

        self._lbl_tag_current = QLabel("")
        self._lbl_tag_current.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.TEXT_MUTED};"
        )
        self._lbl_tag_current.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_tag_current.setWordWrap(True)
        tc_lay.addWidget(self._lbl_tag_current)

        right.addWidget(tag_card)

        # ── Preview card: what will be written ──
        preview_card = _card_frame(C.PRIMARY)
        pc_lay = QVBoxLayout(preview_card)
        pc_lay.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
        pc_lay.setSpacing(S.GAP)

        preview_hdr_row = QHBoxLayout()
        preview_hdr_row.setSpacing(S.GAP)
        preview_icon = icon_label(Icon.INFO, color=C.SECONDARY, size=14)
        preview_hdr_row.addWidget(preview_icon)
        preview_lbl = QLabel("WRITE PREVIEW")
        preview_lbl.setStyleSheet(
            f"font-size: {F.SMALL}px; font-weight: bold;"
            f"color: {C.SECONDARY}; letter-spacing: 1px;"
        )
        preview_hdr_row.addWidget(preview_lbl)
        preview_hdr_row.addStretch(1)
        pc_lay.addLayout(preview_hdr_row)

        self._lbl_preview_data = QLabel("---")
        self._lbl_preview_data.setStyleSheet(
            f"font-size: {F.BODY}px; color: {C.PRIMARY}; font-weight: bold;"
        )
        self._lbl_preview_data.setWordWrap(True)
        self._lbl_preview_data.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pc_lay.addWidget(self._lbl_preview_data)

        right.addWidget(preview_card)

        # ── Result card: success/failure ──
        result_card = _card_frame(C.TEXT_MUTED)
        self._result_card = result_card
        rc_lay = QVBoxLayout(result_card)
        rc_lay.setContentsMargins(S.PAD, S.PAD, S.PAD, S.PAD)
        rc_lay.setSpacing(S.GAP)

        result_hdr_row = QHBoxLayout()
        result_hdr_row.setSpacing(S.GAP)
        result_icon = icon_label(Icon.OK, color=C.TEXT_MUTED, size=14)
        result_hdr_row.addWidget(result_icon)
        result_lbl = QLabel("LAST RESULT")
        result_lbl.setStyleSheet(
            f"font-size: {F.SMALL}px; font-weight: bold;"
            f"color: {C.SECONDARY}; letter-spacing: 1px;"
        )
        result_hdr_row.addWidget(result_lbl)
        result_hdr_row.addStretch(1)
        rc_lay.addLayout(result_hdr_row)

        self._lbl_result = QLabel("--")
        self._lbl_result.setStyleSheet(
            f"font-size: {F.BODY}px; color: {C.TEXT_MUTED};"
        )
        self._lbl_result.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_result.setWordWrap(True)
        rc_lay.addWidget(self._lbl_result)

        # Tags written counter
        self._lbl_tags_written = QLabel("Tags written: 0")
        self._lbl_tags_written.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.TEXT_SEC};"
        )
        self._lbl_tags_written.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rc_lay.addWidget(self._lbl_tags_written)

        right.addWidget(result_card)
        right.addStretch(1)

        body.addWidget(right_frame, stretch=1)

        root.addLayout(body, stretch=1)

        # ── Internal state ──
        self._scan_timer = QTimer()
        self._scan_timer.timeout.connect(self._scan_for_tag)

    # ══════════════════════════════════════════════════════
    # LIFECYCLE
    # ══════════════════════════════════════════════════════

    def on_enter(self):
        # Pause inventory RFID polling — Tag Writer takes exclusive serial access
        if hasattr(self.app, 'inventory_engine'):
            self.app.inventory_engine.rfid_paused = True
            logger.info("Tag Writer: RFID polling PAUSED (exclusive mode)")

        self._load_readers()
        self._load_products()
        self._update_preview()
        self._scan_timer.start(800)

    def on_leave(self):
        self._scan_timer.stop()
        self._writing = False
        # Resume inventory RFID polling
        if hasattr(self.app, 'inventory_engine'):
            self.app.inventory_engine.rfid_paused = False
            logger.info("Tag Writer: RFID polling RESUMED")

    def _load_readers(self):
        """Populate reader selector from multi-reader RFID driver."""
        self._combo_reader.blockSignals(True)
        self._combo_reader.clear()

        rfid = self.app.rfid
        if hasattr(rfid, 'get_mapping'):
            mapping = rfid.get_mapping()
            for m in mapping:
                rid = m.get("reader_id", "")
                port = m.get("port", "")
                short_port = port.split("/")[-1] if "/" in port else port
                # "S1 (USB1)" format
                slot_num = rid.split("slot")[-1] if "slot" in rid else "?"
                label = f"S{slot_num}  ({short_port})"
                self._combo_reader.addItem(label, rid)  # data = reader_id
        else:
            # Single reader mode
            self._combo_reader.addItem("Default reader", "")

        self._combo_reader.blockSignals(False)

    # ══════════════════════════════════════════════════════
    # PRODUCT LOADING
    # ══════════════════════════════════════════════════════

    def _load_products(self):
        """Load products from DB into combo box."""
        try:
            self._products = self.app.db.get_products()
        except Exception as e:
            logger.error(f"Failed to load products: {e}")
            self._products = []

        self._combo_product.blockSignals(True)
        self._combo_product.clear()

        if not self._products:
            self._combo_product.addItem(
                "No products -- sync with cloud first"
            )
        else:
            for p in self._products:
                name = p.get("name", "Unknown")
                ppg = p.get("ppg_code", "")
                ptype = p.get("product_type", "").upper()
                label = f"{name}"
                if ppg:
                    label += f"  [{ppg}]"
                if ptype:
                    label += f"  ({ptype})"
                self._combo_product.addItem(label)

        self._combo_product.blockSignals(False)
        self._on_product_changed()

    def _on_product_changed(self):
        self._load_colors_for_product()
        self._update_preview()

    def _load_colors_for_product(self):
        """Populate color dropdown from the selected product's colors_json."""
        self._combo_color.blockSignals(True)
        self._combo_color.clear()

        idx = self._combo_product.currentIndex()
        if idx < 0 or not self._products:
            self._combo_color.addItem("No product selected")
            self._combo_color.blockSignals(False)
            return

        product = self._products[idx]
        colors_raw = product.get("colors_json", "[]")

        # Parse colors_json (could be string or list)
        import json as _json
        colors = []
        if isinstance(colors_raw, str):
            try:
                colors = _json.loads(colors_raw) if colors_raw else []
            except Exception:
                colors = []
        elif isinstance(colors_raw, list):
            colors = colors_raw

        if colors:
            for c in colors:
                if isinstance(c, dict):
                    name = c.get("name", "")
                    hex_c = c.get("hex", "")
                    label = name if name else hex_c
                    if hex_c and name:
                        label = f"{name}  ({hex_c})"
                    self._combo_color.addItem(label, name or hex_c)
                elif isinstance(c, str):
                    self._combo_color.addItem(c, c)
        else:
            self._combo_color.addItem("NONE (no colors defined)")
            self._combo_color.setItemData(0, "NONE")

        self._combo_color.blockSignals(False)

    # ══════════════════════════════════════════════════════
    # TAG SCANNING (background poll)
    # ══════════════════════════════════════════════════════

    def _get_selected_reader_id(self) -> str:
        """Get the reader_id from the dropdown selection."""
        idx = self._combo_reader.currentIndex()
        if idx >= 0:
            return self._combo_reader.itemData(idx) or ""
        return ""

    def _scan_for_tag(self):
        """Quick poll in background thread — never blocks the UI."""
        if self._writing or self._scan_busy:
            return

        self._scan_busy = True
        selected_rid = self._get_selected_reader_id()

        def _do_scan():
            try:
                rfid = self.app.rfid
                if selected_rid and hasattr(rfid, 'poll_reader'):
                    tags = rfid.poll_reader(selected_rid)
                else:
                    tags = rfid.poll_tags()
                QTimer.singleShot(0, lambda: self._update_scan_ui(tags))
            except Exception as e:
                logger.debug(f"Tag scan error: {e}")
                QTimer.singleShot(0, lambda: self._update_scan_ui([]))

        threading.Thread(target=_do_scan, daemon=True).start()

    def _update_scan_ui(self, tags):
        """Update UI from scan results — always on main thread."""
        self._scan_busy = False

        if tags:
            tag = tags[0]
            uid = tag.tag_id
            product_data = tag.product_data or ""

            self._last_uid = uid
            self._lbl_tag_status.setText("TAG DETECTED")
            self._lbl_tag_status.setStyleSheet(
                f"font-size: {F.H3}px; font-weight: bold;"
                f"color: {C.SUCCESS};"
            )

            # Update status dot to green
            self._tag_dot.setStyleSheet(
                f"background-color: {C.SUCCESS};"
                f"border-radius: 6px; border: none;"
            )

            self._lbl_tag_uid.setText(f"UID: {uid}")

            if product_data:
                self._lbl_tag_current.setText(f"Current: {product_data}")
            else:
                self._lbl_tag_current.setText("Empty tag (no data)")

            # Update header badge
            self._status_badge.setText("TAG OK")
            self._status_badge.setStyleSheet(
                f"background-color: {C.SUCCESS_BG};"
                f"color: {C.SUCCESS};"
                f"border: 1px solid {C.SUCCESS}; border-radius: 4px;"
                f"padding: 2px 8px; font-size: {F.TINY}px;"
                f"font-weight: bold;"
            )
        else:
            self._last_uid = None
            self._lbl_tag_status.setText("Place tag on reader")
            self._lbl_tag_status.setStyleSheet(
                f"font-size: {F.H3}px; font-weight: bold;"
                f"color: {C.TEXT_MUTED};"
            )

            # Update status dot to red
            self._tag_dot.setStyleSheet(
                f"background-color: {C.DANGER};"
                f"border-radius: 6px; border: none;"
            )

            self._lbl_tag_uid.setText("")
            self._lbl_tag_current.setText("")

            self._status_badge.setText("WAITING")
            self._status_badge.setStyleSheet(
                f"background-color: {C.BG_CARD_ALT};"
                f"color: {C.TEXT_MUTED};"
                f"border: 1px solid {C.TEXT_MUTED}; border-radius: 4px;"
                f"padding: 2px 8px; font-size: {F.TINY}px;"
                f"font-weight: bold;"
            )

    # ══════════════════════════════════════════════════════
    # PREVIEW
    # ══════════════════════════════════════════════════════

    def _update_preview(self):
        """Update the write preview based on current form values."""
        data = self._build_write_string()
        if data:
            self._lbl_preview_data.setText(data)
            self._lbl_preview_data.setStyleSheet(
                f"font-size: {F.BODY}px; color: {C.PRIMARY};"
                f"font-weight: bold;"
            )
        else:
            self._lbl_preview_data.setText("Select a product")
            self._lbl_preview_data.setStyleSheet(
                f"font-size: {F.BODY}px; color: {C.TEXT_MUTED};"
            )

    def _build_write_string(self) -> str:
        """Build the CODE|BATCH|NAME|COLOR string."""
        idx = self._combo_product.currentIndex()
        if idx < 0 or not self._products:
            return ""

        product = self._products[idx]
        ppg_code = product.get("ppg_code", "000000")
        name = product.get("name", "UNKNOWN")
        batch = self._input_batch.text().strip() or "00000000"

        # Color from dropdown
        color_idx = self._combo_color.currentIndex()
        color = (self._combo_color.itemData(color_idx) or "NONE") if color_idx >= 0 else "NONE"
        color = str(color).strip().upper() or "NONE"

        return f"{ppg_code}|{batch}|{name}|{color}"

    # ══════════════════════════════════════════════════════
    # WRITE TAG
    # ══════════════════════════════════════════════════════

    def _on_write_tag(self):
        """Write product data to the NFC tag."""
        if self._writing:
            return

        # Validate
        idx = self._combo_product.currentIndex()
        if idx < 0 or not self._products:
            self._show_result("No product selected", False)
            return

        if not self._last_uid:
            self._show_result(
                "No tag on reader -- place tag first", False
            )
            return

        product = self._products[idx]
        write_string = self._build_write_string()
        if not write_string:
            self._show_result("Cannot build write data", False)
            return

        # Disable button, show writing state
        self._writing = True
        self._btn_write.setText("WRITING...")
        self._btn_write.setEnabled(False)
        self._btn_write.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {C.PRIMARY_DIM}; color: {C.BG_DARK};"
            f"  border: none; border-radius: {S.RADIUS}px;"
            f"  font-size: {F.H3}px; font-weight: bold;"
            f"  min-height: {S.BTN_H}px; padding: 8px 16px;"
            f"}}"
        )
        QApplication.processEvents()

        # RFID polling already paused on screen enter — no extra pause needed

        # Stop scan timer during write to avoid serial contention
        self._scan_timer.stop()

        # Safety timeout: if write hangs > 8s, force-reset UI
        self._write_timeout_timer = QTimer()
        self._write_timeout_timer.setSingleShot(True)
        self._write_timeout_timer.timeout.connect(
            lambda: self._on_write_timeout(product, write_string)
        )
        self._write_timeout_timer.start(8000)

        # Write in a thread to avoid blocking UI
        selected_rid = self._get_selected_reader_id()

        def do_write():
            try:
                # Write on the SELECTED reader only
                if selected_rid:
                    success = self.app.rfid.write_product_data(
                        write_string, reader_id=selected_rid
                    )
                else:
                    success = self.app.rfid.write_product_data(write_string)
                QTimer.singleShot(0, lambda: self._on_write_complete(
                    success, product, write_string
                ))
            except Exception as e:
                logger.error(f"Tag write error: {e}")
                QTimer.singleShot(0, lambda: self._on_write_complete(
                    False, product, write_string
                ))

        threading.Thread(target=do_write, daemon=True).start()

    def _on_write_timeout(self, product: dict, write_string: str):
        """Safety: force-reset if write hangs more than 8 seconds."""
        if not self._writing:
            return  # Already completed normally
        logger.warning("Tag write TIMEOUT (8s) — force-resetting UI")
        # The write thread may still be stuck on reader.lock — mark it so
        # _on_write_complete won't fire again when the thread eventually returns
        self._on_write_complete(False, product, write_string, timed_out=True)

    def _on_write_complete(self, success: bool, product: dict,
                           write_string: str, timed_out: bool = False):
        """Handle write result on main thread."""
        # Cancel timeout timer
        if hasattr(self, '_write_timeout_timer'):
            self._write_timeout_timer.stop()

        # Guard: if already handled (timeout fired + thread returned later), skip
        if not self._writing and not timed_out:
            return
        self._writing = False

        # Restart scan timer — delay 2s after timeout (write thread may still
        # hold the reader lock), immediate after normal completion
        if timed_out:
            QTimer.singleShot(2000, lambda: self._scan_timer.start(800))
        else:
            self._scan_timer.start(800)
        self._btn_write.setText(f"{Icon.SAVE}  WRITE TAG")
        self._btn_write.setEnabled(True)
        self._btn_write.setStyleSheet(
            f"QPushButton {{"
            f"  background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"    stop:0 {C.ACCENT}, stop:1 {C.PRIMARY});"
            f"  color: {C.BG_DARK}; border: none;"
            f"  border-radius: {S.RADIUS}px;"
            f"  font-size: {F.H3}px; font-weight: bold;"
            f"  min-height: {S.BTN_H}px; padding: 8px 16px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"    stop:0 {C.PRIMARY_DIM}, stop:1 {C.ACCENT});"
            f"}}"
        )

        if success:
            self._tags_written += 1
            product_name = product.get("name", "Unknown")
            self._show_result(
                f"{Icon.OK} Written: {product_name}\n{write_string}", True
            )

            # Update result card accent
            self._result_card.setStyleSheet(
                f"QFrame#card {{"
                f"  background-color: {C.BG_CARD};"
                f"  border: 1px solid {C.BORDER};"
                f"  border-left: 4px solid {C.SUCCESS};"
                f"  border-radius: {S.RADIUS}px;"
                f"}}"
            )

            # Register tag -> product mapping in DB
            try:
                batch = self._input_batch.text().strip() or None
                can_ml = None
                try:
                    can_ml = int(self._input_can_size.text().strip())
                except (ValueError, TypeError):
                    pass

                self.app.db.upsert_rfid_tag(
                    tag_uid=self._last_uid,
                    product_id=product["product_id"],
                    can_size_ml=can_ml,
                    batch_number=batch,
                )
                logger.info(
                    f"Tag {self._last_uid} mapped to product "
                    f"{product['product_id']} ({product_name})"
                )
            except Exception as e:
                logger.error(f"Failed to save tag mapping: {e}")

            # Buzzer confirm
            try:
                self.app.buzzer.play_pattern("confirm")
            except Exception:
                pass
        else:
            if timed_out:
                self._show_result(
                    f"{Icon.ERROR} WRITE TIMEOUT -- keep tag steady & retry", False
                )
            else:
                self._show_result(
                    f"{Icon.ERROR} WRITE FAILED -- try again", False
                )

            # Update result card accent
            self._result_card.setStyleSheet(
                f"QFrame#card {{"
                f"  background-color: {C.BG_CARD};"
                f"  border: 1px solid {C.BORDER};"
                f"  border-left: 4px solid {C.DANGER};"
                f"  border-radius: {S.RADIUS}px;"
                f"}}"
            )

            try:
                self.app.buzzer.play_pattern("error")
            except Exception:
                pass

        self._lbl_tags_written.setText(
            f"Tags written: {self._tags_written}"
        )

    def _show_result(self, text: str, success: bool):
        """Update the result label."""
        color = C.SUCCESS if success else C.DANGER
        self._lbl_result.setText(text)
        self._lbl_result.setStyleSheet(
            f"font-size: {F.BODY}px; color: {color}; font-weight: bold;"
        )

    # Connect preview updates to input changes
    def showEvent(self, event):
        super().showEvent(event)
        self._input_batch.textChanged.connect(self._update_preview)
        self._combo_color.currentIndexChanged.connect(self._update_preview)

    def hideEvent(self, event):
        super().hideEvent(event)
        try:
            self._input_batch.textChanged.disconnect(self._update_preview)
            self._combo_color.currentIndexChanged.disconnect(self._update_preview)
        except Exception:
            pass
