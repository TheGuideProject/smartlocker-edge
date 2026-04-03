#!/usr/bin/env python3
"""
Minimal HX711 raw diagnostic v3.
Robust serial handling: waits for specific responses, validates channels,
discards stale/boot/info lines.

Usage:
    python3 scripts/diag_raw.py [port]
"""

import sys
import serial
import json
import time

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB4"
BAUD = 115200


def open_and_wait_boot(port, baud):
    print(f"[1] Opening {port} @ {baud}...")
    s = serial.Serial(port, baud, timeout=1.0)
    print("[2] Waiting for Arduino boot...")
    deadline = time.time() + 10
    while time.time() < deadline:
        line = s.readline().decode("utf-8", errors="replace").strip()
        if line:
            print(f"     boot: {line}")
            if '"ready"' in line:
                break
    # Drain everything remaining
    drain(s)
    return s


def drain(s, pause=0.3):
    """Read and discard everything in the serial buffer."""
    time.sleep(pause)
    while s.in_waiting:
        s.read(s.in_waiting)
        time.sleep(0.1)


def read_line_json(s, timeout=10.0):
    """Read one JSON line from serial. Returns parsed dict or None."""
    old_timeout = s.timeout
    s.timeout = timeout
    try:
        line = s.readline().decode("utf-8", errors="replace").strip()
        if line:
            return json.loads(line), line
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, line
    finally:
        s.timeout = old_timeout
    return None, ""


def wait_for_tare(s, timeout=15.0):
    """Send tare all and wait explicitly for the ok response."""
    drain(s)
    cmd = json.dumps({"cmd": "tare", "ch": "all"}, separators=(",", ":")) + "\n"
    s.write(cmd.encode("utf-8"))
    s.flush()

    deadline = time.time() + timeout
    while time.time() < deadline:
        obj, raw_line = read_line_json(s, timeout=2.0)
        if obj is None:
            if raw_line:
                print(f"     [scarto non-JSON] {raw_line}")
            continue
        if "ok" in obj and obj.get("ok") == "tare":
            print(f"     TARE OK: {obj}")
            drain(s)
            return True
        elif "info" in obj:
            print(f"     [init]  {raw_line}")
        else:
            print(f"     [scarto] {raw_line}")

    print("     TARE TIMEOUT!")
    drain(s)
    return False


def read_channel(s, ch):
    """Send read command for `ch`, wait for response with matching channel.
    Discards any non-matching lines."""
    drain(s, pause=0.1)
    cmd = json.dumps({"cmd": "read", "ch": ch}, separators=(",", ":")) + "\n"
    s.write(cmd.encode("utf-8"))
    s.flush()

    deadline = time.time() + 10.0
    while time.time() < deadline:
        obj, raw_line = read_line_json(s, timeout=5.0)
        if obj is None:
            if raw_line:
                print(f"     [scarto non-JSON] {raw_line}")
            continue
        # Check if this is a measurement for the RIGHT channel
        if "ch" in obj and "raw" in obj and obj["ch"] == ch:
            return obj
        # Wrong channel or non-measurement line
        if "info" in obj:
            print(f"     [init]  {raw_line}")
        elif "ch" in obj and obj["ch"] != ch:
            print(f"     [canale sbagliato: volevo {ch}, ricevuto {obj['ch']}] {raw_line}")
        else:
            print(f"     [scarto] {raw_line}")

    print(f"     TIMEOUT reading {ch}")
    return None


def read_stable(s, ch, count=10, interval=1.0):
    """Read channel `count` times. Returns list of response dicts."""
    results = []
    for i in range(count):
        if i > 0:
            time.sleep(interval)
        resp = read_channel(s, ch)
        if resp:
            raw = resp["raw"]
            g = resp.get("g", "?")
            off = resp.get("off", "?")
            diff = resp.get("diff", "?")
            scl = resp.get("scl", "?")
            stable = resp.get("stable", "?")
            print(f"     [{i+1:2d}/{count}] raw={raw:>10}  off={off:>10}  "
                  f"diff={diff:>8}  scl={scl:>8}  g={g:>10}  stable={stable}")
            results.append(resp)
        else:
            print(f"     [{i+1:2d}/{count}] NESSUNA RISPOSTA VALIDA")
    return results


