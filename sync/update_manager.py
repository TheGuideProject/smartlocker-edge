"""
OTA Update Manager - Git-based firmware updates for SmartLocker Edge.

Flow:
1. Cloud config includes {"update": {"version": "1.3.0", "branch": "master"}}
2. UpdateManager compares against current version from config/VERSION
3. If different: git fetch → git reset --hard → pip install → verify → restart
4. If verify fails: rollback to previous commit
5. Reports status back to cloud via cloud_client
"""

import os
import sys
import time
import logging
import subprocess
import hashlib
from typing import Optional, Tuple

logger = logging.getLogger("smartlocker.update")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_FILE = os.path.join(PROJECT_ROOT, "config", "VERSION")
REQUIREMENTS_FILE = os.path.join(PROJECT_ROOT, "requirements.txt")


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

            # Step 3: Save requirements hash for comparison
            old_req_hash = self._file_hash(REQUIREMENTS_FILE)

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
