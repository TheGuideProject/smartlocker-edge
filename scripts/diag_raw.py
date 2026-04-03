#!/usr/bin/env python3
"""
Minimal HX711 raw diagnostic v2.
Reads raw values with settling time to get accurate deltas.

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
BOOT_TIMEOUT = 8
READ_TIMEOUT = 3


def open_and_wait_boot(port, baud):
    print(f"[1] Opening {port} @ {baud}...")
    s = serial.Serial(port, baud, timeout=1.0)
    print("[2] Waiting for Arduino boot...")
    deadline = time.time() + BOOT_TIMEOUT
    while time.time() < deadline:
        line = s.readline().decode("utf-8", errors="replace").strip()
        if line:
            print(f"     boot: {line}")
            if '"ready"' in line:
                break
    time.sleep(0.5)
    while s.in_waiting:
        s.readline()
    return s


def send_cmd(s, cmd_dict):
    cmd_str = json.dumps(cmd_dict, separators=(",", ":")) + "\n"
    s.reset_input_buffer()
    s.write(cmd_str.encode("utf-8"))
    s.flush()
    deadline = time.time() + READ_TIMEOUT
    while time.time() < deadline:
        line = s.readline().decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if "ch" in obj or "ok" in obj or "err" in obj or "status" in obj:
                return obj
        except json.JSONDecodeError:
            pass
    return None


def read_stable(s, ch, count=10, interval=1.0):
    """Read channel `count` times with `interval` seconds between.
    Returns list of (raw, g) tuples."""
    results = []
    for i in range(count):
        if i > 0:
            time.sleep(interval)
        resp = send_cmd(s, {"cmd": "read", "ch": ch})
        if resp and "raw" in resp:
            raw = resp["raw"]
            g = resp.get("g", "?")
            stable = resp.get("stable", "?")
            print(f"     [{i+1:2d}/{count}] raw={raw:>10}  g={g:>10}  stable={stable}")
            results.append((raw, float(g) if isinstance(g, (int, float)) else 0))
        else:
            print(f"     [{i+1:2d}/{count}] ERROR: {resp}")
    return results


def main():
    s = open_and_wait_boot(PORT, BAUD)

    # Ping
    print("\n[3] Ping...")
    resp = send_cmd(s, {"cmd": "ping"})
    print(f"     -> {resp}")
    if not resp or resp.get("status") != "ok":
        print("Arduino not responding. Aborting.")
        s.close()
        return

    # === TARE (bilance vuote) ===
    print("\n" + "=" * 60)
    input(">>> TOGLI TUTTO da entrambe le bilance, poi premi INVIO...")

    print("\n[4] Tare all...")
    resp = send_cmd(s, {"cmd": "tare", "ch": "all"})
    print(f"     -> {resp}")

    print("\n[5] Letture SHELF a vuoto (10 letture, 1 al secondo)...")
    shelf_empty = read_stable(s, "shelf", count=10, interval=1.0)

    print("\n[6] Letture MIX a vuoto (10 letture, 1 al secondo)...")
    mix_empty = read_stable(s, "mix", count=10, interval=1.0)

    # === PESO SULLA SHELF ===
    print("\n" + "=" * 60)
    input(">>> METTI 5kg sulla SHELF, aspetta che si assesti, poi premi INVIO...")
    print("     Aspetto 5 secondi per assestamento...")
    time.sleep(5)

    print("\n[7] Letture SHELF con peso (10 letture, 1 al secondo)...")
    shelf_weight = read_stable(s, "shelf", count=10, interval=1.0)

    print("\n     Togli il peso dalla shelf.")

    # === PESO SULLA MIX ===
    print("\n" + "=" * 60)
    input(">>> METTI 5kg sulla MIX, aspetta che si assesti, poi premi INVIO...")
    print("     Aspetto 5 secondi per assestamento...")
    time.sleep(5)

    print("\n[8] Letture MIX con peso (10 letture, 1 al secondo)...")
    mix_weight = read_stable(s, "mix", count=10, interval=1.0)

    # === ANALISI ===
    print("\n" + "=" * 60)
    print("ANALISI")
    print("=" * 60)

    for label, empty, weight in [("SHELF", shelf_empty, shelf_weight),
                                  ("MIX", mix_empty, mix_weight)]:
        if not empty or not weight:
            print(f"\n{label}: dati mancanti")
            continue
        # Use last 5 readings (more settled)
        empty_raws = [r[0] for r in empty[-5:]]
        weight_raws = [r[0] for r in weight[-5:]]
        avg_empty = sum(empty_raws) / len(empty_raws)
        avg_weight = sum(weight_raws) / len(weight_raws)
        delta = avg_weight - avg_empty
        noise = max(empty_raws) - min(empty_raws)

        print(f"\n{label}:")
        print(f"  avg raw vuoto:     {avg_empty:.0f}")
        print(f"  avg raw con peso:  {avg_weight:.0f}")
        print(f"  delta raw:         {delta:.0f}")
        print(f"  noise (max-min):   {noise}")
        print(f"  direzione:         {'raw SALE' if delta > 0 else 'raw SCENDE'} con peso")
        if abs(delta) > 10:
            factor = abs(delta) / 5000.0
            print(f"  factor (se 5kg):   {factor:.4f} counts/gram")
            sign = "(raw - offset)" if delta > 0 else "(offset - raw)"
            print(f"  formula corretta:  grams = {sign} / {factor:.4f}")
        else:
            print(f"  ATTENZIONE: delta troppo piccolo, peso non rilevato!")

    print("\n" + "=" * 60)
    print("Copia TUTTO questo output e mandamelo.")
    s.close()


if __name__ == "__main__":
    main()
