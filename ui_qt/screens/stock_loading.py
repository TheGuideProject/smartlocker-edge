"""
SmartLocker Stock Loading Screen — LOAD STOCK

Dedicated screen for loading new paint cans onto the shelf.
Flow: RFID detected → 8s stabilization → weight saved → success → idle.
One can at a time.

Weight baseline: keeps a rolling buffer of recent shelf weights (last 4s).
When RFID fires, uses the OLDEST reading as baseline (before can was placed),
since the weight sensor updates faster than RFID.
"""

import logging
from collections import deque

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel,
    QFrame, QStackedWidget, QProgressBar,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from ui_qt.theme import C, F, S
from ui_qt.icons import Icon, icon_badge, screen_header
from core.event_types import Event, EventType

logger = logging.getLogger("smartlocker.ui.stock_loading")

# States
_IDLE = 0
_STABILIZING = 1
_SUCCESS = 2

# Stabilization time in seconds
_STABILIZE_SECONDS = 8


class StockLoadingScreen(QWidget):
    """Screen for loading new cans onto the shelf via RFID + weight."""

    # Thread-safe signal: inventory engine callback (HW thread) → main thread
    _can_detected_signal = pyqtSignal(object)

    def __init__(self, app):
        super().__init__()
        self.app = app

        # State
        self._countdown = 0
        self._weight_before = 0.0
        self._current_tag_data = None
        self._busy = False

        # Rolling weight buffer: stores last 8 readings (4 seconds at 500ms).
        # When RFID triggers, the oldest value is the weight BEFORE the can
        # was placed (weight sensor updates every 500ms, RFID every 2000ms).
        self._weight_history = deque(maxlen=8)

        # Timers
        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick)

        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._countdown_tick)

        # Connect signal
        self._can_detected_signal.connect(self._handle_can_detected_ui)

        self._build_ui()

    # ── UI Construction ──────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header, _ = screen_header(self.app, "LOAD STOCK", Icon.ADD, C.SUCCESS)
        root.addWidget(header)

        # Stacked pages
        self._pages = QStackedWidget()
        root.addWidget(self._pages, 1)

        self._pages.addWidget(self._build_idle_page())       # 0
        self._pages.addWidget(self._build_stabilize_page())  # 1
        self._pages.addWidget(self._build_success_page())    # 2

    def _build_idle_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(S.PAD * 2, S.PAD * 2, S.PAD * 2, S.PAD * 2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Big icon
        badge = icon_badge(Icon.ADD, C.SUCCESS_BG, C.SUCCESS, 64)
        layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(S.PAD)

        # Instructions
        lbl = QLabel("Place the can on the shelf")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color: {C.TEXT}; font-size: {F.H1}px; font-weight: bold;")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        sub = QLabel("The system automatically detects\nthe product via RFID")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"color: {C.TEXT_SEC}; font-size: {F.BODY}px;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        layout.addSpacing(S.PAD * 2)

        # Current shelf weight
        self._weight_label = QLabel("Shelf weight: --")
        self._weight_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._weight_label.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-size: {F.SMALL}px;"
        )
        layout.addWidget(self._weight_label)

        layout.addStretch(1)
        return page

    def _build_stabilize_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background-color: {C.WARNING_BG};")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(S.PAD * 2, S.PAD, S.PAD * 2, S.PAD * 2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Warning icon
        badge = icon_badge(Icon.WARN, C.WARNING_BG, C.WARNING, 56)
        layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(S.GAP)

        # Title
        title = QLabel("INVENTORY UPDATE")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color: {C.WARNING}; font-size: {F.H1}px; font-weight: bold;"
        )
        layout.addWidget(title)

        subtitle = QLabel("DO NOT TOUCH THE SHELF!")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(
            f"color: {C.WARNING}; font-size: {F.H2}px; font-weight: bold;"
        )
        layout.addWidget(subtitle)

        layout.addSpacing(S.PAD)

        # Countdown number
        self._countdown_label = QLabel(str(_STABILIZE_SECONDS))
        self._countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._countdown_label.setStyleSheet(
            f"color: {C.TEXT}; font-size: {F.HERO + 12}px; font-weight: bold;"
        )
        layout.addWidget(self._countdown_label)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setRange(0, _STABILIZE_SECONDS)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(8)
        self._progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: {C.BG_CARD};
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {C.WARNING};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self._progress)

        layout.addSpacing(S.PAD)

        # Product info card
        self._product_card = QFrame()
        self._product_card.setStyleSheet(
            f"background-color: {C.BG_CARD}; border: 1px solid {C.BORDER};"
            f"border-radius: {S.RADIUS}px; padding: {S.PAD}px;"
        )
        card_layout = QVBoxLayout(self._product_card)
        card_layout.setSpacing(2)

        self._stab_product_name = QLabel("")
        self._stab_product_name.setStyleSheet(
            f"color: {C.TEXT}; font-size: {F.H2}px; font-weight: bold; border: none;"
        )
        card_layout.addWidget(self._stab_product_name)

        self._stab_product_details = QLabel("")
        self._stab_product_details.setStyleSheet(
            f"color: {C.TEXT_SEC}; font-size: {F.SMALL}px; border: none;"
        )
        card_layout.addWidget(self._stab_product_details)

        layout.addWidget(self._product_card)
        layout.addStretch(1)
        return page

    def _build_success_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background-color: {C.SUCCESS_BG};")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(S.PAD * 2, S.PAD * 2, S.PAD * 2, S.PAD * 2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Check icon
        badge = icon_badge(Icon.OK, C.SUCCESS_BG, C.SUCCESS, 64)
        layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(S.PAD)

        self._success_title = QLabel("LOADED")
        self._success_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._success_title.setStyleSheet(
            f"color: {C.SUCCESS}; font-size: {F.H1}px; font-weight: bold;"
        )
        layout.addWidget(self._success_title)

        self._success_weight = QLabel("")
        self._success_weight.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._success_weight.setStyleSheet(
            f"color: {C.TEXT}; font-size: {F.HERO}px; font-weight: bold;"
        )
        layout.addWidget(self._success_weight)

        self._success_product = QLabel("")
        self._success_product.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._success_product.setStyleSheet(
            f"color: {C.TEXT_SEC}; font-size: {F.BODY}px;"
        )
        self._success_product.setWordWrap(True)
        layout.addWidget(self._success_product)

        layout.addStretch(1)
        return page

    # ── Lifecycle ────────────────────────────────────────────

    def on_enter(self):
        """Activate stock loading mode."""
        self._busy = False
        self._weight_history.clear()
        self._pages.setCurrentIndex(_IDLE)

        # Set engine flag + callback
        self.app.inventory_engine.stock_loading_mode = True
        self.app.inventory_engine.on_stock_can_detected = self._on_can_detected_hw

        # Start weight display timer
        self._tick_timer.start(500)
        self._tick()

        logger.info("Stock loading screen entered")

    def on_leave(self):
        """Deactivate stock loading mode."""
        self._tick_timer.stop()
        self._countdown_timer.stop()
        self._busy = False

        # Clear engine flag + callback
        self.app.inventory_engine.stock_loading_mode = False
        self.app.inventory_engine.on_stock_can_detected = None

        logger.info("Stock loading screen left")

    # ── HW Thread → Main Thread ──────────────────────────────

    def _on_can_detected_hw(self, data: dict):
        """Called from HW worker thread. Emit signal to main thread."""
        self._can_detected_signal.emit(data)

    def _handle_can_detected_ui(self, data: dict):
        """Handle can detection on the main (UI) thread."""
        if self._busy:
            logger.info("Stock loading: ignoring tag while busy (stabilizing/success)")
            return

        tag_data = data
        product_name = tag_data.get("product_name", "")
        lot = tag_data.get("lot_number", "")
        shelf_id = tag_data.get("shelf_id", "shelf1")

        if not product_name:
            product_name = f"Tag: {tag_data.get('tag_uid', '???')}"

        logger.info(
            f"Stock loading: can detected - {product_name}, lot={lot}, "
            f"shelf={shelf_id}"
        )

        # Use OLDEST weight in the buffer as baseline.
        # The weight sensor updates every 500ms, RFID every 2s.
        # By the time RFID fires, recent weight readings already include
        # the can. The oldest reading (3-4s ago) is the clean baseline.
        if len(self._weight_history) >= 2:
            self._weight_before = self._weight_history[0]
        else:
            self._weight_before = self.app.inventory_engine.get_shelf_weight_baseline(
                shelf_id
            )

        logger.info(f"Stock loading: baseline weight = {self._weight_before:.0f}g "
                     f"(buffer size={len(self._weight_history)})")

        self._current_tag_data = tag_data
        self._busy = True

        # Update stabilization page content
        self._stab_product_name.setText(product_name)
        details = []
        if lot:
            details.append(f"Batch: {lot}")
        if tag_data.get("product_id"):
            details.append(f"ID: {tag_data['product_id'][:12]}...")
        self._stab_product_details.setText("  |  ".join(details) if details else "")

        # Start countdown
        self._countdown = _STABILIZE_SECONDS
        self._countdown_label.setText(str(_STABILIZE_SECONDS))
        self._progress.setValue(0)
        self._pages.setCurrentIndex(_STABILIZING)
        self._countdown_timer.start(1000)

    # ── Countdown ────────────────────────────────────────────

    def _countdown_tick(self):
        self._countdown -= 1
        self._countdown_label.setText(str(max(0, self._countdown)))
        self._progress.setValue(_STABILIZE_SECONDS - self._countdown)

        if self._countdown <= 0:
            self._countdown_timer.stop()
            self._finalize_loading()

    def _finalize_loading(self):
        """Read stable weight, calculate delta, save to DB."""
        tag = self._current_tag_data
        if not tag:
            self._return_to_idle()
            return

        shelf_id = tag.get("shelf_id", "shelf1")

        # Read weight after stabilization using the correct channel
        weight_channel = self.app.inventory_engine.get_weight_channel_for_shelf(
            shelf_id
        )
        if not weight_channel:
            weight_channel = shelf_id  # fallback

        weight_after = 0.0
        try:
            reading = self.app.weight.read_weight(weight_channel)
            weight_after = reading.grams
        except Exception as e:
            logger.error(f"Stock loading: weight read failed: {e}")

        net_weight_g = weight_after - self._weight_before
        product_name = tag.get("product_name", "Unknown")
        product_id = tag.get("product_id", "")
        lot = tag.get("lot_number", "")
        slot_id = tag.get("slot_id", "")

        logger.info(
            f"Stock loading: baseline={self._weight_before:.0f}g, "
            f"after={weight_after:.0f}g, net={net_weight_g:.0f}g"
        )

        # Accept if delta > 100g (demo: any reasonable increase)
        if net_weight_g < 100:
            logger.warning(
                f"Stock loading: net weight too low ({net_weight_g:.0f}g), "
                f"saving anyway for demo"
            )
            # For demo: still save if weight_after > 0 (single-can baseline)
            if weight_after > 100:
                net_weight_g = weight_after  # use absolute weight as fallback

        if net_weight_g <= 0:
            logger.warning("Stock loading: no weight detected, skipping save")
            self._show_error()
            return

        # ── Save to DB ──

        # 1. Resolve product info for vessel stock update
        product_info = {
            "product_id": product_id,
            "product_name": product_name,
            "ppg_code": tag.get("ppg_code", ""),
            "product_type": "base_paint",
            "density_g_per_ml": 1.3,
        }

        # Try to get accurate product info from catalog
        if self.app.db:
            prod = None
            if product_id:
                prod = self.app.db.get_product_by_id(product_id)
            if not prod and product_name:
                prod = self.app.db.get_product_by_name(product_name)
            if prod:
                product_info["product_id"] = prod.get("product_id", product_id)
                product_info["product_type"] = prod.get("product_type", "base_paint")
                product_info["density_g_per_ml"] = float(
                    prod.get("density_g_per_ml", 1.3) or 1.3
                )
                product_info["colors_json"] = prod.get("colors_json", "[]")

        # 2. Update vessel stock
        try:
            self.app.db.update_vessel_stock_from_barcode(
                product_info, action="load", weight_g=net_weight_g
            )
            logger.info(
                f"Stock loading: vessel_stock updated - "
                f"{product_name} +{net_weight_g:.0f}g"
            )
        except Exception as e:
            logger.error(f"Stock loading: DB update failed: {e}")

        # 3. Publish event (single CAN_PLACED with source=stock_loading)
        try:
            from config import settings
            event = Event(
                event_type=EventType.CAN_PLACED,
                device_id=settings.DEVICE_ID,
                shelf_id=shelf_id,
                slot_id=slot_id,
                tag_id=tag.get("tag_uid", ""),
                data={
                    "product_id": product_info.get("product_id", product_id),
                    "product_name": product_name,
                    "ppg_code": product_info.get("ppg_code", ""),
                    "batch_number": lot,
                    "source": "stock_loading",
                    "weight_g": round(net_weight_g, 1),
                    "weight_before_g": round(self._weight_before, 1),
                    "weight_after_g": round(weight_after, 1),
                    "slot_id": slot_id,
                },
                confirmation="confirmed",
            )
            self.app.event_bus.publish(event)
        except Exception as e:
            logger.error(f"Stock loading: event publish failed: {e}")

        # 4. Buzzer + LED feedback
        try:
            from hal.interfaces import BuzzerPattern, LEDColor, LEDPattern
            self.app.buzzer.play(BuzzerPattern.CONFIRM)
            if slot_id:
                self.app.led.set_slot(slot_id, LEDColor.GREEN, LEDPattern.SOLID)
        except Exception as e:
            logger.debug(f"Stock loading: feedback failed: {e}")

        # 5. Show success
        weight_kg = net_weight_g / 1000
        density = float(product_info.get("density_g_per_ml", 1.3) or 1.3)
        liters = round(net_weight_g / (density * 1000), 2)
        self._success_title.setText("LOADED")
        self._success_title.setStyleSheet(
            f"color: {C.SUCCESS}; font-size: {F.H1}px; font-weight: bold;"
        )
        self._success_weight.setText(f"{weight_kg:.1f} kg  ({liters:.2f} L)")
        self._success_product.setText(
            f"{product_name}" + (f"\nBatch: {lot}" if lot else "")
        )
        self._pages.setCurrentIndex(_SUCCESS)

        # 6. Clear weight buffer so next load gets a fresh baseline
        #    (which will include THIS can's weight)
        self._weight_history.clear()

        # Auto-return to idle after 3 seconds
        QTimer.singleShot(3000, self._return_to_idle)

    def _show_error(self):
        """Show brief error then return to idle."""
        self._success_title.setText("ERROR")
        self._success_weight.setText("No weight")
        self._success_product.setText("No weight change detected")
        self._success_title.setStyleSheet(
            f"color: {C.DANGER}; font-size: {F.H1}px; font-weight: bold;"
        )
        self._pages.setCurrentIndex(_SUCCESS)
        # Clear buffer for retry
        self._weight_history.clear()
        QTimer.singleShot(3000, self._return_to_idle)

    def _return_to_idle(self):
        """Reset to waiting state."""
        # Save slot_id before clearing tag data (for LED clear)
        slot_id = None
        if self._current_tag_data:
            slot_id = self._current_tag_data.get("slot_id")

        self._busy = False
        self._current_tag_data = None
        self._countdown_timer.stop()

        # Clear LED
        try:
            if slot_id:
                self.app.led.clear_slot(slot_id)
        except Exception:
            pass

        self._pages.setCurrentIndex(_IDLE)

    # ── Periodic tick (weight display + buffer in idle) ──────

    def _tick(self):
        """Update shelf weight display and maintain weight buffer."""
        try:
            weight = self.app.inventory_engine.get_shelf_weight_baseline()
            # Only buffer weights while in IDLE (not during stabilization)
            if self._pages.currentIndex() == _IDLE:
                self._weight_history.append(weight)
                self._weight_label.setText(f"Shelf weight: {weight:.0f} g")
        except Exception:
            if self._pages.currentIndex() == _IDLE:
                self._weight_label.setText("Shelf weight: --")
