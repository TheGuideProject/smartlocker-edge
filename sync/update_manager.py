"""
OTA Update Manager - Git-based firmware updates for SmartLocker Edge.

Flow:
1. Cloud config includes {"update": {"version": "1.3.0", "branch": "master"}}
2. UpdateManager compares against current version from config/VERSION
3. If different: git fetch → git reset --hard → pip install → verify → restart
4. If .ino firmware changed: auto-compile + flash Arduino via avrdude
5. If verify fails: rollback to previous commit
6. Reports status back to cloud via cloud_client
"""

import os
import sys
import time
import logging
import subprocess
import hashlib
import glob as globmod
import json
import serial  # type: ignore
from typing import Optional, Tuple, Callable

logger = logging.getLogger("smartlocker.update")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_FILE = os.path.join(PROJECT_ROOT, "config", "VERSION")
REQUIREMENTS_FILE = os.path.join(PROJECT_ROOT, "requirements.txt")
FIRMWARE_DIR = os.path.join(PROJECT_ROOT, "firmware", "smartlocker_nano")
FIRMWARE_INO = os.path.join(FIRMWARE_DIR, "smartlocker_nano.ino")
FIRMWARE_HEX = os.path.join(FIRMWARE_DIR, "smartlocker_nano.hex")
BUILD_DIR = "/tmp/smartlocker_arduino_build"