def main():
    s = open_and_wait_boot(PORT, BAUD)

    # Ping
    print("\n[3] Ping...")
    drain(s)
    cmd = json.dumps({"cmd": "ping"}, separators=(",", ":")) + "\n"
    s.write(cmd.encode("utf-8"))
    s.flush()
    deadline = time.time() + 10.0
    while time.time() < deadline:
        obj, raw_line = read_line_json(s, timeout=3.0)
        if obj and "status" in obj:
            print(f"     -> {obj}")
            break
        elif obj and "info" in obj:
            print(f"     [init] {raw_line}")
        elif raw_line:
            print(f"     [scarto] {raw_line}")
    else:
        print("     NESSUNA RISPOSTA AL PING")
        s.close()
        return

    # === TARE ===
    print("\n" + "=" * 60)
    input(">>> TOGLI TUTTO da entrambe le bilance, poi premi INVIO...")
    print("\n[4] Tare all (attendo risposta esplicita)...")
    if not wait_for_tare(s):
        print("     ATTENZIONE: tare potrebbe non essere riuscito")

    # === LETTURE A VUOTO ===
    print("\n[5] Letture SHELF a vuoto (10x, 1s intervallo)...")
    shelf_empty = read_stable(s, "shelf", count=10, interval=1.0)

    print("\n[6] Letture MIX a vuoto (10x, 1s intervallo)...")
    mix_empty = read_stable(s, "mix", count=10, interval=1.0)

    # === PESO SHELF ===
    print("\n" + "=" * 60)
    input(">>> METTI 5kg sulla SHELF, aspetta che sia FERMO, poi premi INVIO...")
    print("     Aspetto 5 secondi...")
    time.sleep(5)
    print("\n[7] Letture SHELF con peso (10x, 1s intervallo)...")
    shelf_weight = read_stable(s, "shelf", count=10, interval=1.0)
    print("\n     Togli il peso dalla shelf.")

    # === PESO MIX ===
    print("\n" + "=" * 60)
    input(">>> METTI 5kg sulla MIX, aspetta che sia FERMO, poi premi INVIO...")
    print("     Aspetto 5 secondi...")
    time.sleep(5)
    print("\n[8] Letture MIX con peso (10x, 1s intervallo)...")
    mix_weight = read_stable(s, "mix", count=10, interval=1.0)

    # === ANALISI ===
    print("\n" + "=" * 60)
    print("ANALISI")
    print("=" * 60)

    for label, empty, weight in [("SHELF", shelf_empty, shelf_weight),
                                  ("MIX", mix_empty, mix_weight)]:
        if len(empty) < 3 or len(weight) < 3:
            print(f"\n{label}: dati insufficienti (empty={len(empty)}, weight={len(weight)})")
            continue

        # Use last 5 readings (most settled)
        e_raws = [r["raw"] for r in empty[-5:]]
        w_raws = [r["raw"] for r in weight[-5:]]
        avg_e = sum(e_raws) / len(e_raws)
        avg_w = sum(w_raws) / len(w_raws)
        delta = avg_w - avg_e
        noise_e = max(e_raws) - min(e_raws)
        noise_w = max(w_raws) - min(w_raws)

        # Get offset from last reading
        last_off = empty[-1].get("off", "?")
        last_scl = empty[-1].get("scl", "?")

        print(f"\n{label}:")
        print(f"  offset usato:      {last_off}")
        print(f"  scale usato:       {last_scl}")
        print(f"  avg raw vuoto:     {avg_e:.0f}")
        print(f"  avg raw con peso:  {avg_w:.0f}")
        print(f"  delta raw:         {delta:.0f}")
        print(f"  noise vuoto:       {noise_e}")
        print(f"  noise con peso:    {noise_w}")
        print(f"  direzione:         {'raw SALE' if delta > 0 else 'raw SCENDE'} con peso")
        if abs(delta) > abs(noise_e):
            factor = abs(delta) / 5000.0
            sign = "(raw - offset)" if delta > 0 else "(offset - raw)"
            print(f"  SNR:               {abs(delta)/max(noise_e,1):.1f}:1")
            print(f"  factor (se 5kg):   {factor:.4f}")
            print(f"  formula:           grams = {sign} / {factor:.4f}")
        else:
            print(f"  SNR:               {abs(delta)/max(noise_e,1):.1f}:1  *** SEGNALE < RUMORE ***")
            print(f"  SHELF POTREBBE AVERE UN PROBLEMA HARDWARE")

    print("\n" + "=" * 60)
    print("Copia TUTTO questo output e mandamelo.")
    s.close()


if __name__ == "__main__":
    main()
