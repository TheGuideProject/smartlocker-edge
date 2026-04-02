#!/usr/bin/env python3
"""
Quick weight diagnostics — talk directly to Arduino and show raw readings.
Usage: python3 scripts/diag_weight.py
"""
import serial
import serial.tools.list_ports
import json
import time
import sys


def find_arduino():
    """Find Arduino serial port (CH340/CP210x, skip PN532)."""
    ports = serial.tools.list_ports.comports()
    candidates = []
    for p in ports:
        desc = (p.description or "").lower()
        vid = p.vid or 0
        if vid == 0x1A86 or "ch340" in desc or "cp210" in desc:
            candidates.append(p.device)

    for port in candidates:
        try:
            s = serial.Serial(port, 115200, timeout=1)
            time.sleep(0.3)
            # Read boot messages
            boot = b""
            t0 = time.time()
            while time.time() - t0 < 2:
                if s.in_waiting:
                    boot += s.readline()
                else:
                    time.sleep(0.1)

            # Try ping
            s.write(b'{"cmd":"ping"}\n')
            time.sleep(0.3)
            resp = s.readline().decode("utf-8", errors="ignore").strip()
            if "ok" in resp or "fw" in resp:
                print(f"[OK] Arduino found on {port}")
                print(f"     Boot: {boot.decode('utf-8', errors='ignore').strip()[:200]}")
                print(f"     Ping: {resp}")
                return s, port
            s.close()
        except Exception as e:
            print(f"[--] {port}: {e}")

    return None, None


def send_cmd(ser, cmd_dict):
    """Send JSON command and return response."""
    msg = json.dumps(cmd_dict) + "\n"
    ser.write(msg.encode())
    time.sleep(0.3)

    resp_line = ""
    t0 = time.time()
    while time.time() - t0 < 2:
        if ser.in_waiting:
            resp_line = ser.readline().decode("utf-8", errors="ignore").strip()
            if resp_line:
                try:
                    return json.loads(resp_line)
                except json.JSONDecodeError:
                    print(f"  (non-JSON): {resp_line}")
        else:
            time.sleep(0.05)
    return None


def main():
    print("=" * 60)
    print("SmartLocker Weight Diagnostics")
    print("=" * 60)

    ser, port = find_arduino()
    if not ser:
        print("\n[ERROR] Arduino not found! Check USB cable.")
        sys.exit(1)

    # Status
    print("\n--- STATUS ---")
    status = send_cmd(ser, {"cmd": "status"})
    print(f"  Status: {status}")

    # Init HX711
    print("\n--- INIT HX711 ---")
    init = send_cmd(ser, {"cmd": "init_hx"})
    print(f"  Init: {init}")
    time.sleep(0.5)
    # Drain any info messages
    while ser.in_waiting:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if line:
            print(f"  Info: {line}")

    # Tare both
    print("\n--- TARE ALL ---")
    tare = send_cmd(ser, {"cmd": "tare", "ch": "all"})
    print(f"  Tare: {tare}")
    time.sleep(0.5)

    # Read shelf 5 times
    print("\n--- SHELF SCALE (5 readings) ---")
    for i in range(5):
        resp = send_cmd(ser, {"cmd": "read", "ch": "shelf"})
        if resp and "g" in resp:
            print(f"  [{i+1}] {resp['g']:.1f}g  raw={resp.get('raw', '?')}  stable={resp.get('stable', '?')}")
        elif resp and "err" in resp:
            print(f"  [{i+1}] ERROR: {resp['err']}")
        else:
            print(f"  [{i+1}] No response")
        time.sleep(0.3)

    # Read mix 5 times
    print("\n--- MIX SCALE (5 readings) ---")
    for i in range(5):
        resp = send_cmd(ser, {"cmd": "read", "ch": "mix"})
        if resp and "g" in resp:
            print(f"  [{i+1}] {resp['g']:.1f}g  raw={resp.get('raw', '?')}  stable={resp.get('stable', '?')}")
        elif resp and "err" in resp:
            print(f"  [{i+1}] ERROR: {resp['err']}")
        else:
            print(f"  [{i+1}] No response")
        time.sleep(0.3)

    # Interactive: continuous reading
    print("\n--- CONTINUOUS READING (Ctrl+C to stop) ---")
    print("Place/remove weight to test sensitivity")
    print(f"{'Time':>8}  {'Shelf (g)':>12}  {'Mix (g)':>12}  {'Shelf raw':>12}  {'Mix raw':>12}")
    print("-" * 62)

    try:
        t_start = time.time()
        while True:
            shelf = send_cmd(ser, {"cmd": "read", "ch": "shelf"})
            mix_ = send_cmd(ser, {"cmd": "read", "ch": "mix"})

            elapsed = time.time() - t_start
            sg = f"{shelf['g']:.1f}" if shelf and "g" in shelf else "ERR"
            mg = f"{mix_['g']:.1f}" if mix_ and "g" in mix_ else "ERR"
            sr = str(shelf.get("raw", "?")) if shelf else "?"
            mr = str(mix_.get("raw", "?")) if mix_ else "?"

            print(f"{elapsed:7.1f}s  {sg:>12}  {mg:>12}  {sr:>12}  {mr:>12}")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopped.")

    ser.close()
    print("Done.")


if __name__ == "__main__":
    main()
