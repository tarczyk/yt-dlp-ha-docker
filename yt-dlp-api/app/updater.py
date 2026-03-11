"""
Updater module — sole owner of yt-dlp update logic.

Owns:
- threading.Lock for update concurrency safety
- subprocess pip install call (always with timeout=120)
- /data/update-state.json persistence
- HA persistent notification on failure
- Error signal detection

Public interface:
    updater.update_if_needed(reason: str) -> UpdateResult
    updater.get_update_status() -> dict
    updater.is_updating() -> bool
    updater.contains_error_signal(output: str) -> bool
"""
import json
import logging
import os
import re
import subprocess
import tempfile
import threading
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

import yt_dlp

logger = logging.getLogger(__name__)

# Error signals that trigger ad-hoc update — owned here, never duplicated elsewhere.
# Uses regex with word boundaries for "bot" and "403" to avoid false positives
# ("robot", "chatbot", "1403", etc.). Always use contains_error_signal() — never
# iterate over this list directly with substring matching.
_ERROR_SIGNAL_RE = re.compile(
    r"Sign in|\b403\b|Forbidden|format not available|\bbot\b"
)


@dataclass
class UpdateResult:
    """Result of an update_if_needed() call."""
    success: bool
    version_before: str = ""
    version_after: str = ""
    error: str | None = None


