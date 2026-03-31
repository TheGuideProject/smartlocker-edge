#!/usr/bin/env python3
"""
SmartLocker Aggressive Fan Control — PWM fan curve for Raspberry Pi 5.

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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [FAN] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fan")

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


# ── RPi5 PWM Fan via thermal sysfs ───────────────────
# RPi5 has built-in fan control via:
#   /sys/class/thermal/cooling_device0/cur_state
# States: 0=off, 1=low, 2=medium, 3=high, 4=full
# Or via /sys/class/hwmon/ for finer PWM control

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


def find_pwm_fan():
    """Find the fan PWM control file on the system."""
    # RPi5 official fan
    paths = [
        # RPi5 active cooler via cooling_device
        "/sys/class/thermal/cooling_device0/cur_state",
        # GPIO PWM fan via hwmon
        "/sys/class/hwmon/hwmon0/pwm1",
        "/sys/class/hwmon/hwmon1/pwm1",
        "/sys/class/hwmon/hwmon2/pwm1",
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def find_max_state():
    """Find the max cooling state for RPi5 fan."""
    try:
        with open("/sys/class/thermal/cooling_device0/max_state", "r") as f:
            return int(f.read().strip())
    except Exception:
        return 4  # Default RPi5 has 4 states


def set_fan_speed_cooling_device(speed_pct: int):
    """Set fan speed via RPi5 cooling_device (0-4 states)."""
    max_state = find_max_state()

    if speed_pct <= 0:
        state = 0
    elif speed_pct <= 25:
        state = 1
    elif speed_pct <= 50:
        state = 2
    elif speed_pct <= 75:
        state = 3
    else:
        state = max_state

    try:
        with open("/sys/class/thermal/cooling_device0/cur_state", "w") as f:
            f.write(str(state))
    except PermissionError:
        log.error("Permission denied — run with sudo!")
        sys.exit(1)
    except Exception as e:
        log.error(f"Failed to set fan state: {e}")


def set_fan_speed_pwm(path: str, speed_pct: int):
    """Set fan speed via PWM file (0-255)."""
    value = int(speed_pct * 255 / 100)
    value = max(0, min(255, value))
    try:
        with open(path, "w") as f:
            f.write(str(value))
    except PermissionError:
        log.error("Permission denied — run with sudo!")
        sys.exit(1)
    except Exception as e:
        log.error(f"Failed to write PWM: {e}")


def set_fan_speed_gpio(speed_pct: int):
    """Set fan speed via GPIO PWM (fallback for HAT fans)."""
    try:
        import lgpio
        FAN_GPIO = 14  # Common fan control pin
        h = lgpio.gpiochip_open(0)
        if speed_pct <= 0:
            lgpio.gpio_write(h, FAN_GPIO, 0)
        else:
            freq = 25000  # 25kHz PWM for fan
            duty = max(0, min(100, speed_pct))
            lgpio.tx_pwm(h, FAN_GPIO, freq, duty)
    except ImportError:
        pass
    except Exception as e:
        log.warning(f"GPIO fan control failed: {e}")


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


def run_fan_loop():
    """Main fan control loop."""
    pwm_path = find_pwm_fan()
    use_cooling_device = False
    use_gpio = False

    if pwm_path and "cooling_device" in pwm_path:
        use_cooling_device = True
        log.info(f"Using RPi5 cooling_device: {pwm_path}")
    elif pwm_path:
        log.info(f"Using PWM fan control: {pwm_path}")
    else:
        use_gpio = True
        log.info("No sysfs fan found — trying GPIO PWM on pin 14")

    current_speed = 0
    last_temp = 0.0

    log.info("Fan control started — aggressive curve (50C=40%, 70C=100%)")
    log.info(f"Poll interval: {POLL_INTERVAL_S}s, Hysteresis: {HYSTERESIS_C}C")

    while True:
        temp = get_cpu_temp()
        target_speed = calculate_fan_speed(temp, current_speed)

        if target_speed != current_speed:
            log.info(f"CPU {temp:.1f}C -> Fan {current_speed}% -> {target_speed}%")
            current_speed = target_speed

            if use_cooling_device:
                set_fan_speed_cooling_device(current_speed)
            elif use_gpio:
                set_fan_speed_gpio(current_speed)
            else:
                set_fan_speed_pwm(pwm_path, current_speed)

        elif abs(temp - last_temp) > 3:
            # Log significant temp changes even if fan speed unchanged
            log.info(f"CPU {temp:.1f}C (fan at {current_speed}%)")

        last_temp = temp
        time.sleep(POLL_INTERVAL_S)


def main():
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
