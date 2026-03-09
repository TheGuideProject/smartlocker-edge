"""
System Monitor - Hardware health checks for Raspberry Pi.

Monitors CPU temperature, RAM usage, disk space, SD card health.
Raises alarms via AlarmManager when thresholds are exceeded.
Auto-resolves alarms when conditions return to normal.
"""

import os
import time
import logging
import threading
from typing import Dict, Any, Optional

logger = logging.getLogger("smartlocker.monitor")


class SystemMonitor:
    """Monitors RPi system health and raises alarms."""

    def __init__(self, alarm_manager):
        self.alarm_manager = alarm_manager
        self._thread = None
        self._running = False
        self._interval = 60  # Check every 60 seconds
        self._last_check = {}

    def start(self, interval_s: int = 60):
        """Start background monitoring."""
        self._interval = interval_s
        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="SystemMonitor",
        )
        self._thread.start()
        logger.info(f"System monitor started (interval: {interval_s}s)")

    def stop(self):
        """Stop background monitoring."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _monitor_loop(self):
        """Background loop that runs health checks periodically."""
        time.sleep(10)  # Initial delay to let system settle
        while self._running:
            try:
                self.check_all()
            except Exception as e:
                logger.error(f"Monitor check error: {e}")
            time.sleep(self._interval)

    def check_all(self) -> Dict[str, Any]:
        """Run all health checks. Returns status dict."""
        from core.error_codes import ErrorCode

        result = {}

        # CPU Temperature
        cpu_temp = self._get_cpu_temp()
        result["cpu_temp"] = cpu_temp
        if cpu_temp is not None:
            if cpu_temp >= 80:
                self.alarm_manager.raise_alarm(
                    ErrorCode.E020_CPU_OVERTEMP,
                    f"CPU at {cpu_temp:.1f}\u00b0C",
                    "system",
                )
            elif cpu_temp >= 70:
                self.alarm_manager.raise_alarm(
                    ErrorCode.E021_CPU_HIGH_TEMP,
                    f"CPU at {cpu_temp:.1f}\u00b0C",
                    "system",
                )
            else:
                # Clear temperature alarms if they were raised
                self.alarm_manager.resolve_by_code(
                    ErrorCode.E020_CPU_OVERTEMP, "system"
                )
                self.alarm_manager.resolve_by_code(
                    ErrorCode.E021_CPU_HIGH_TEMP, "system"
                )

        # Check CPU throttling
        throttled = self._check_throttling()
        result["cpu_throttled"] = throttled
        if throttled:
            self.alarm_manager.raise_alarm(
                ErrorCode.E022_CPU_THROTTLING,
                "CPU frequency limited",
                "system",
            )

        # RAM Usage
        ram_pct = self._get_ram_usage()
        result["ram_pct"] = ram_pct
        if ram_pct is not None:
            if ram_pct >= 90:
                self.alarm_manager.raise_alarm(
                    ErrorCode.E023_RAM_CRITICAL,
                    f"RAM at {ram_pct:.0f}%",
                    "system",
                )
            elif ram_pct >= 80:
                self.alarm_manager.raise_alarm(
                    ErrorCode.E024_RAM_HIGH,
                    f"RAM at {ram_pct:.0f}%",
                    "system",
                )
            else:
                self.alarm_manager.resolve_by_code(
                    ErrorCode.E023_RAM_CRITICAL, "system"
                )
                self.alarm_manager.resolve_by_code(
                    ErrorCode.E024_RAM_HIGH, "system"
                )

        # Disk Usage
        disk_pct = self._get_disk_usage()
        result["disk_pct"] = disk_pct
        if disk_pct is not None:
            if disk_pct >= 95:
                self.alarm_manager.raise_alarm(
                    ErrorCode.E025_DISK_FULL,
                    f"Disk at {disk_pct:.0f}%",
                    "system",
                )
            elif disk_pct >= 85:
                self.alarm_manager.raise_alarm(
                    ErrorCode.E026_DISK_HIGH,
                    f"Disk at {disk_pct:.0f}%",
                    "system",
                )
            else:
                self.alarm_manager.resolve_by_code(
                    ErrorCode.E025_DISK_FULL, "system"
                )
                self.alarm_manager.resolve_by_code(
                    ErrorCode.E026_DISK_HIGH, "system"
                )

        # SD Card health
        sd_ok = self._check_sd_health()
        result["sd_health"] = "ok" if sd_ok else "error"

        self._last_check = result
        return result

    def get_last_check(self) -> Dict[str, Any]:
        """Return results from the most recent health check."""
        return dict(self._last_check)

    # --- Platform-specific checks ---
    # Work on RPi, gracefully degrade on other platforms

    def _get_cpu_temp(self) -> Optional[float]:
        """Read CPU temperature. Works on RPi, returns None elsewhere."""
        # Try RPi thermal zone
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                return int(f.read().strip()) / 1000.0
        except (FileNotFoundError, ValueError, PermissionError):
            pass
        # Try vcgencmd (RPi specific)
        try:
            import subprocess
            result = subprocess.run(
                ["vcgencmd", "measure_temp"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Output: temp=45.6'C
                temp_str = (
                    result.stdout.strip()
                    .replace("temp=", "")
                    .replace("'C", "")
                )
                return float(temp_str)
        except (FileNotFoundError, ValueError):
            pass
        except Exception:
            pass
        return None

    def _check_throttling(self) -> bool:
        """Check if CPU is being throttled (RPi specific)."""
        try:
            import subprocess
            result = subprocess.run(
                ["vcgencmd", "get_throttled"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # throttled=0x0 means no throttling
                val = result.stdout.strip().split("=")[1]
                return int(val, 16) != 0
        except Exception:
            pass
        return False

    def _get_ram_usage(self) -> Optional[float]:
        """Get RAM usage percentage."""
        try:
            import psutil
            return psutil.virtual_memory().percent
        except ImportError:
            pass
        # Fallback: parse /proc/meminfo
        try:
            with open("/proc/meminfo", "r") as f:
                lines = f.readlines()
            mem = {}
            for line in lines:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = int(parts[1].strip().split()[0])
                    mem[key] = val
            total = mem.get("MemTotal", 1)
            available = mem.get("MemAvailable", 0)
            return ((total - available) / total) * 100
        except Exception:
            return None

    def _get_disk_usage(self) -> Optional[float]:
        """Get root partition disk usage percentage."""
        try:
            stat = os.statvfs("/")
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bfree * stat.f_frsize
            if total == 0:
                return None
            return ((total - free) / total) * 100
        except (AttributeError, OSError):
            # os.statvfs not available on Windows; fallback
            try:
                import shutil
                usage = shutil.disk_usage("/")
                if usage.total == 0:
                    return None
                return (usage.used / usage.total) * 100
            except Exception:
                return None

    def _check_sd_health(self) -> bool:
        """Basic SD card health check."""
        # Try writing a small test file
        try:
            test_path = "/tmp/.smartlocker_sd_test"
            with open(test_path, "w") as f:
                f.write("test")
            os.remove(test_path)
        except Exception:
            from core.error_codes import ErrorCode
            self.alarm_manager.raise_alarm(
                ErrorCode.E027_SD_CARD_ERROR,
                "Cannot write to filesystem",
                "system",
            )
            return False

        # Check if filesystem is read-only
        try:
            with open("/proc/mounts", "r") as f:
                for line in f:
                    if " / " in line and "ro," in line:
                        from core.error_codes import ErrorCode
                        self.alarm_manager.raise_alarm(
                            ErrorCode.E028_SD_CARD_READONLY,
                            "Root filesystem is read-only",
                            "system",
                        )
                        return False
        except Exception:
            pass

        return True
