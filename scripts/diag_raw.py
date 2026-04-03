#!/usr/bin/env python3
"""
Minimal HX711 raw diagnostic.
Opens Arduino serial, waits for full boot, then reads raw + grams
for both channels. Designed to run ONCE per invocation with clear output.

Usage:
    python3 scripts/diag_raw.py [port]

Default port: /dev/ttyUSB4
"""

import sys
import serial
import json
import time

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB4"
BAUD = 115200
BOOT_TIMEOUT = 8  # seconds max to wait for boot
READ_TIMEOUT = 3  # seconds per command


def open_and_wait_boot(port, baud):
    """Open serial, wait for Arduino boot to complete."""
    print(f"[1] Opening {port} @ {baud}...")
    s = serial.Serial(port, baud, timeout=1.0)

    print("[2] Waiting for Arduino boot (reset on serial open)...")
    deadline = time.time() + BOOT_TIMEOUT
    boot_lines = []
    boot_done = False

    while time.time() < deadline:
        line = s.readline().decode("utf-8", errors="replace").strip()
        if line:
            boot_lines.append(line)
            print(f"     boot: {line}")
            if '"ready"' in line:
                boot_done = True
                break

    if not boot_done:
        print("     WARNING: did not see boot:ready, continuing anyway")

    # Drain any remaining init messages
    time.sleep(0.5)
    while s.in_waiting:
        extra = s.readline().decode("utf-8", errors="replace").strip()
        if extra:
            boot_lines.append(extra)
            print(f"     boot: {extra}")

    return s


def send_and_read(s, cmd_dict, label=""):
    """Send JSON command, read all response lines until we get the one we want."""
    cmd_str = json.dumps(cmd_dict, separators=(",", ":")) + "\n"
    s.reset_input_buffer()
    s.write(cmd_str.encode("utf-8"))
    s.flush()

    deadline = time.time() + READ_TIMEOUT
    responses = []

    while time.time() < deadline:
        line = s.readline().decode("utf-8", errors="replace").strip()
        if not line:
            continue
        responses.append(line)
        # Check if this is a data response (has "ch" or "ok" or "err")
        try:
            obj = json.loads(line)
            if "ch" in obj or "ok" in obj or "err" in obj or "status" in obj:
                return obj, responses
        except json.JSONDecodeError:
            pass

    return None, responses


def main():
    s = open_and_wait_boot(PORT, BAUD)

    # Step 1: Ping
    print("\n[3] Ping...")
    resp, _ = send_and_read(s, {"cmd": "ping"})
    if resp:
        print(f"     -> {resp}")
    else:
        print("     -> NO RESPONSE. Arduino not connected?")
        s.close()
        return

    # Step 2: Read both channels RAW (offset=0, no tare)
    print("\n[4] Reading SHELF (no tare, offset=0)...")
    resp, extras = send_and_read(s, {"cmd": "read", "ch": "shelf"})
    for e in extras:
        if e != json.dumps(resp, separators=(",", ":")):
            print(f"     info: {e}")
    if resp and "g" in resp:
        print(f"     SHELF raw={resp['raw']}  g={resp['g']}  stable={resp.get('stable')}")
        shelf_raw_empty = resp["raw"]
        shelf_g_empty = resp["g"]
    else:
        print(f"     ERROR: {resp}")
        shelf_raw_empty = None
        shelf_g_empty = None

    print("\n[5] Reading MIX (no tare, offset=0)...")
    resp, extras = send_and_read(s, {"cmd": "read", "ch": "mix"})
    for e in extras:
        if e != json.dumps(resp, separators=(",", ":")):
            print(f"     info: {e}")
    if resp and "g" in resp:
        print(f"     MIX   raw={resp['raw']}  g={resp['g']}  stable={resp.get('stable')}")
        mix_raw_empty = resp["raw"]
        mix_g_empty = resp["g"]
    else:
        print(f"     ERROR: {resp}")
        mix_raw_empty = None
        mix_g_empty = None

    # Step 3: Manual tare
    print("\n" + "=" * 60)
    input(">>> TOGLI TUTTO dalle bilance, poi premi INVIO per TARE...")
    print("\n[6] Taring all channels...")
    resp, _ = send_and_read(s, {"cmd": "tare", "ch": "all"})
    print(f"     -> {resp}")

    # Read after tare (should be ~0)
    time.sleep(0.3)
    print("\n[7] Reading after tare (should be ~0)...")
    resp, _ = send_and_read(s, {"cmd": "read", "ch": "shelf"})
    if resp and "g" in resp:
        print(f"     SHELF raw={resp['raw']}  g={resp['g']}")
    resp, _ = send_and_read(s, {"cmd": "read", "ch": "mix"})
    if resp and "g" in resp:
        print(f"     MIX   raw={resp['raw']}  g={resp['g']}")

    # Step 4: Add weight
    print("\n" + "=" * 60)
    input(">>> METTI un peso noto (es. 5kg) sulla SHELF, poi premi INVIO...")
    print("\n[8] Reading SHELF with weight...")
    for i in range(3):
        time.sleep(0.3)
        resp, _ = send_and_read(s, {"cmd": "read", "ch": "shelf"})
        if resp and "g" in resp:
            print(f"     lettura {i+1}: raw={resp['raw']}  g={resp['g']}  stable={resp.get('stable')}")

    print("\n" + "=" * 60)
    input(">>> METTI un peso noto sulla MIX, poi premi INVIO...")
    print("\n[9] Reading MIX with weight...")
    for i in range(3):
        time.sleep(0.3)
        resp, _ = send_and_read(s, {"cmd": "read", "ch": "mix"})
        if resp and "g" in resp:
            print(f"     lettura {i+1}: raw={resp['raw']}  g={resp['g']}  stable={resp.get('stable')}")

    # Summary
    print("\n" + "=" * 60)
    print("SOMMARIO")
    print("=" * 60)
    print("Firmware pins:   SHELF_DT=4 SHELF_SCK=5  MIX_DT=2 MIX_SCK=3")
    print("Scale factors:   shelf=0.2084  mix=0.0638")
    print("Sign formula:    grams = (raw - offset) / scale")
    print()
    print("Copia questo output e mandamelo intero.")

    s.close()


if __name__ == "__main__":
    main()
