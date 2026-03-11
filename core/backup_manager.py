"""
Backup Manager

Daemon thread that periodically creates SQLite backups using the
sqlite3.backup() API, rotates old copies, and optionally copies
to USB media for off-site safety.
"""

import logging
import os
import shutil
import sqlite3
import threading
import time
from datetime import datetime
from typing import Optional, List, Dict, Any

from config import settings

logger = logging.getLogger("smartlocker.backup")


class BackupManager:
    """
    Manages periodic SQLite database backups.

    Features:
      - Uses sqlite3.backup() for hot, consistent backups
      - Rotates old copies (keeps max N)
      - Tries to copy latest backup to USB if present
      - Daemon thread that runs in the background

    Usage:
        bm = BackupManager(db_path="data/smartlocker.db")
        bm.start()
        ...
        bm.stop()
    """

    # Common USB mount points on Raspberry Pi / Linux
    USB_MOUNT_POINTS = [
        "/media/usb0",
        "/media/usb1",
        "/media/usb",
        "/mnt/usb",
    ]

    def __init__(
        self,
        db_path: Optional[str] = None,
        backup_dir: Optional[str] = None,
        interval_h: Optional[float] = None,
        max_copies: Optional[int] = None,
    ):
        self.db_path = db_path or settings.DB_PATH
        self.backup_dir = backup_dir or settings.BACKUP_DIR
        self.interval_h = interval_h or settings.BACKUP_INTERVAL_H
        self.max_copies = max_copies or settings.BACKUP_MAX_COPIES

        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._last_backup_time = 0.0
        self._last_backup_path: Optional[str] = None
        self._backup_count = 0
        self._last_error: Optional[str] = None

    def start(self) -> None:
        """Start the backup daemon thread."""
        if self._running:
            logger.warning("BackupManager already running")
            return

        os.makedirs(self.backup_dir, exist_ok=True)

        self._running = True
        self._thread = threading.Thread(
            target=self._backup_loop,
            name="BackupManager",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            f"BackupManager started: every {self.interval_h}h, "
            f"max {self.max_copies} copies, dir={self.backup_dir}"
        )

    def stop(self) -> None:
        """Stop the backup daemon thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None
        logger.info("BackupManager stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    # ============================================================
    # MAIN LOOP
    # ============================================================

    def _backup_loop(self) -> None:
        """Main backup loop (runs in background daemon thread)."""
        # Initial backup shortly after start (30 seconds)
        time.sleep(30)
        if self._running:
            self._do_backup()

        while self._running:
            try:
                now = time.time()
                interval_s = self.interval_h * 3600

                if now - self._last_backup_time >= interval_s:
                    self._do_backup()

                # Sleep in short intervals so we can stop quickly
                time.sleep(60)
            except Exception as e:
                logger.error(f"Backup loop error: {e}")
                self._last_error = str(e)
                time.sleep(300)  # Back off on error

    # ============================================================
    # BACKUP OPERATIONS
    # ============================================================

    def _do_backup(self) -> bool:
        """Create a backup using sqlite3.backup() API."""
        try:
            if not os.path.exists(self.db_path):
                logger.warning(f"Database file not found: {self.db_path}")
                return False

            # Generate timestamped filename
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"smartlocker_backup_{ts}.db"
            backup_path = os.path.join(self.backup_dir, backup_filename)

            # Use sqlite3.backup() for a safe hot backup
            src_conn = sqlite3.connect(self.db_path)
            dst_conn = sqlite3.connect(backup_path)
            try:
                src_conn.backup(dst_conn)
                logger.info(f"Backup created: {backup_path}")
            finally:
                dst_conn.close()
                src_conn.close()

            self._last_backup_time = time.time()
            self._last_backup_path = backup_path
            self._backup_count += 1
            self._last_error = None

            # Rotate old backups
            self._rotate_backups()

            # Try to copy to USB
            self._copy_to_usb(backup_path)

            return True

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            self._last_error = str(e)
            return False

    def _rotate_backups(self) -> None:
        """Remove oldest backups to keep only max_copies."""
        try:
            backups = self._list_backups()
            if len(backups) <= self.max_copies:
                return

            # Sort by modification time (oldest first)
            backups.sort(key=lambda p: os.path.getmtime(p))

            # Remove oldest until we're at max_copies
            to_remove = backups[: len(backups) - self.max_copies]
            for path in to_remove:
                os.remove(path)
                logger.info(f"Rotated old backup: {os.path.basename(path)}")

        except Exception as e:
            logger.warning(f"Backup rotation error: {e}")

    def _list_backups(self) -> List[str]:
        """List all backup files in the backup directory."""
        if not os.path.exists(self.backup_dir):
            return []
        return [
            os.path.join(self.backup_dir, f)
            for f in os.listdir(self.backup_dir)
            if f.startswith("smartlocker_backup_") and f.endswith(".db")
        ]

    def _copy_to_usb(self, backup_path: str) -> bool:
        """Try to copy the backup to a USB drive if one is mounted."""
        for mount in self.USB_MOUNT_POINTS:
            if os.path.isdir(mount):
                try:
                    usb_backup_dir = os.path.join(mount, "smartlocker_backups")
                    os.makedirs(usb_backup_dir, exist_ok=True)
                    dest = os.path.join(usb_backup_dir, os.path.basename(backup_path))
                    shutil.copy2(backup_path, dest)
                    logger.info(f"Backup copied to USB: {dest}")
                    return True
                except Exception as e:
                    logger.debug(f"USB copy to {mount} failed: {e}")
        return False

    # ============================================================
    # STATUS / INFO
    # ============================================================

    def get_backup_info(self) -> Dict[str, Any]:
        """Get backup status for UI display."""
        backups = self._list_backups()
        latest_size = 0
        if self._last_backup_path and os.path.exists(self._last_backup_path):
            latest_size = os.path.getsize(self._last_backup_path)

        return {
            "is_running": self._running,
            "interval_h": self.interval_h,
            "max_copies": self.max_copies,
            "backup_dir": self.backup_dir,
            "backup_count": len(backups),
            "total_backups_created": self._backup_count,
            "last_backup_time": self._last_backup_time,
            "last_backup_path": self._last_backup_path,
            "last_backup_size_bytes": latest_size,
            "last_error": self._last_error,
        }
