"""
Barcode Scanner Service — Always-on USB barcode input capture.

USB barcode scanners act as HID keyboard devices: they send characters
rapidly (< 50ms between keystrokes) followed by Enter.

This module provides a global Qt event filter that:
1. Detects rapid keyboard input (barcode scan vs. human typing)
2. Collects characters until Enter
3. Parses barcode data: PPG_CODE/BATCH/PRODUCT_NAME/COLOR
4. Emits a signal with the parsed product info
5. Looks up the product in local database

Works alongside RFID — if RFID is healthy, barcode is backup.
If RFID is down, barcode becomes primary identification.
"""

import time
import logging
from typing import Optional, Dict, Any

from PyQt6.QtCore import QObject, QEvent, pyqtSignal, QTimer
from PyQt6.QtGui import QKeyEvent

logger = logging.getLogger("smartlocker.barcode")

# Max time between keystrokes to be considered a barcode scan (ms)
SCAN_CHAR_TIMEOUT_MS = 80
# Min chars for a valid barcode
MIN_BARCODE_LENGTH = 5


class BarcodeScanEvent:
    """Parsed barcode scan result."""

    def __init__(self, raw_data: str):
        self.raw_data = raw_data.strip()
        self.ppg_code = ""
        self.batch_number = ""
        self.product_name = ""
        self.color = ""
        self.is_valid = False
        self._parse()

    def _parse(self):
        """Parse barcode format.

        Supported formats:
          - Short: SL-{PPG_CODE}-{BATCH}  (e.g. SL-616826-001)
          - Legacy: PPG_CODE/BATCH/PRODUCT_NAME/COLOR
          - Single value: treated as PPG code
        """
        raw = self.raw_data

        # Short format: SL-PPG_CODE-BATCH
        if raw.startswith("SL-") and raw.count("-") >= 2:
            parts = raw.split("-", 2)  # ['SL', 'PPG_CODE', 'BATCH']
            self.ppg_code = parts[1].strip()
            self.batch_number = parts[2].strip()
            self.is_valid = bool(self.ppg_code)
            return

        # Legacy format: PPG_CODE/BATCH/PRODUCT_NAME/COLOR
        parts = raw.split("/")
        if len(parts) >= 3:
            self.ppg_code = parts[0].strip()
            self.batch_number = parts[1].strip()
            self.product_name = parts[2].strip()
            if len(parts) >= 4:
                self.color = parts[3].strip()
            self.is_valid = bool(self.ppg_code and self.product_name)
            return

        # Single value — might be just a PPG code or tag UID
        self.ppg_code = raw
        self.is_valid = len(raw) >= MIN_BARCODE_LENGTH

    def __repr__(self):
        return (f"BarcodeScanEvent(ppg={self.ppg_code}, batch={self.batch_number}, "
                f"product={self.product_name}, color={self.color})")


