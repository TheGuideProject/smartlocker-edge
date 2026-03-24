#!/usr/bin/env python3
"""
HX711 Weight Sensor Test & Calibration Tool

Usage:
  python3 scripts/test_weight.py              # Live weight monitor
  python3 scripts/test_weight.py calibrate    # Calibration wizard
  python3 scripts/test_weight.py tare         # Tare (set zero)
"""

import sys
import time

try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
except ImportError:
    print("ERROR: RPi.GPIO not available. Run on Raspberry Pi.")
    sys.exit(1)

DT_PIN = 5
SCK_PIN = 6

GPIO.setup(SCK_PIN, GPIO.OUT)
GPIO.setup(DT_PIN, GPIO.IN)
GPIO.output(SCK_PIN, False)


def read_raw():
    """Read raw 24-bit value from HX711."""
    timeout = time.time() + 2.0
    while GPIO.input(DT_PIN):
        if time.time() > timeout:
            return None

    count = 0
    for _ in range(24):
        GPIO.output(SCK_PIN, True)
        count = count << 1
        GPIO.output(SCK_PIN, False)
        if GPIO.input(DT_PIN):
            count += 1

    # 25th pulse for gain 128
    GPIO.output(SCK_PIN, True)
    GPIO.output(SCK_PIN, False)

    if count & 0x800000:
        count -= 0x1000000

    return count


def read_averaged(samples=5):
    """Read multiple samples, remove outliers, return average."""
    values = []
    for _ in range(samples):
        val = read_raw()
        if val is not None:
            values.append(val)
        time.sleep(0.05)

    if not values:
        return None

    if len(values) >= 4:
        values.sort()
        values = values[1:-1]

    return int(sum(values) / len(values))


def mode_live():
    """Continuous weight display."""
    print("=" * 50)
    print("  HX711 Live Weight Monitor")
    print("=" * 50)
    print()
    print("  Taring... (don't touch the scale)")

    time.sleep(1)
    offset = read_averaged(10)
    if offset is None:
        print("  ERROR: Cannot read HX711. Check wiring!")
        GPIO.cleanup()
        return

    # Calibration: ~5275 units per kg (from user tests)
    scale = 5.275  # units per gram

    print(f"  Tare offset: {offset}")
    print(f"  Scale factor: {scale} units/gram")
    print()
    print("  Put weight on the scale. Press Ctrl+C to stop.")
    print("  " + "-" * 46)

    readings = []
    try:
        while True:
            raw = read_averaged(3)
            if raw is not None:
                grams = (raw - offset) / scale
                grams = max(0, grams)
                kg = grams / 1000

                readings.append(grams)
                if len(readings) > 5:
                    readings = readings[-5:]

                stable = ""
                if len(readings) >= 3:
                    spread = max(readings) - min(readings)
                    if spread < 10:
                        stable = " [STABLE]"

                bar_len = min(40, int(grams / 100))
                bar = "█" * bar_len

                print(f"\r  {grams:8.1f} g  |  {kg:6.3f} kg  {bar:<40s}{stable}   ", end="", flush=True)
            time.sleep(0.3)

    except KeyboardInterrupt:
        print("\n\n  Stopped.")
    finally:
        GPIO.cleanup()


def mode_calibrate():
    """Calibration wizard."""
    print("=" * 50)
    print("  HX711 Calibration Wizard")
    print("=" * 50)
    print()

    # Step 1: Tare
    print("  Step 1: Remove ALL weight from the scale.")
    input("  Press Enter when empty...")

    print("  Reading zero point (10 samples)...")
    offset = read_averaged(10)
    if offset is None:
        print("  ERROR: Cannot read HX711!")
        GPIO.cleanup()
        return

    print(f"  Zero offset = {offset}")
    print()

    # Step 2: Known weight
    known_g = input("  Step 2: How many grams is your test weight? (e.g. 1000): ")
    try:
        known_g = float(known_g)
    except ValueError:
        print("  Invalid number!")
        GPIO.cleanup()
        return

    print(f"  Place {known_g}g on the scale.")
    input("  Press Enter when placed...")

    print("  Reading (10 samples)...")
    loaded = read_averaged(10)
    if loaded is None:
        print("  ERROR: Cannot read HX711!")
        GPIO.cleanup()
        return

    print(f"  Loaded value = {loaded}")

    # Calculate scale factor
    diff = offset - loaded  # Note: our values decrease with weight
    if diff == 0:
        print("  ERROR: No difference detected! Check wiring.")
        GPIO.cleanup()
        return

    scale = abs(diff) / known_g
    print()
    print("  " + "=" * 46)
    print(f"  CALIBRATION RESULTS:")
    print(f"    Offset (tare) = {offset}")
    print(f"    Scale factor  = {scale:.4f} units/gram")
    print(f"    Diff for {known_g}g = {abs(diff)} raw units")
    print(f"    Resolution    ~ {1/scale:.1f}g per unit")
    print("  " + "=" * 46)
    print()
    print("  Update hal/real/real_weight_hx711.py:")
    print(f"    self.scale = {scale:.4f}")
    print()

    # Verify
    print("  Verifying... (keep weight on scale)")
    time.sleep(0.5)
    verify = read_averaged(5)
    if verify is not None:
        grams = abs(verify - offset) / scale
        print(f"  Verification: {grams:.1f}g (expected {known_g}g)")
        error_pct = abs(grams - known_g) / known_g * 100
        print(f"  Error: {error_pct:.1f}%")

    GPIO.cleanup()


def mode_tare():
    """Quick tare."""
    print("  Taring...")
    offset = read_averaged(10)
    if offset:
        print(f"  Tare offset: {offset}")
    else:
        print("  ERROR: Cannot read!")
    GPIO.cleanup()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "live"

    if cmd == "calibrate":
        mode_calibrate()
    elif cmd == "tare":
        mode_tare()
    else:
        mode_live()
