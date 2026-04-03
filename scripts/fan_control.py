#!/usr/bin/env python3
"""
SmartLocker Aggressive Fan Control — PWM fan curve for Raspberry Pi 5.

Uses /sys/class/hwmon/hwmonN/pwm1 where name == "pwmfan".
This is the verified working path on this RPi5 hardware.

Curve:
  < 45C  → OFF (0%)
  45-50C → 25%  (spin-up)
  50-55C → 40%
  55-60C → 60%
  60-65C → 80%
  65-70C → 90%
  >= 70C → 100% (full blast)

Reads CPU temperature every 3 seconds and adjusts fan PWM.

Usage:
  sudo python3 fan_control.py          # Run in foreground
  sudo python3 fan_control.py --daemon  # Run as daemon

Install as systemd service:
  sudo cp smartlocker-fan.service /etc/systemd/system/
  sudo systemctl enable smartlocker-fan
  sudo systemctl start smartlocker-fan
"""

import time
import sys
import os
import signal
import logging

log = logging.getLogger("smartlocker.fan")

# ── Configuration ──────────────────────────────────────
POLL_INTERVAL_S = 3       # Check temperature every 3 seconds
HYSTERESIS_C = 2.0        # Don't flap: need 2C drop to reduce speed

# Aggressive fan curve: (temp_threshold_C, fan_speed_pct)
# Fan starts at 45C, full speed at 70C
FAN_CURVE = [
    (70, 100),
    (65,  90),
    (60,  80),
    (55,  60),
    (50,  40),
    (45,  25),
]
# Below 45C (minus hysteresis) → off
FAN_OFF_TEMP = 43  # 45 - 2 hysteresis


