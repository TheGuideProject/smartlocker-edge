"""
Hardware Worker Thread

Runs all hardware polling (RFID, weight, sensors) in a dedicated
background thread. Communicates with the UI via Qt signals.

This prevents the UI from freezing when serial devices are slow
(PN532 via CH340, Arduino via CH340, etc).
"""

import logging
import time
import threading
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal, QMutex

logger = logging.getLogger("smartlocker.hw_worker")


class HardwareWorker(QThread):
    """Background thread for all hardware polling.

    Signals emitted to UI (thread-safe via Qt signal/slot):
      - tag_detected(dict)      : RFID tag appeared
      - tag_removed(str)        : RFID tag UID removed
      - weight_changed(dict)    : weight reading updated
      - weight_alarm(dict)      : shelf weight alarm triggered
      - sensor_status(dict)     : periodic health status
      - event_created(object)   : inventory event for DB/sync
    """

    # Signals (UI connects to these)
    tag_detected = pyqtSignal(dict)
    tag_removed = pyqtSignal(str)
    weight_changed = pyqtSignal(dict)
    weight_alarm = pyqtSignal(dict)
    sensor_status = pyqtSignal(dict)
    event_created = pyqtSignal(object)

    def __init__(self, inventory_engine, poll_interval_ms: int = 500):
        super().__init__()
        self._engine = inventory_engine
        self._poll_interval_ms = poll_interval_ms
        self._running = False
        self._mutex = QMutex()

    def run(self):
        """Main polling loop — runs in background thread."""
        self._running = True
        logger.info("[HW Worker] Started")

        interval_s = self._poll_interval_ms / 1000.0

        while self._running:
            try:
                self._engine.poll()
            except Exception as e:
                logger.debug(f"[HW Worker] Poll error: {e}")

            # Emit periodic sensor status
            try:
                status = {
                    "rfid_healthy": getattr(self._engine, '_rfid_healthy', False),
                    "weight_ok": self._engine.weight.is_healthy() if hasattr(self._engine.weight, 'is_healthy') else False,
                    "timestamp": time.time(),
                }
                self.sensor_status.emit(status)
            except Exception:
                pass

            self.msleep(int(interval_s * 1000))

        logger.info("[HW Worker] Stopped")

    def stop(self):
        """Stop the worker thread."""
        self._running = False
        self.wait(3000)  # Wait up to 3s for thread to finish
