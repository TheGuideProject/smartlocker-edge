#!/usr/bin/env python3
"""Test both HX711 scales using lgpio directly (RPi5 compatible)."""
import lgpio
import time

h = lgpio.gpiochip_open(0)

channels = {
    "SCAFFALE": {"dt": 5, "sck": 6, "scale": 9.81},
    "MIXING": {"dt": 23, "sck": 24, "scale": 20.69},
}

# Setup GPIO
for name, cfg in channels.items():
    lgpio.gpio_claim_output(h, cfg["sck"], 0)
    lgpio.gpio_claim_input(h, cfg["dt"])


def read_raw(dt, sck):
    timeout = time.time() + 2
    while lgpio.gpio_read(h, dt):
        if time.time() > timeout:
            return None
    count = 0
    for _ in range(24):
        lgpio.gpio_write(h, sck, 1)
        count = count << 1
        lgpio.gpio_write(h, sck, 0)
        if lgpio.gpio_read(h, dt):
            count += 1
    lgpio.gpio_write(h, sck, 1)
    lgpio.gpio_write(h, sck, 0)
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

lgpio.gpiochip_close(h)
print()
print("DONE")