def get_cpu_temp() -> float:
    """Read CPU temperature in Celsius."""
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            return int(f.read().strip()) / 1000.0
    except Exception:
        pass
    # Fallback: vcgencmd
    try:
        import subprocess
        result = subprocess.run(
            ["vcgencmd", "measure_temp"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return float(result.stdout.strip().replace("temp=", "").replace("'C", ""))
    except Exception:
        pass
    return 0.0


def find_pwmfan_hwmon() -> dict | None:
    """Find the hwmon device named 'pwmfan' and return its paths.

    Scans /sys/class/hwmon/hwmonN/ for name == 'pwmfan'.
    Returns dict with pwm1, pwm1_enable, fan1_input paths, or None.
    """
    hwmon_base = "/sys/class/hwmon"
    if not os.path.isdir(hwmon_base):
        return None

    for entry in sorted(os.listdir(hwmon_base)):
        hwmon_dir = os.path.join(hwmon_base, entry)
        name_file = os.path.join(hwmon_dir, "name")
        if not os.path.isfile(name_file):
            continue
        try:
            with open(name_file, "r") as f:
                name = f.read().strip()
        except Exception:
            continue

        if name == "pwmfan":
            pwm1 = os.path.join(hwmon_dir, "pwm1")
            if os.path.exists(pwm1):
                return {
                    "dir": hwmon_dir,
                    "name": name,
                    "hwmon": entry,
                    "pwm1": pwm1,
                    "pwm1_enable": os.path.join(hwmon_dir, "pwm1_enable"),
                    "fan1_input": os.path.join(hwmon_dir, "fan1_input"),
                }
    return None


def read_file(path: str) -> str | None:
    """Read a sysfs file, return stripped content or None."""
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except Exception:
        return None


def write_file(path: str, value: str) -> bool:
    """Write a value to a sysfs file. Returns True on success."""
    try:
        with open(path, "w") as f:
            f.write(value)
        return True
    except PermissionError:
        log.error(f"Permission denied writing {path} — run with sudo!")
        return False
    except Exception as e:
        log.error(f"Failed to write {path}: {e}")
        return False


def enable_manual_pwm(fan: dict) -> bool:
    """Set pwm1_enable to 1 (manual mode) so we can control pwm1 directly."""
    enable_path = fan["pwm1_enable"]
    if not os.path.exists(enable_path):
        log.warning(f"pwm1_enable not found at {enable_path}")
        return True  # May work without it

    current = read_file(enable_path)
    log.info(f"pwm1_enable current value: {current} (path: {enable_path})")

    if current != "1":
        if write_file(enable_path, "1"):
            log.info("pwm1_enable set to 1 (manual mode)")
            return True
        else:
            log.error("Failed to set pwm1_enable to manual mode")
            return False
    else:
        log.info("pwm1_enable already in manual mode (1)")
        return True


def set_fan_speed(fan: dict, speed_pct: int) -> None:
    """Set fan speed via pwm1 (0-255). Logs path, value, and RPM feedback."""
    pwm_value = int(speed_pct * 255 / 100)
    pwm_value = max(0, min(255, pwm_value))

    path = fan["pwm1"]
    if write_file(path, str(pwm_value)):
        # Read back RPM if available
        rpm = read_file(fan["fan1_input"]) if os.path.exists(fan["fan1_input"]) else "N/A"
        log.info(f"PWM written: {path} = {pwm_value} ({speed_pct}%), fan1_input = {rpm} RPM")
    else:
        log.error(f"Failed to write PWM {pwm_value} to {path}")


def calculate_fan_speed(temp: float, current_speed: int) -> int:
    """Calculate target fan speed based on temperature and hysteresis."""
    # Check curve from hottest to coolest
    for threshold, speed in FAN_CURVE:
        if temp >= threshold:
            return speed

    # Below minimum threshold
    if temp <= FAN_OFF_TEMP:
        return 0

    # In hysteresis zone: keep current speed
    return current_speed


import threading


class FanController(threading.Thread):
    """Background thread for fan control — can be started/stopped from the app."""

    def __init__(self):
        super().__init__(daemon=True, name="FanController")
        self._stop_event = threading.Event()
        self.current_speed = 0
        self.current_temp = 0.0

    def run(self):
        """Main fan control loop (runs in background thread)."""
        fan = find_pwmfan_hwmon()

        if not fan:
            log.error(
                "No 'pwmfan' hwmon device found! "
                "Check /sys/class/hwmon/hwmonN/name for 'pwmfan'. "
                "Fan control disabled."
            )
            return

        log.info(f"Found pwmfan: {fan['hwmon']} at {fan['dir']}")
        log.info(f"  pwm1:        {fan['pwm1']}")
        log.info(f"  pwm1_enable: {fan['pwm1_enable']}")
        log.info(f"  fan1_input:  {fan['fan1_input']}")

        # Set manual mode
        if not enable_manual_pwm(fan):
            log.error("Cannot set manual PWM mode — fan control disabled.")
            return

        last_temp = 0.0

        log.info("Fan control started — aggressive curve (50C=40%, 70C=100%)")
        log.info(f"Poll interval: {POLL_INTERVAL_S}s, Hysteresis: {HYSTERESIS_C}C")

        while not self._stop_event.is_set():
            temp = get_cpu_temp()
            self.current_temp = temp
            target_speed = calculate_fan_speed(temp, self.current_speed)

            if target_speed != self.current_speed:
                log.info(f"CPU {temp:.1f}C -> Fan {self.current_speed}% -> {target_speed}%")
                self.current_speed = target_speed
                set_fan_speed(fan, self.current_speed)

            elif abs(temp - last_temp) > 3:
                log.info(f"CPU {temp:.1f}C (fan at {self.current_speed}%)")

            last_temp = temp
            self._stop_event.wait(POLL_INTERVAL_S)

        log.info("Fan control stopped.")

    def stop(self):
        """Signal the fan loop to stop."""
        self._stop_event.set()


def run_fan_loop():
    """Main fan control loop (standalone mode)."""
    controller = FanController()
    controller.run()  # Run in current thread (not as daemon)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    # Handle graceful shutdown
    def signal_handler(sig, frame):
        log.info("Shutting down fan control...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if "--daemon" in sys.argv:
        log.info("Running as daemon...")
        # Detach from terminal
        if os.fork() > 0:
            sys.exit(0)
        os.setsid()
        if os.fork() > 0:
            sys.exit(0)

    run_fan_loop()


if __name__ == "__main__":
    main()
