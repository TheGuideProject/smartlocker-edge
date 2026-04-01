"""
SmartLocker Launcher

Single entry point that starts both the hardware daemon and the UI.
Double-click this file (or the .bat shortcut) to launch everything.

Usage:
    python launcher.py              # Daemon + Qt UI (default)
    python launcher.py --test       # Force test mode (fake sensors)
    python launcher.py --no-daemon  # Direct mode (no daemon, single process)
"""

import subprocess
import sys
import os
import time
import signal
import socket

# ── Configuration ──
DAEMON_PORT = 9800
DAEMON_STARTUP_TIMEOUT = 15  # seconds to wait for daemon (Arduino serial can be slow)
PYTHON = sys.executable
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a TCP port is accepting connections."""
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except (ConnectionRefusedError, TimeoutError, OSError):
        return False


def wait_for_daemon(port: int, timeout: float) -> bool:
    """Wait until daemon is accepting connections."""
    start = time.time()
    while time.time() - start < timeout:
        if is_port_open(port):
            return True
        time.sleep(0.3)
    return False


def main():
    args = sys.argv[1:]
    extra_args = []
    no_daemon = False

    for arg in args:
        if arg == "--no-daemon":
            no_daemon = True
        else:
            extra_args.append(arg)

    # ── Single process mode (no daemon) ──
    if no_daemon:
        print("[LAUNCHER] Starting in single-process mode...")
        cmd = [PYTHON, os.path.join(SCRIPT_DIR, "main.py")] + extra_args
        os.execv(PYTHON, cmd)
        return

    # ── Daemon + UI mode ──
    daemon_proc = None
    ui_proc = None

    try:
        # 1. Check if daemon already running
        if is_port_open(DAEMON_PORT):
            print(f"[LAUNCHER] Daemon already running on port {DAEMON_PORT}")
        else:
            # Start daemon process
            print(f"[LAUNCHER] Starting hardware daemon on port {DAEMON_PORT}...")
            daemon_cmd = [
                PYTHON, os.path.join(SCRIPT_DIR, "hw_daemon.py"),
                "--port", str(DAEMON_PORT),
            ] + extra_args

            # On Windows: CREATE_NEW_PROCESS_GROUP so daemon runs independently
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

            daemon_proc = subprocess.Popen(
                daemon_cmd,
                creationflags=creation_flags,
            )
            print(f"[LAUNCHER] Daemon PID: {daemon_proc.pid}")

            # Wait for daemon to be ready
            if wait_for_daemon(DAEMON_PORT, DAEMON_STARTUP_TIMEOUT):
                print("[LAUNCHER] Daemon ready!")
            else:
                print("[LAUNCHER] WARNING: Daemon not responding yet, starting UI anyway...")

        # 2. Start UI process (connects to daemon)
        print("[LAUNCHER] Starting UI (daemon-client mode)...")
        ui_cmd = [
            PYTHON, os.path.join(SCRIPT_DIR, "main.py"),
            "--daemon-client", "--port", str(DAEMON_PORT),
        ] + extra_args

        ui_proc = subprocess.Popen(ui_cmd)
        print(f"[LAUNCHER] UI PID: {ui_proc.pid}")

        # 3. Wait for UI to exit
        ui_proc.wait()
        print("[LAUNCHER] UI closed.")

    except KeyboardInterrupt:
        print("\n[LAUNCHER] Interrupted.")

    finally:
        # Cleanup: stop daemon when UI exits
        if daemon_proc and daemon_proc.poll() is None:
            print("[LAUNCHER] Stopping daemon...")
            try:
                if sys.platform == "win32":
                    daemon_proc.terminate()
                else:
                    daemon_proc.send_signal(signal.SIGTERM)
                daemon_proc.wait(timeout=3)
            except Exception:
                daemon_proc.kill()
            print("[LAUNCHER] Daemon stopped.")

        print("[LAUNCHER] Goodbye.")


if __name__ == "__main__":
    main()
