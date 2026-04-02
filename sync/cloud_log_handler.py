"""
Cloud Log Handler — Buffers application log lines and uploads them
to the cloud periodically for remote debugging.

Usage (in app.py or main.py, after cloud_client is created):
    from sync.cloud_log_handler import CloudLogHandler
    handler = CloudLogHandler(cloud_client, flush_interval=60, max_buffer=200)
    logging.getLogger("smartlocker").addHandler(handler)
    # handler.stop() on shutdown
"""

import time
import logging
import threading
from datetime import datetime, timezone
from typing import List, Dict, Optional


class CloudLogHandler(logging.Handler):
    """
    Logging handler that buffers log records and periodically uploads
    them to the cloud via cloud_client.upload_device_logs().

    Only captures WARNING+ by default (configurable via level).
    Buffer is capped at max_buffer lines — oldest lines are dropped
    when the buffer is full.
    """

    def __init__(
        self,
        cloud_client,
        flush_interval: int = 60,
        max_buffer: int = 200,
        level: int = logging.WARNING,
    ):
        super().__init__(level)
        self._client = cloud_client
        self._flush_interval = flush_interval
        self._max_buffer = max_buffer
        self._buffer: List[Dict] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start the background flush thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._flush_loop, daemon=True, name="cloud-log-sync"
        )
        self._thread.start()

    def stop(self):
        """Stop the flush thread and do a final flush."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        # Final flush
        self._flush()

    def emit(self, record: logging.LogRecord):
        """Buffer a log record (called by logging framework)."""
        try:
            entry = {
                "timestamp": datetime.fromtimestamp(
                    record.created, tz=timezone.utc
                ).isoformat(),
                "level": record.levelname,
                "logger_name": record.name,
                "message": self.format(record)[:2000],
            }
            with self._lock:
                self._buffer.append(entry)
                # Drop oldest if buffer full
                if len(self._buffer) > self._max_buffer:
                    self._buffer = self._buffer[-self._max_buffer:]
        except Exception:
            pass  # Never let logging handler crash the app

    def _flush_loop(self):
        """Background thread: flush buffer every flush_interval seconds."""
        while self._running:
            time.sleep(self._flush_interval)
            self._flush()

    def _flush(self):
        """Upload buffered logs to cloud and clear buffer."""
        with self._lock:
            if not self._buffer:
                return
            batch = list(self._buffer)
            self._buffer.clear()

        try:
            self._client.upload_device_logs(batch)
        except Exception:
            # Put logs back on failure (up to max_buffer)
            with self._lock:
                self._buffer = batch + self._buffer
                if len(self._buffer) > self._max_buffer:
                    self._buffer = self._buffer[-self._max_buffer:]