def read_version() -> str:
    """Read current version from config/VERSION file."""
    try:
        with open(VERSION_FILE, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "unknown"


class UpdateManager:
    """Manages OTA firmware updates via git."""

    def __init__(self, cloud_client, db):
        self._cloud = cloud_client
        self._db = db
        self._previous_commit = None
        self._update_in_progress = False
        self._arduino_release: Optional[Callable] = None  # returns (port, close_fn)

    def set_arduino_release(self, callback: Callable):
        """Set callback to release Arduino serial port before flashing.

        callback() should:
          1. Return the current Arduino serial port path (e.g. '/dev/ttyUSB0')
          2. Close the serial connection so avrdude can access the port
        """
        self._arduino_release = callback

    def check_update(self, config_data: dict) -> Optional[dict]:
        """Check if config contains an update command."""
        update = config_data.get("update")
        if not update:
            return None

        target_version = update.get("version", "")
        current = read_version()
        action = update.get("action", "update")

        if action == "update" and target_version == current:
            logger.info(f"Already at version {current}, skipping update")
            return None

        logger.info(f"Update available: {current} → {target_version}")
        return update

    def apply_update(self, update_info: dict) -> Tuple[bool, str]:
        """Execute the full update workflow."""
        if self._update_in_progress:
            return False, "Update already in progress"

        self._update_in_progress = True
        target_version = update_info.get("version", "?")
        branch = update_info.get("branch", "master")

        try:
            logger.info(f"=== OTA UPDATE START: → v{target_version} (branch: {branch}) ===")

            # Step 1: Save current state for rollback
            self._previous_commit = self._get_current_commit()
            logger.info(f"Rollback point: {self._previous_commit[:10] if self._previous_commit else 'N/A'}")

            # Step 2: Report "downloading" status
            self._report_status("downloading", target_version)

            # Step 3: Save requirements + firmware hashes for comparison
            old_req_hash = self._file_hash(REQUIREMENTS_FILE)
            old_ino_hash = self._file_hash(FIRMWARE_INO)

            # Step 4: Git fetch
            ok, output = self._run_git(["fetch", "origin"])
            if not ok:
                return self._fail(f"git fetch failed: {output}", target_version)
            logger.info("Git fetch completed")

            # Step 5: Git reset --hard
            target_ref = f"origin/{branch}"
            ok, output = self._run_git(["reset", "--hard", target_ref])
            if not ok:
                return self._fail(f"git reset failed: {output}", target_version)
            logger.info(f"Git reset to {target_ref}")

            # Step 6: Report "applying" status
            self._report_status("applying", target_version)

            # Step 7: Check if requirements changed
            new_req_hash = self._file_hash(REQUIREMENTS_FILE)
            if new_req_hash != old_req_hash:
                logger.info("requirements.txt changed, running pip install...")
                ok, output = self._run_pip_install()
                if not ok:
                    logger.warning(f"pip install failed: {output}")
                    # Don't fail the update for pip errors — might still work

            # Step 8: Verify new code
            ok, error = self._verify_new_code()
            if not ok:
                logger.error(f"Verification failed: {error}")
                self.rollback()
                return self._fail(f"Code verification failed: {error}", target_version)

            logger.info("Code verification passed")

            # Step 8b: Flash Arduino if firmware .ino changed
            new_ino_hash = self._file_hash(FIRMWARE_INO)
            if new_ino_hash != old_ino_hash and new_ino_hash:
                logger.info("Arduino firmware changed — starting auto-flash...")
                self._report_status("applying", f"{target_version} (flashing Arduino)")
                flash_ok, flash_msg = self._flash_arduino()
                if flash_ok:
                    logger.info(f"Arduino flash OK: {flash_msg}")
                else:
                    # Arduino flash failure is NOT fatal — Python app still updated
                    logger.warning(f"Arduino flash FAILED: {flash_msg} — continuing anyway")
            elif new_ino_hash == old_ino_hash:
                logger.info("Arduino firmware unchanged — skip flash")

            # Step 9: Update VERSION file if not already updated by git
            # (read the new version from the file that git pulled)
            new_version = read_version()
            logger.info(f"New version: {new_version}")

            # Step 10: Report success
            self._report_status("completed", new_version)

            # Log to local DB
            try:
                self._db.save_config("last_update", f"{new_version} at {time.strftime('%Y-%m-%dT%H:%M:%S')}")
            except Exception:
                pass

            logger.info(f"=== OTA UPDATE COMPLETE: v{new_version} — Restarting... ===")

            # Step 11: Restart
            self._restart_app()

            return True, ""  # Won't reach here if restart works

        except Exception as e:
            logger.exception(f"Update error: {e}")
            if self._previous_commit:
                self.rollback()
            return self._fail(str(e), target_version)
        finally:
            self._update_in_progress = False

    def rollback(self) -> bool:
        """Rollback to previous commit."""
        if not self._previous_commit:
            logger.error("No rollback point available")
            return False

        logger.warning(f"Rolling back to {self._previous_commit[:10]}...")
        ok, output = self._run_git(["reset", "--hard", self._previous_commit])
        if ok:
            logger.info("Rollback successful")
        else:
            logger.error(f"Rollback failed: {output}")
        return ok

    def _get_current_commit(self) -> Optional[str]:
        """Get current git HEAD commit hash."""
        ok, output = self._run_git(["rev-parse", "HEAD"])
        return output.strip() if ok else None

    def _verify_new_code(self) -> Tuple[bool, str]:
        """Verify new code can import without errors."""
        try:
            check_script = (
                "import config.settings; "
                "import core.event_bus; "
                "import core.inventory_engine; "
                "import core.mixing_engine; "
                "import persistence.database; "
                "import sync.cloud_client; "
                "print('VERIFY_OK')"
            )
            result = subprocess.run(
                [sys.executable, "-c", check_script],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and "VERIFY_OK" in result.stdout:
                return True, ""
            return False, result.stderr[:500] if result.stderr else "Import check failed"
        except subprocess.TimeoutExpired:
            return False, "Verification timed out (30s)"
        except Exception as e:
            return False, str(e)

    def _run_pip_install(self) -> Tuple[bool, str]:
        """Run pip install -r requirements.txt."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS_FILE, "--quiet"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=120,
            )
            return result.returncode == 0, result.stderr[:500]
        except subprocess.TimeoutExpired:
            return False, "pip install timed out (120s)"
        except Exception as e:
            return False, str(e)

    def _restart_app(self):
        """Restart the application."""
        logger.info("Restarting in 2 seconds...")
        time.sleep(2)

        # Check if running under systemd
        if os.path.exists("/run/systemd/system"):
            logger.info("Systemd detected — exiting for auto-restart")
            sys.exit(0)
        else:
            logger.info("Restarting via os.execv")
            os.execv(sys.executable, [sys.executable] + sys.argv)

    def _report_status(self, status: str, version: str = ""):
        """Report update status to cloud."""
        try:
            if hasattr(self._cloud, 'report_update_status'):
                self._cloud.report_update_status(status, version)
            else:
                logger.debug(f"Cloud client doesn't have report_update_status, status: {status}")
        except Exception as e:
            logger.warning(f"Failed to report status '{status}': {e}")

    def _fail(self, error: str, version: str) -> Tuple[bool, str]:
        """Handle update failure."""
        logger.error(f"Update failed: {error}")
        self._report_status("failed", version)
        self._update_in_progress = False
        return False, error

    def _run_git(self, args: list) -> Tuple[bool, str]:
        """Run a git command."""
        cmd = ["git"] + args
        try:
            result = subprocess.run(
                cmd,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=60,
            )
            output = result.stdout + result.stderr
            if result.returncode != 0:
                logger.warning(f"Git command failed: {' '.join(cmd)}\n{output}")
            return result.returncode == 0, output.strip()
        except subprocess.TimeoutExpired:
            return False, f"Git command timed out: {' '.join(cmd)}"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def _file_hash(filepath: str) -> str:
        """Get MD5 hash of a file."""
        try:
            with open(filepath, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except FileNotFoundError:
            return ""

    # ================================================================
    # ARDUINO FIRMWARE FLASH
    # ================================================================

    def _flash_arduino(self) -> Tuple[bool, str]:
        """Compile and flash Arduino Nano firmware via avrdude.

        Steps:
          1. Release the serial port (close existing connection)
          2. Detect Arduino port (or use the one from the release callback)
          3. Compile .ino → .hex with arduino-cli (or use pre-compiled .hex)
          4. Flash via avrdude
          5. Wait for reboot (3.5s CH340 boot time)
          6. Verify with JSON ping
        """
        try:
            # --- Step 1: Release serial port & get port path ---
            arduino_port = None
            if self._arduino_release:
                try:
                    arduino_port = self._arduino_release()
                    logger.info(f"Arduino serial released (port was: {arduino_port})")
                except Exception as e:
                    logger.warning(f"Arduino release callback failed: {e}")

            # --- Step 2: Find Arduino port if not provided ---
            if not arduino_port:
                arduino_port = self._detect_arduino_port()
            if not arduino_port:
                return False, "No Arduino port found (/dev/ttyUSB* not available)"

            logger.info(f"Arduino flash target port: {arduino_port}")

            # Small delay to let OS release the port fully
            time.sleep(0.5)

            # --- Step 3: Compile firmware ---
            hex_file = None

            # Try arduino-cli first
            if self._has_command("arduino-cli"):
                logger.info("Compiling with arduino-cli...")
                ok, hex_file, msg = self._compile_arduino_cli()
                if not ok:
                    logger.warning(f"arduino-cli compile failed: {msg}")
                    hex_file = None

            # Fallback to pre-compiled .hex
            if not hex_file and os.path.exists(FIRMWARE_HEX):
                logger.info("Using pre-compiled .hex file")
                hex_file = FIRMWARE_HEX

            if not hex_file:
                return False, "No arduino-cli and no pre-compiled .hex — cannot flash"

            # --- Step 4: Flash with avrdude ---
            if not self._has_command("avrdude"):
                return False, "avrdude not installed (sudo apt install avrdude)"

            logger.info(f"Flashing {hex_file} → {arduino_port} ...")
            ok, output = self._run_avrdude(hex_file, arduino_port)
            if not ok:
                return False, f"avrdude failed: {output}"

            logger.info("avrdude flash done, waiting for Arduino reboot...")

            # --- Step 5: Wait for CH340 boot ---
            time.sleep(3.5)

            # --- Step 6: Verify with ping ---
            ping_ok = self._arduino_ping(arduino_port)
            if ping_ok:
                return True, f"Flash + verify OK on {arduino_port}"
            else:
                return True, f"Flash OK on {arduino_port} (ping verify failed — may need manual check)"

        except Exception as e:
            logger.exception(f"Arduino flash error: {e}")
            return False, str(e)

    def _detect_arduino_port(self) -> Optional[str]:
        """Auto-detect Arduino Nano (CH340) on /dev/ttyUSB*."""
        ports = sorted(globmod.glob("/dev/ttyUSB*"))
        if not ports:
            return None

        # Try to identify by opening briefly and reading boot data
        for port in ports:
            try:
                s = serial.Serial(port=port, baudrate=115200, timeout=1.0)
                time.sleep(0.5)
                if s.in_waiting:
                    data = s.read(s.in_waiting)
                    # PN532 sends binary 0x00 0x55 — skip it
                    if b'\x00\x55' in data or b'\x00\x00' in data:
                        s.close()
                        continue
                s.close()
                # If not PN532, likely Arduino (or at least a CH340)
                return port
            except Exception:
                continue

        # If all detection fails, return first port as best guess
        return ports[0] if ports else None

    def _compile_arduino_cli(self) -> Tuple[bool, Optional[str], str]:
        """Compile .ino to .hex using arduino-cli."""
        try:
            # Ensure core is installed
            subprocess.run(
                ["arduino-cli", "core", "install", "arduino:avr"],
                capture_output=True, text=True, timeout=120,
            )

            # Ensure libraries
            for lib in ["HX711", "ArduinoJson"]:
                subprocess.run(
                    ["arduino-cli", "lib", "install", lib],
                    capture_output=True, text=True, timeout=60,
                )

            # Compile
            result = subprocess.run(
                [
                    "arduino-cli", "compile",
                    "--fqbn", "arduino:avr:nano:cpu=atmega328old",
                    "--output-dir", BUILD_DIR,
                    FIRMWARE_DIR,
                ],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                return False, None, result.stderr[:500]

            # Find .hex output
            hex_path = os.path.join(BUILD_DIR, "smartlocker_nano.ino.hex")
            if not os.path.exists(hex_path):
                # Try alt naming
                hex_path = os.path.join(BUILD_DIR, "smartlocker_nano.ino.with_bootloader.hex")
            if os.path.exists(hex_path):
                return True, hex_path, "Compiled OK"
            return False, None, "Compiled but .hex not found"
        except subprocess.TimeoutExpired:
            return False, None, "Compile timed out (120s)"
        except Exception as e:
            return False, None, str(e)

    def _run_avrdude(self, hex_file: str, port: str) -> Tuple[bool, str]:
        """Flash .hex to Arduino Nano via avrdude."""
        try:
            result = subprocess.run(
                [
                    "avrdude",
                    "-p", "atmega328p",
                    "-c", "arduino",
                    "-P", port,
                    "-b", "57600",
                    "-U", f"flash:w:{hex_file}:i",
                ],
                capture_output=True, text=True, timeout=60,
            )
            output = (result.stdout + result.stderr).strip()
            return result.returncode == 0, output[-500:]
        except subprocess.TimeoutExpired:
            return False, "avrdude timed out (60s)"
        except Exception as e:
            return False, str(e)

    def _arduino_ping(self, port: str) -> bool:
        """Open serial to Arduino and verify it responds to ping."""
        try:
            s = serial.Serial(port=port, baudrate=115200, timeout=2.0)
            time.sleep(1.0)  # let Arduino settle after boot
            # Flush any boot messages
            if s.in_waiting:
                s.read(s.in_waiting)
            # Send ping
            s.write(b'{"cmd":"ping"}\n')
            s.flush()
            # Read response
            for _ in range(5):
                line = s.readline().decode("utf-8", errors="ignore").strip()
                if '"status":"ok"' in line:
                    s.close()
                    logger.info("Arduino ping OK after flash")
                    return True
            s.close()
            logger.warning("Arduino ping: no valid response")
            return False
        except Exception as e:
            logger.warning(f"Arduino ping failed: {e}")
            return False

    @staticmethod
    def _has_command(cmd: str) -> bool:
        """Check if a system command is available."""
        try:
            result = subprocess.run(
                ["which", cmd], capture_output=True, timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False
