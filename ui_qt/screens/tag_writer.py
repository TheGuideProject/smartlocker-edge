"""
SmartLocker Tag Writer Screen

Select a product from the local database, enter batch info,
then write the data to an NFC tag via PN532 USB.
Also registers the tag→product mapping in the local DB.
"""

import logging
import threading

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QLineEdit, QComboBox, QApplication,
)
from PyQt6.QtCore import Qt, QTimer

from ui_qt.theme import C, F, S

logger = logging.getLogger("smartlocker.ui.tag_writer")

# Compact sizes for 800x480
_PAD = 8
_GAP = 6
_F_BIG = 24
_F_MED = 14
_F_SM = 12


class TagWriterScreen(QWidget):
    """Write product data to NFC tags from the product database."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._products = []       # cached product list
        self._last_uid = None     # UID of last detected tag
        self._writing = False
        self._build_ui()

    # ══════════════════════════════════════════════════════
    # UI BUILD
    # ══════════════════════════════════════════════════════

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ──
        header = QFrame()
        header.setStyleSheet(
            f"background-color: {C.BG_STATUS};"
            f"border-bottom: 1px solid {C.BORDER};"
        )
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(_PAD, 4, _PAD, 4)
        h_lay.setSpacing(_GAP)

        btn_back = QPushButton("< BACK")
        btn_back.setObjectName("ghost")
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back.clicked.connect(self.app.go_back)
        h_lay.addWidget(btn_back)

        title = QLabel("TAG WRITER")
        title.setStyleSheet(
            f"font-size: {F.H3}px; font-weight: bold; color: {C.TEXT};"
        )
        h_lay.addWidget(title)
        h_lay.addStretch(1)

        self._status_badge = QLabel("READY")
        self._status_badge.setStyleSheet(
            f"font-size: {_F_SM}px; color: {C.TEXT_MUTED};"
        )
        h_lay.addWidget(self._status_badge)

        root.addWidget(header)

        # ── Body: horizontal layout (form LEFT, status RIGHT) ──
        body = QHBoxLayout()
        body.setContentsMargins(_PAD, _PAD, _PAD, _PAD)
        body.setSpacing(_PAD)

        # LEFT: Product selection + inputs
        left = QVBoxLayout()
        left.setSpacing(_GAP)

        # Product dropdown
        lbl_prod = QLabel("PRODUCT")
        lbl_prod.setStyleSheet(
            f"font-size: {_F_SM}px; font-weight: bold; color: {C.SECONDARY};"
        )
        left.addWidget(lbl_prod)

        self._combo_product = QComboBox()
        self._combo_product.setStyleSheet(
            f"QComboBox {{"
            f"  background-color: {C.BG_INPUT}; color: {C.TEXT};"
            f"  border: 1px solid {C.BORDER}; border-radius: 6px;"
            f"  padding: 6px 10px; font-size: {_F_MED}px; min-height: 32px;"
            f"}}"
            f"QComboBox::drop-down {{"
            f"  border: none; width: 24px;"
            f"}}"
            f"QComboBox QAbstractItemView {{"
            f"  background-color: {C.BG_CARD}; color: {C.TEXT};"
            f"  border: 1px solid {C.BORDER}; selection-background-color: {C.PRIMARY_BG};"
            f"  font-size: {_F_MED}px;"
            f"}}"
        )
        self._combo_product.currentIndexChanged.connect(self._on_product_changed)
        left.addWidget(self._combo_product)

        # Batch number input
        lbl_batch = QLabel("BATCH NUMBER")
        lbl_batch.setStyleSheet(
            f"font-size: {_F_SM}px; font-weight: bold; color: {C.SECONDARY};"
        )
        left.addWidget(lbl_batch)

        self._input_batch = QLineEdit()
        self._input_batch.setPlaceholderText("e.g. 80008800")
        self._input_batch.setStyleSheet(
            f"background-color: {C.BG_INPUT}; color: {C.TEXT};"
            f"border: 1px solid {C.BORDER}; border-radius: 6px;"
            f"padding: 6px 10px; font-size: {_F_MED}px; min-height: 32px;"
        )
        left.addWidget(self._input_batch)

        # Color input
        lbl_color = QLabel("COLOR (optional)")
        lbl_color.setStyleSheet(
            f"font-size: {_F_SM}px; font-weight: bold; color: {C.SECONDARY};"
        )
        left.addWidget(lbl_color)

        self._input_color = QLineEdit()
        self._input_color.setPlaceholderText("e.g. WHITE, RED, YELLOWGREEN")
        self._input_color.setStyleSheet(
            f"background-color: {C.BG_INPUT}; color: {C.TEXT};"
            f"border: 1px solid {C.BORDER}; border-radius: 6px;"
            f"padding: 6px 10px; font-size: {_F_MED}px; min-height: 32px;"
        )
        left.addWidget(self._input_color)

        # Can size input
        lbl_can = QLabel("CAN SIZE (ml)")
        lbl_can.setStyleSheet(
            f"font-size: {_F_SM}px; font-weight: bold; color: {C.SECONDARY};"
        )
        left.addWidget(lbl_can)

        can_row = QHBoxLayout()
        can_row.setSpacing(_GAP)
        self._input_can_size = QLineEdit()
        self._input_can_size.setPlaceholderText("5000")
        self._input_can_size.setStyleSheet(
            f"background-color: {C.BG_INPUT}; color: {C.TEXT};"
            f"border: 1px solid {C.BORDER}; border-radius: 6px;"
            f"padding: 6px 10px; font-size: {_F_MED}px; min-height: 32px;"
        )
        can_row.addWidget(self._input_can_size, stretch=1)

        # Quick presets
        for size in ["1000", "5000", "20000"]:
            btn = QPushButton(f"{size}")
            btn.setStyleSheet(
                f"background-color: {C.BG_CARD}; color: {C.TEXT_SEC};"
                f"border: 1px solid {C.BORDER}; border-radius: 4px;"
                f"padding: 4px 8px; font-size: {_F_SM}px; min-height: 28px;"
            )
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, s=size: self._input_can_size.setText(s))
            can_row.addWidget(btn)
        left.addLayout(can_row)

        left.addStretch(1)

        # ── WRITE button ──
        self._btn_write = QPushButton("WRITE TAG")
        self._btn_write.setStyleSheet(
            f"background-color: {C.PRIMARY}; color: {C.BG_DARK};"
            f"border: none; border-radius: 8px;"
            f"font-size: {_F_BIG}px; font-weight: bold;"
            f"min-height: 48px; padding: 8px;"
        )
        self._btn_write.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_write.clicked.connect(self._on_write_tag)
        left.addWidget(self._btn_write)

        # RIGHT: Tag status + preview
        right = QVBoxLayout()
        right.setSpacing(_GAP)

        # Tag detection card
        tag_card = QFrame()
        tag_card.setObjectName("card")
        tc_lay = QVBoxLayout(tag_card)
        tc_lay.setContentsMargins(_PAD, _PAD, _PAD, _PAD)
        tc_lay.setSpacing(_GAP)

        lbl_tag_section = QLabel("NFC TAG")
        lbl_tag_section.setStyleSheet(
            f"font-size: {_F_SM}px; font-weight: bold; color: {C.SECONDARY};"
        )
        tc_lay.addWidget(lbl_tag_section)

        self._lbl_tag_status = QLabel("No tag detected")
        self._lbl_tag_status.setStyleSheet(
            f"font-size: {_F_BIG}px; font-weight: bold; color: {C.TEXT_MUTED};"
        )
        self._lbl_tag_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tc_lay.addWidget(self._lbl_tag_status)

        self._lbl_tag_uid = QLabel("")
        self._lbl_tag_uid.setStyleSheet(
            f"font-size: {_F_MED}px; color: {C.TEXT_SEC};"
        )
        self._lbl_tag_uid.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tc_lay.addWidget(self._lbl_tag_uid)

        self._lbl_tag_current = QLabel("")
        self._lbl_tag_current.setStyleSheet(
            f"font-size: {_F_SM}px; color: {C.TEXT_MUTED};"
        )
        self._lbl_tag_current.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_tag_current.setWordWrap(True)
        tc_lay.addWidget(self._lbl_tag_current)

        right.addWidget(tag_card)

        # Preview card: what will be written
        preview_card = QFrame()
        preview_card.setObjectName("card")
        pc_lay = QVBoxLayout(preview_card)
        pc_lay.setContentsMargins(_PAD, _PAD, _PAD, _PAD)
        pc_lay.setSpacing(_GAP)

        lbl_preview = QLabel("WRITE PREVIEW")
        lbl_preview.setStyleSheet(
            f"font-size: {_F_SM}px; font-weight: bold; color: {C.SECONDARY};"
        )
        pc_lay.addWidget(lbl_preview)

        self._lbl_preview_data = QLabel("---")
        self._lbl_preview_data.setStyleSheet(
            f"font-size: {_F_MED}px; color: {C.PRIMARY}; font-weight: bold;"
        )
        self._lbl_preview_data.setWordWrap(True)
        self._lbl_preview_data.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pc_lay.addWidget(self._lbl_preview_data)

        right.addWidget(preview_card)

        # Result card
        result_card = QFrame()
        result_card.setObjectName("card")
        rc_lay = QVBoxLayout(result_card)
        rc_lay.setContentsMargins(_PAD, _PAD, _PAD, _PAD)
        rc_lay.setSpacing(_GAP)

        lbl_result = QLabel("LAST RESULT")
        lbl_result.setStyleSheet(
            f"font-size: {_F_SM}px; font-weight: bold; color: {C.SECONDARY};"
        )
        rc_lay.addWidget(lbl_result)

        self._lbl_result = QLabel("--")
        self._lbl_result.setStyleSheet(
            f"font-size: {_F_MED}px; color: {C.TEXT_MUTED};"
        )
        self._lbl_result.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_result.setWordWrap(True)
        rc_lay.addWidget(self._lbl_result)

        self._lbl_tags_written = QLabel("Tags written: 0")
        self._lbl_tags_written.setStyleSheet(
            f"font-size: {_F_SM}px; color: {C.TEXT_SEC};"
        )
        self._lbl_tags_written.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rc_lay.addWidget(self._lbl_tags_written)

        right.addWidget(result_card)
        right.addStretch(1)

        # Assemble body
        body.addLayout(left, stretch=1)
        body.addLayout(right, stretch=1)
        root.addLayout(body, stretch=1)

        # Internal state
        self._tags_written = 0
        self._scan_timer = QTimer()
        self._scan_timer.timeout.connect(self._scan_for_tag)

    # ══════════════════════════════════════════════════════
    # LIFECYCLE
    # ══════════════════════════════════════════════════════

    def on_enter(self):
        self._load_products()
        self._update_preview()
        self._scan_timer.start(800)

    def on_leave(self):
        self._scan_timer.stop()

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
            self._combo_product.addItem("No products — sync with cloud first")
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
        self._update_preview()

    # ══════════════════════════════════════════════════════
    # TAG SCANNING (background poll)
    # ══════════════════════════════════════════════════════

    def _scan_for_tag(self):
        """Quick poll to detect if a tag is on the reader."""
        if self._writing:
            return

        try:
            tags = self.app.rfid.poll_tags()
            if tags:
                tag = tags[0]
                uid = tag.tag_id
                product_data = tag.product_data or ""

                self._last_uid = uid
                self._lbl_tag_status.setText("TAG DETECTED")
                self._lbl_tag_status.setStyleSheet(
                    f"font-size: {_F_BIG}px; font-weight: bold; color: {C.SUCCESS};"
                )
                self._lbl_tag_uid.setText(f"UID: {uid}")

                if product_data:
                    self._lbl_tag_current.setText(f"Current: {product_data}")
                else:
                    self._lbl_tag_current.setText("Empty tag (no data)")

                self._status_badge.setText("TAG OK")
                self._status_badge.setStyleSheet(
                    f"background-color: {C.SUCCESS_BG}; color: {C.SUCCESS};"
                    f"border: 1px solid {C.SUCCESS}; border-radius: 4px;"
                    f"padding: 2px 8px; font-size: {_F_SM}px; font-weight: bold;"
                )
            else:
                self._last_uid = None
                self._lbl_tag_status.setText("Place tag on reader")
                self._lbl_tag_status.setStyleSheet(
                    f"font-size: {_F_BIG}px; font-weight: bold; color: {C.TEXT_MUTED};"
                )
                self._lbl_tag_uid.setText("")
                self._lbl_tag_current.setText("")

                self._status_badge.setText("WAITING")
                self._status_badge.setStyleSheet(
                    f"font-size: {_F_SM}px; color: {C.TEXT_MUTED};"
                )
        except Exception as e:
            logger.debug(f"Tag scan error: {e}")

    # ══════════════════════════════════════════════════════
    # PREVIEW
    # ══════════════════════════════════════════════════════

    def _update_preview(self):
        """Update the write preview based on current form values."""
        data = self._build_write_string()
        if data:
            self._lbl_preview_data.setText(data)
            self._lbl_preview_data.setStyleSheet(
                f"font-size: {_F_MED}px; color: {C.PRIMARY}; font-weight: bold;"
            )
        else:
            self._lbl_preview_data.setText("Select a product")
            self._lbl_preview_data.setStyleSheet(
                f"font-size: {_F_MED}px; color: {C.TEXT_MUTED};"
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
        color = self._input_color.text().strip().upper() or "NONE"

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
            self._show_result("No tag on reader — place tag first", False)
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
            f"background-color: {C.PRIMARY_DIM}; color: {C.BG_DARK};"
            f"border: none; border-radius: 8px;"
            f"font-size: {_F_BIG}px; font-weight: bold;"
            f"min-height: 48px; padding: 8px;"
        )
        QApplication.processEvents()

        # Write in a thread to avoid blocking UI
        def do_write():
            try:
                success = self.app.rfid.write_product_data(write_string)
                # Schedule UI update on main thread
                QTimer.singleShot(0, lambda: self._on_write_complete(
                    success, product, write_string
                ))
            except Exception as e:
                logger.error(f"Tag write error: {e}")
                QTimer.singleShot(0, lambda: self._on_write_complete(
                    False, product, write_string
                ))

        threading.Thread(target=do_write, daemon=True).start()

    def _on_write_complete(self, success: bool, product: dict, write_string: str):
        """Handle write result on main thread."""
        self._writing = False
        self._btn_write.setText("WRITE TAG")
        self._btn_write.setEnabled(True)
        self._btn_write.setStyleSheet(
            f"background-color: {C.PRIMARY}; color: {C.BG_DARK};"
            f"border: none; border-radius: 8px;"
            f"font-size: {_F_BIG}px; font-weight: bold;"
            f"min-height: 48px; padding: 8px;"
        )

        if success:
            self._tags_written += 1
            product_name = product.get("name", "Unknown")
            self._show_result(
                f"OK! Written: {product_name}\n{write_string}", True
            )

            # Register tag → product mapping in DB
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
            self._show_result("WRITE FAILED — try again", False)
            try:
                self.app.buzzer.play_pattern("error")
            except Exception:
                pass

        self._lbl_tags_written.setText(f"Tags written: {self._tags_written}")

    def _show_result(self, text: str, success: bool):
        """Update the result label."""
        color = C.SUCCESS if success else C.DANGER
        self._lbl_result.setText(text)
        self._lbl_result.setStyleSheet(
            f"font-size: {_F_MED}px; color: {color}; font-weight: bold;"
        )

    # Connect preview updates to input changes
    def showEvent(self, event):
        super().showEvent(event)
        self._input_batch.textChanged.connect(self._update_preview)
        self._input_color.textChanged.connect(self._update_preview)

    def hideEvent(self, event):
        super().hideEvent(event)
        try:
            self._input_batch.textChanged.disconnect(self._update_preview)
            self._input_color.textChanged.disconnect(self._update_preview)
        except Exception:
            pass