class BarcodeScanner(QObject):
    """Global barcode scanner listener.

    Install as event filter on QApplication to capture all keyboard input.
    Emits barcode_scanned signal when a valid scan is detected.

    Usage:
        scanner = BarcodeScanner(app_window)
        QApplication.instance().installEventFilter(scanner)
        scanner.barcode_scanned.connect(my_handler)
    """

    # Signal emitted when a complete barcode is scanned
    barcode_scanned = pyqtSignal(object)  # BarcodeScanEvent

    def __init__(self, app_window):
        super().__init__()
        self._app = app_window
        self._buffer = ""
        self._last_key_time = 0.0
        self._scanning = False
        self._enabled = True

        # Timeout timer — if no key for SCAN_CHAR_TIMEOUT_MS, flush buffer
        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(self._on_timeout)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value
        if not value:
            self._reset()

    def eventFilter(self, obj, event):
        """Capture keyboard events to detect barcode scanner input."""
        if not self._enabled:
            return False

        if event.type() != QEvent.Type.KeyPress:
            return False

        key_event = event
        key = key_event.key()
        text = key_event.text()
        now = time.time() * 1000  # ms

        # Enter key — end of scan
        if key in (16777220, 16777221):  # Qt.Key.Key_Return, Qt.Key.Key_Enter
            if self._buffer and len(self._buffer) >= MIN_BARCODE_LENGTH:
                self._process_scan()
                return True  # Consume the Enter key
            else:
                self._reset()
                return False

        # Only printable characters
        if not text or not text.isprintable():
            return False

        # Check timing — is this rapid input (scanner) or human typing?
        time_since_last = now - self._last_key_time

        if self._buffer and time_since_last > SCAN_CHAR_TIMEOUT_MS:
            # Too slow — this is human typing, not a scanner
            self._reset()
            return False

        # Accumulate character
        self._buffer += text
        self._last_key_time = now
        self._scanning = True

        # Restart timeout timer
        self._timeout_timer.stop()
        self._timeout_timer.start(int(SCAN_CHAR_TIMEOUT_MS * 1.5))

        # Consume event if we're in scanning mode (don't pass to widgets)
        if len(self._buffer) > 2:
            return True

        return False

    def _process_scan(self):
        """Process completed barcode scan."""
        raw = self._buffer.strip()
        self._reset()

        if len(raw) < MIN_BARCODE_LENGTH:
            return

        logger.info(f"Barcode scanned: {raw}")
        scan = BarcodeScanEvent(raw)
        self.barcode_scanned.emit(scan)

    def _on_timeout(self):
        """Buffer timeout — not a barcode scan."""
        self._reset()

    def _reset(self):
        """Clear scan buffer."""
        self._buffer = ""
        self._scanning = False
        self._last_key_time = 0.0
        self._timeout_timer.stop()


def lookup_barcode_product(db, scan: BarcodeScanEvent) -> Optional[Dict[str, Any]]:
    """Look up a scanned barcode in the local database.

    Tries multiple strategies:
    1. Full barcode_data match in product_barcodes table
    2. PPG code match in product table
    3. Fallback: return barcode data as-is (always works for valid scans)

    NEVER returns None for a valid barcode — worst case returns raw data.
    """
    if not scan.is_valid:
        return None

    if not db:
        # No database — return raw barcode data
        return {
            "product_id": "",
            "product_name": scan.product_name or f"PPG-{scan.ppg_code}",
            "ppg_code": scan.ppg_code,
            "product_type": "",
            "batch_number": scan.batch_number,
            "color": scan.color,
            "match_type": "no_db",
        }

    # Strategy 1: Look up by full barcode data string
    try:
        result = db.get_barcode_product(scan.raw_data)
        if result:
            logger.info(f"Barcode matched (full): {result.get('product_name')}")
            return result
    except Exception as e:
        logger.debug(f"Barcode full lookup failed: {e}")

    # Strategy 2: Look up by PPG code in product table
    try:
        result = db.get_product_by_ppg_code(scan.ppg_code)
        if result:
            logger.info(f"Barcode matched (ppg_code): {result.get('name')}")
            return {
                "product_id": result.get("product_id") or result.get("id", ""),
                "product_name": result.get("name", ""),
                "ppg_code": result.get("ppg_code", ""),
                "product_type": result.get("product_type", ""),
                "batch_number": scan.batch_number,
                "color": scan.color,
                "match_type": "ppg_code",
            }
    except Exception as e:
        logger.debug(f"Barcode ppg_code lookup failed: {e}")

    # Strategy 3: ALWAYS return something for valid barcodes
    # Use whatever we parsed from the barcode itself
    logger.info(f"Barcode not in DB — using raw data: PPG={scan.ppg_code}")
    return {
        "product_id": "",
        "product_name": scan.product_name or f"PPG-{scan.ppg_code}",
        "ppg_code": scan.ppg_code,
        "product_type": "",
        "batch_number": scan.batch_number,
        "color": scan.color,
        "match_type": "barcode_only",
    }
