#!/usr/bin/env python3
"""Test both HX711 scales with calibration values."""
import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

channels = {
    "SCAFFALE": {"dt": 5, "sck": 6, "scale": 10.78},
    "MIXING": {"dt": 23, "sck": 24, "scale": 17.86},
}


def read_raw(dt, sck):
    timeout = time.time() + 2
    while GPIO.input(dt):
        if time.time() > timeout:
            return None
    count = 0
    for _ in range(24):
        GPIO.output(sck, True)
        count = count << 1
        GPIO.output(sck, False)
        if GPIO.input(dt):
            count += 1
    GPIO.output(sck, True)
    GPIO.output(sck, False)
    if count & 0x800000:
        count -= 0x1000000
    return count


def read_avg(dt, sck, n=10):
    vals = []
    for _ in range(n):
        v = read_raw(dt, sck)
        if v is not None:
            vals.append(v)
        time.sleep(0.05)
    return int(sum(vals) / len(vals)) if vals else None


# Setup GPIO
for name, cfg in channels.items():
    GPIO.setup(cfg["sck"], GPIO.OUT)
    GPIO.setup(cfg["dt"], GPIO.IN)
    GPIO.output(cfg["sck"], False)

print("=== TEST BILANCE ===")
print()
print("Togli tutto da entrambe le bilance")
input("Premi INVIO...")

offsets = {}
for name, cfg in channels.items():
    offsets[name] = read_avg(cfg["dt"], cfg["sck"], 15)
    print(f"  {name} zero: {offsets[name]}")

print()
print("Ora metti 2kg sullo SCAFFALE")
input("Premi INVIO...")

for name, cfg in channels.items():
    raw = read_avg(cfg["dt"], cfg["sck"], 10)
    if raw is not None and offsets[name] is not None:
        grams = (offsets[name] - raw) / cfg["scale"]
        print(f"  {name}: {grams:.0f}g")
    else:
        print(f"  {name}: ERRORE lettura")

print()
print("Ora sposta 2kg sul PIATTO MIXING")
input("Premi INVIO...")

for name, cfg in channels.items():
    raw = read_avg(cfg["dt"], cfg["sck"], 10)
    if raw is not None and offsets[name] is not None:
        grams = (offsets[name] - raw) / cfg["scale"]
        print(f"  {name}: {grams:.0f}g")
    else:
        print(f"  {name}: ERRORE lettura")

GPIO.cleanup()
print()
print("DONE")