class Updater:
    """
    Encapsulates all yt-dlp update logic.

    Threading model: single threading.Lock prevents concurrent updates.
    Works correctly only in single-process Flask deployment (threaded=True).
    """

    def __init__(self, state_path: str = "/data/update-state.json") -> None:
        self._state_path = state_path
        self._lock = threading.Lock()
        self._state: dict = {}
        self._load_state()

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _load_state(self) -> None:
        """Load state from JSON file. Creates with defaults if missing or corrupted."""
        if os.path.exists(self._state_path):
            try:
                with open(self._state_path, "r", encoding="utf-8") as f:
                    self._state = json.load(f)
                # Recovery: container may have crashed mid-update, leaving stale "updating" state.
                # /health would permanently show "updating" until the next actual update — reset to "failed".
                if self._state.get("update_status") == "updating":
                    logger.warning("[UPDATER] Stale 'updating' state detected on startup — resetting to 'failed'")
                    self._state["update_status"] = "failed"
                    self._save_state()
                return
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("[UPDATER] State file unreadable (%s), recreating with defaults", exc)

        # Create default state — no external network calls
        current_version = yt_dlp.version.__version__
        self._state = {
            "last_update_attempt": None,
            "last_successful_update": None,
            "current_version": current_version,
            "latest_version": current_version,  # conservative: assume up to date until first pip run
            "update_status": "ok",
            "last_error": None,
        }
        self._save_state()

    def _save_state(self) -> None:
        """Persist current state to JSON file. Uses atomic write (temp + rename)."""
        state_dir = os.path.dirname(self._state_path)
        try:
            if state_dir:
                os.makedirs(state_dir, exist_ok=True)
            dir_for_tmp = state_dir if state_dir else "."
            fd, tmp_path = tempfile.mkstemp(dir=dir_for_tmp, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self._state, f, indent=2)
                os.replace(tmp_path, self._state_path)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except OSError as exc:
            logger.error("[UPDATER] Failed to save state file: %s", exc)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_update_status(self) -> dict:
        """
        Return current update status for /health endpoint.
        Makes NO external network calls — reads from in-memory state only.
        """
        return {
            "current_version": self._state.get("current_version", ""),
            "latest_version": self._state.get("latest_version", ""),
            "last_update": self._state.get("last_successful_update"),
            "update_status": self._state.get("update_status", "ok"),
        }

    def is_updating(self) -> bool:
        """
        Return True if an update subprocess is currently running.
        Uses lock try-acquire to avoid TOCTOU race with _updating flag.
        """
        acquired = self._lock.acquire(blocking=False)
        if acquired:
            self._lock.release()
            return False
        return True

    def contains_error_signal(self, output: str) -> bool:
        """
        Return True if download output contains any known yt-dlp error signal.
        This is the single source of truth for error signal detection.
        Never duplicate this logic elsewhere (especially not in yt_dlp_manager.py).
        Uses regex for word-boundary matching on "bot" to avoid false positives.
        """
        return bool(_ERROR_SIGNAL_RE.search(output))

    def update_if_needed(self, reason: str) -> UpdateResult:
        """
        Run `pip install -U yt-dlp` with timeout=120.

        Returns immediately (success=False) if another update is already running.

        Args:
            reason: "scheduled" | "ad-hoc" — used for log component tag

        Returns:
            UpdateResult with success flag, version diff, and optional error message
        """
        # Non-blocking acquire: if another thread holds the lock, return immediately
        acquired = self._lock.acquire(blocking=False)
        if not acquired:
            logger.info("[UPDATER] Update already in progress, skipping (reason=%s)", reason)
            return UpdateResult(success=False, error="update already in progress")

        component = "AUTO-UPDATE" if reason == "scheduled" else "AD-HOC-UPDATE"
        version_before = self._state.get("current_version", "")

        try:
            # Mark as updating in state
            now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            self._state["update_status"] = "updating"
            self._state["last_update_attempt"] = now_str
            self._save_state()

            logger.info("[%s] Starting yt-dlp update (reason=%s, current=%s)",
                        component, reason, version_before)

            result = subprocess.run(
                ["pip", "install", "-U", "yt-dlp"],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                version_after = self._get_installed_version()
                now_success = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                self._state["update_status"] = "ok"
                self._state["current_version"] = version_after
                self._state["latest_version"] = version_after
                self._state["last_successful_update"] = now_success
                self._state["last_error"] = None
                self._save_state()

                logger.info("[%s] yt-dlp updated: %s → %s", component, version_before, version_after)
                return UpdateResult(
                    success=True,
                    version_before=version_before,
                    version_after=version_after,
                )
            else:
                error_msg = f"subprocess exit code {result.returncode}"
                self._state["update_status"] = "failed"
                self._state["last_error"] = error_msg
                self._save_state()
                logger.error("[UPDATER] Update failed: %s", error_msg)
                self._send_ha_notification(error_msg, reason)
                return UpdateResult(success=False, version_before=version_before, error=error_msg)

        except subprocess.TimeoutExpired:
            error_msg = "timeout after 120s"
            self._state["update_status"] = "failed"
            self._state["last_error"] = error_msg
            self._save_state()
            logger.error("[UPDATER] Update failed: %s", error_msg)
            self._send_ha_notification(error_msg, reason)
            return UpdateResult(success=False, version_before=version_before, error=error_msg)

        except Exception as exc:  # noqa: BLE001
            error_msg = str(exc)
            self._state["update_status"] = "failed"
            self._state["last_error"] = error_msg
            self._save_state()
            logger.error("[UPDATER] Update failed with unexpected error: %s", exc)
            self._send_ha_notification(error_msg, reason)
            return UpdateResult(success=False, version_before=version_before, error=error_msg)

        finally:
            self._lock.release()

    def _send_ha_notification(self, error_type: str, reason: str) -> None:
        """
        Send persistent notification to Home Assistant on update failure.

        Gracefully degrades when SUPERVISOR_TOKEN is not set (Docker mode).
        Ordering requirement: always call BEFORE setting task status to TASK_STATUS_FAILED.

        Args:
            error_type: Human-readable error description (e.g. "timeout after 120s")
            reason: "scheduled" | "ad-hoc"
        """
        token = os.environ.get("SUPERVISOR_TOKEN")
        if not token:
            logger.warning("[HA-NOTIFY] SUPERVISOR_TOKEN not set — log only mode")
            return

        current_version = self._state.get("current_version", "unknown")
        timestamp_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        message = f"{error_type}. yt-dlp: {current_version}. {timestamp_utc}"
        payload = json.dumps({
            "title": "⚠️ ha-yt-dlp",
            "message": message,
        }).encode("utf-8")

        url = "http://supervisor/core/api/services/persistent_notification/create"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

        for attempt in range(2):
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: F841
                    logger.info("[HA-NOTIFY] Notification sent (reason=%s)", reason)
                    return
            except Exception as exc:
                logger.warning("[HA-NOTIFY] Failed to send notification (attempt %d/2): %s", attempt + 1, exc)
            if attempt == 0:
                time.sleep(5)

        logger.critical("[HA-NOTIFY] Failed to send HA notification after retry")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_installed_version(self) -> str:
        """
        Return the currently installed yt-dlp version.
        Separated from update_if_needed for testability.
        """
        import importlib
        import yt_dlp as yt_dlp_module
        try:
            importlib.reload(yt_dlp_module.version)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[UPDATER] Failed to reload yt_dlp.version after update: %s", exc)
        return yt_dlp_module.version.__version__
