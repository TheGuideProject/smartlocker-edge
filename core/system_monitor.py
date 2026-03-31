"""
System Monitor - Hardware health checks for Raspberry Pi.

Monitors CPU temperature, RAM usage, disk space, SD card health,
NTP clock sync, and power supply voltage.
Raises alarms via AlarmManager when thresholds are exceeded.
Auto-resolves alarms when conditions return to normal.
Keeps a rolling history buffer for UI graphs (last 60 samples = 1 hour).
"""

import os
import time
import logging
import datetime
import threading
from collections import deque
from typing import Dict, Any, List, Optional

logger = logging.getLogger("smartlocker.monitor")

# History buffer size (60 samples @ 60s interval = 1 hour)
HISTORY_MAX = 60


class SystemMonitor:
    """Monitors RPi system health and raises alarms."""

    def __init__(self, alarm_manager):
        self.alarm_manager = alarm_manager
        self._thread = None
        self._running = False
        self._interval = 60  # Check every 60 seconds
        self._last_check: Dict[str, Any] = {}
        self._history: deque = deque(maxlen=HISTORY_MAX)

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
        time.sleep(2)  # Short delay to let system settle
        while self._running:
            try:
                self.check_all()
            except Exception as e:
                logger.error(f"Monitor check error: {e}")
            time.sleep(self._interval)

    def force_check(self) -> Optional[Dict[str, Any]]:
        """Run an immediate health check (called from UI thread).
        Safe to call — individual checks handle their own exceptions."""
        try:
            return self.check_all()
        except Exception as e:
            logger.error(f"Force check error: {e}")
            return None

    def check_all(self) -> Dict[str, Any]:
        """Run all health checks. Returns status dict."""
        from core.error_codes import ErrorCode

        result = {
            "timestamp": time.time(),
        }

        # ── CPU Temperature ──────────────────────────────────
        cpu_temp = self._get_cpu_temp()
        result["cpu_temp"] = cpu_temp
        if cpu_temp is not None:
            if cpu_temp >= 80:
                self.alarm_manager.raise_alarm(
                    ErrorCode.E020_CPU_OVERTEMP,
                    f"CPU at {cpu_temp:.1f}°C",
                    "system",
                )
            elif cpu_temp >= 70:
                self.alarm_manager.raise_alarm(
                    ErrorCode.E021_CPU_HIGH_TEMP,
                    f"CPU at {cpu_temp:.1f}°C",
                    "system",
                )
            else:
                self.alarm_manager.resolve_by_code(
                    ErrorCode.E020_CPU_OVERTEMP, "system"
                )
                self.alarm_manager.resolve_by_code(
                    ErrorCode.E021_CPU_HIGH_TEMP, "system"
                )

        # ── Throttling + Power (vcgencmd bitmask) ────────────
        throttle_bits = self._get_throttle_bits()
        result["throttle_bits"] = throttle_bits

        # Under-voltage: bit 0 (now) or bit 16 (since boot)
        under_voltage = bool(throttle_bits & 0x50001)
        result["under_voltage"] = under_voltage
        if under_voltage:
            self.alarm_manager.raise_alarm(
                ErrorCode.E030_POWER_UNSTABLE,
                f"Under-voltage detected (0x{throttle_bits:x})",
                "system",
            )
        else:
            self.alarm_manager.resolve_by_code(
                ErrorCode.E030_POWER_UNSTABLE, "system"
            )

        # CPU throttled: bit 2 (now) or bit 18 (since boot)
        cpu_throttled = bool(throttle_bits & 0x40004)
        result["cpu_throttled"] = cpu_throttled
        if cpu_throttled:
            self.alarm_manager.raise_alarm(
                ErrorCode.E022_CPU_THROTTLING,
                f"CPU throttled (0x{throttle_bits:x})",
                "system",
            )
        else:
            self.alarm_manager.resolve_by_code(
                ErrorCode.E022_CPU_THROTTLING, "system"
            )

        # ── RAM Usage ────────────────────────────────────────
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

        # ── Disk Usage ───────────────────────────────────────
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

        # ── SD Card Health ───────────────────────────────────
        sd_ok = self._check_sd_health()
        result["sd_health"] = "ok" if sd_ok else "error"

        # ── Clock Sync (NTP) ─────────────────────────────────
        clock_ok = self._check_clock_sync()
        result["clock_sync"] = clock_ok
        if not clock_ok:
            self.alarm_manager.raise_alarm(
                ErrorCode.E029_SYSTEM_CLOCK_ERROR,
                "NTP not synchronized",
                "system",
            )
        else:
            self.alarm_manager.resolve_by_code(
                ErrorCode.E029_SYSTEM_CLOCK_ERROR, "system"
            )

        # ── CPU Usage (%) ────────────────────────────────
        cpu_pct = self._get_cpu_usage()
        result["cpu_pct"] = cpu_pct

        # ── Network info ────────────────────────────────
        net_info = self._get_network_info()
        result["network"] = net_info

        # ── Save to history and cache ────────────────────────
        self._last_check = result
        self._history.append(result)

        return result

    def get_last_check(self) -> Dict[str, Any]:
        """Return results from the most recent health check."""
        return dict(self._last_check)

    def get_metrics(self) -> Optional[Dict[str, Any]]:
        """Alias for get_last_check — used by UI SystemHealthScreen."""
        if not self._last_check:
            return None
        return dict(self._last_check)

    def get_history(self) -> List[Dict[str, Any]]:
        """Return the rolling history buffer (up to 60 samples)."""
        return list(self._history)

    # ================================================================
    # Platform-specific checks
    # Work on RPi, gracefully degrade on other platforms
    # ================================================================

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

    def _get_throttle_bits(self) -> int:
        """Get RPi throttle bitmask via vcgencmd. Returns 0 if unavailable.

        Bit meanings:
            0: Under-voltage detected (now)
            1: Arm frequency capped (now)
            2: Currently throttled (now)
            3: Soft temperature limit active
           16: Under-voltage has occurred (since boot)
           17: Arm frequency capped has occurred
           18: Throttling has occurred
           19: Soft temperature limit has occurred
        """
        try:
            import subprocess
            result = subprocess.run(
                ["vcgencmd", "get_throttled"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                val = result.stdout.strip().split("=")[1]
                return int(val, 16)
        except Exception:
            pass
        return 0

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

    def _check_clock_sync(self) -> bool:
        """Check if system clock is NTP synchronized.

        Uses timedatectl on Linux, falls back to year check on other platforms.
        """
        # Try timedatectl (systemd Linux)
        try:
            import subprocess
            result = subprocess.run(
                ["timedatectl", "show", "--property=NTPSynchronized"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return "yes" in result.stdout.strip().lower()
        except (FileNotFoundError, OSError):
            pass
        except Exception:
            pass

        # Fallback: check if year is reasonable (for Windows / test mode)
        return datetime.datetime.now().year >= 2025

    def _get_cpu_usage(self) -> Optional[float]:
        """Get CPU usage percentage."""
        try:
            import psutil
            return psutil.cpu_percent(interval=0.5)
        except ImportError:
            pass
        # Fallback: parse /proc/stat
        try:
            with open("/proc/stat", "r") as f:
                line = f.readline()
            parts = line.split()
            idle = int(parts[4])
            total = sum(int(p) for p in parts[1:])
            if not hasattr(self, "_prev_cpu"):
                self._prev_cpu = (idle, total)
                return 0.0
            prev_idle, prev_total = self._prev_cpu
            self._prev_cpu = (idle, total)
            d_idle = idle - prev_idle
            d_total = total - prev_total
            if d_total == 0:
                return 0.0
            return ((d_total - d_idle) / d_total) * 100
        except Exception:
            return None

    def _get_network_info(self) -> Dict[str, Any]:
        """Get basic network connectivity info."""
        info = {"connected": False, "ip": None, "interface": None}
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            s.connect(("8.8.8.8", 53))
            ip = s.getsockname()[0]
            s.close()
            info["connected"] = True
            info["ip"] = ip
        except Exception:
            pass

        # Try to find active interface
        try:
            import psutil
            for name, addrs in psutil.net_if_addrs().items():
                if name in ("lo", "localhost"):
                    continue
                for addr in addrs:
                    if addr.family == socket.AF_INET and addr.address == info.get("ip"):
                        info["interface"] = name
                        break
        except Exception:
            pass

        return info
