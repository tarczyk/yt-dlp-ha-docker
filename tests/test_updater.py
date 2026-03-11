"""
Tests for app.updater module (Story 1.1).

Run with:
    cd /repo && PYTHONPATH=yt-dlp-api pytest tests/test_updater.py -v
"""
import json
import subprocess
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from app.updater import UpdateResult, Updater


# ---------------------------------------------------------------------------
# AC3 / AC4 — contains_error_signal
# ---------------------------------------------------------------------------

class TestContainsErrorSignal:
    def setup_method(self, method):
        # Lightweight construction — no file I/O needed for this class
        pass

    @pytest.fixture
    def updater(self, tmp_path):
        return Updater(state_path=str(tmp_path / "state.json"))

    def test_sign_in_signal(self, updater):
        assert updater.contains_error_signal("Sign in to confirm you're not a bot") is True

    def test_bot_signal(self, updater):
        assert updater.contains_error_signal("Detected as bot, please try again") is True

    def test_403_signal(self, updater):
        assert updater.contains_error_signal("HTTP Error 403: Forbidden") is True

    def test_forbidden_signal(self, updater):
        assert updater.contains_error_signal("Forbidden") is True

    def test_format_not_available_signal(self, updater):
        # Signal is "format not available" (exact substring match per PRD)
        assert updater.contains_error_signal("ERROR: format not available") is True

    def test_clean_output_returns_false(self, updater):
        assert updater.contains_error_signal("Downloaded 100%") is False

    def test_empty_string_returns_false(self, updater):
        assert updater.contains_error_signal("") is False

    def test_partial_match_not_counted(self, updater):
        # Ensure we don't false-positive on similar but non-matching strings
        assert updater.contains_error_signal("signing in") is False

    def test_bot_does_not_match_robot(self, updater):
        # "bot" signal uses word boundary — must not match inside longer words
        assert updater.contains_error_signal("I am a robot") is False

    def test_bot_does_not_match_chatbot(self, updater):
        assert updater.contains_error_signal("powered by chatbot") is False

    def test_bot_matches_standalone_word(self, updater):
        # Exact word "bot" must still match
        assert updater.contains_error_signal("Sign in to confirm you're not a bot") is True


# ---------------------------------------------------------------------------
# AC1 — __init__ state file creation (no existing file)
# ---------------------------------------------------------------------------

class TestInitStateCreation:
    def test_creates_state_file_if_missing(self, tmp_path):
        state_path = tmp_path / "update-state.json"
        assert not state_path.exists()

        updater = Updater(state_path=str(state_path))

        assert state_path.exists()

    def test_default_state_keys(self, tmp_path):
        state_path = tmp_path / "update-state.json"
        updater = Updater(state_path=str(state_path))

        with open(state_path) as f:
            state = json.load(f)

        assert "current_version" in state
        assert "latest_version" in state
        assert "update_status" in state
        assert state["update_status"] == "ok"
        assert state["current_version"] == state["latest_version"]

    def test_default_state_no_update_history(self, tmp_path):
        state_path = tmp_path / "update-state.json"
        updater = Updater(state_path=str(state_path))

        with open(state_path) as f:
            state = json.load(f)

        assert state["last_update_attempt"] is None
        assert state["last_successful_update"] is None
        assert state["last_error"] is None

    def test_current_version_set_from_yt_dlp(self, tmp_path):
        import yt_dlp
        state_path = tmp_path / "update-state.json"
        updater = Updater(state_path=str(state_path))

        status = updater.get_update_status()
        assert status["current_version"] == yt_dlp.version.__version__


# ---------------------------------------------------------------------------
# AC1 — __init__ loads existing state file
# ---------------------------------------------------------------------------

class TestInitStateLoad:
    def test_loads_existing_state(self, tmp_path):
        state_path = tmp_path / "update-state.json"
        existing = {
            "current_version": "2026.01.01",
            "latest_version": "2026.01.01",
            "update_status": "ok",
            "last_update_attempt": "2026-01-01T03:00:00Z",
            "last_successful_update": "2026-01-01T03:00:00Z",
            "last_error": None,
        }
        state_path.write_text(json.dumps(existing))

        updater = Updater(state_path=str(state_path))
        status = updater.get_update_status()

        assert status["current_version"] == "2026.01.01"
        assert status["update_status"] == "ok"
        assert status["last_update"] == "2026-01-01T03:00:00Z"

    def test_corrupted_state_file_creates_defaults(self, tmp_path):
        state_path = tmp_path / "update-state.json"
        state_path.write_text("{ not valid json {{")

        # Should not raise — fall back to defaults
        updater = Updater(state_path=str(state_path))
        status = updater.get_update_status()
        assert status["update_status"] == "ok"


# ---------------------------------------------------------------------------
# AC2 — get_update_status returns correct keys, no network calls
# ---------------------------------------------------------------------------

class TestGetUpdateStatus:
    def test_returns_required_keys(self, tmp_path):
        updater = Updater(state_path=str(tmp_path / "state.json"))
        status = updater.get_update_status()

        assert "current_version" in status
        assert "latest_version" in status
        assert "last_update" in status
        assert "update_status" in status

    def test_no_network_calls(self, tmp_path):
        updater = Updater(state_path=str(tmp_path / "state.json"))

        with patch("urllib.request.urlopen") as mock_url:
            _ = updater.get_update_status()

        mock_url.assert_not_called()

    def test_no_subprocess_calls(self, tmp_path):
        updater = Updater(state_path=str(tmp_path / "state.json"))

        with patch("subprocess.run") as mock_sub:
            _ = updater.get_update_status()

        mock_sub.assert_not_called()


# ---------------------------------------------------------------------------
# AC5 / AC6 — update_if_needed success path
# ---------------------------------------------------------------------------

class TestUpdateIfNeededSuccess:
    def _make_mock_result(self, returncode=0):
        mock_result = MagicMock()
        mock_result.returncode = returncode
        mock_result.stdout = "Successfully installed yt-dlp-2026.03.10"
        mock_result.stderr = ""
        return mock_result

    def test_calls_subprocess_with_exact_args(self, tmp_path):
        updater = Updater(state_path=str(tmp_path / "state.json"))

        with patch("subprocess.run", return_value=self._make_mock_result()) as mock_sub:
            with patch.object(updater, "_get_installed_version", return_value="2026.03.10"):
                updater.update_if_needed("test")

        mock_sub.assert_called_once_with(
            ["pip", "install", "-U", "yt-dlp"],
            capture_output=True,
            text=True,
            timeout=120,
        )

    def test_returns_success_result(self, tmp_path):
        updater = Updater(state_path=str(tmp_path / "state.json"))

        with patch("subprocess.run", return_value=self._make_mock_result()):
            with patch.object(updater, "_get_installed_version", return_value="2026.03.10"):
                result = updater.update_if_needed("test")

        assert result.success is True
        assert result.error is None

    def test_version_before_after_populated(self, tmp_path):
        state_path = tmp_path / "state.json"
        # Pre-set current_version in state
        existing = {
            "current_version": "2026.01.01",
            "latest_version": "2026.01.01",
            "update_status": "ok",
            "last_update_attempt": None,
            "last_successful_update": None,
            "last_error": None,
        }
        state_path.write_text(json.dumps(existing))

        updater = Updater(state_path=str(state_path))

        with patch("subprocess.run", return_value=self._make_mock_result()):
            with patch.object(updater, "_get_installed_version", return_value="2026.03.10"):
                result = updater.update_if_needed("test")

        assert result.version_before == "2026.01.01"
        assert result.version_after == "2026.03.10"

    def test_state_saved_with_ok_status(self, tmp_path):
        state_path = tmp_path / "state.json"
        updater = Updater(state_path=str(state_path))

        with patch("subprocess.run", return_value=self._make_mock_result()):
            with patch.object(updater, "_get_installed_version", return_value="2026.03.10"):
                updater.update_if_needed("test")

        with open(state_path) as f:
            state = json.load(f)

        assert state["update_status"] == "ok"
        assert state["current_version"] == "2026.03.10"
        assert state["latest_version"] == "2026.03.10"
        assert state["last_successful_update"] is not None
        assert state["last_error"] is None

    def test_last_successful_update_is_iso8601_utc(self, tmp_path):
        updater = Updater(state_path=str(tmp_path / "state.json"))

        with patch("subprocess.run", return_value=self._make_mock_result()):
            with patch.object(updater, "_get_installed_version", return_value="2026.03.10"):
                updater.update_if_needed("test")

        status = updater.get_update_status()
        # Should be ISO 8601 UTC format with Z suffix
        assert status["last_update"] is not None
        assert "T" in status["last_update"]
        assert status["last_update"].endswith("Z")

    def test_last_update_attempt_set_on_start(self, tmp_path):
        # AC6: last_update_attempt must be persisted when update begins
        state_path = tmp_path / "state.json"
        updater = Updater(state_path=str(state_path))

        with patch("subprocess.run", return_value=self._make_mock_result()):
            with patch.object(updater, "_get_installed_version", return_value="2026.03.10"):
                updater.update_if_needed("test")

        with open(state_path) as f:
            state = json.load(f)

        assert state["last_update_attempt"] is not None
        assert "T" in state["last_update_attempt"]
        assert state["last_update_attempt"].endswith("Z")


# ---------------------------------------------------------------------------
# AC7 — update_if_needed timeout failure
# ---------------------------------------------------------------------------

class TestUpdateIfNeededTimeout:
    def test_timeout_returns_failure_result(self, tmp_path):
        updater = Updater(state_path=str(tmp_path / "state.json"))

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="pip", timeout=120)):
            result = updater.update_if_needed("test")

        assert result.success is False
        assert result.error == "timeout after 120s"

    def test_timeout_saves_failed_state(self, tmp_path):
        state_path = tmp_path / "state.json"
        updater = Updater(state_path=str(state_path))

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="pip", timeout=120)):
            updater.update_if_needed("test")

        with open(state_path) as f:
            state = json.load(f)

        assert state["update_status"] == "failed"

    def test_nonzero_returncode_returns_failure(self, tmp_path):
        updater = Updater(state_path=str(tmp_path / "state.json"))
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Could not find a version"

        with patch("subprocess.run", return_value=mock_result):
            result = updater.update_if_needed("test")

        assert result.success is False
        assert result.error is not None

    def test_nonzero_returncode_saves_failed_state(self, tmp_path):
        state_path = tmp_path / "state.json"
        updater = Updater(state_path=str(state_path))
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error"

        with patch("subprocess.run", return_value=mock_result):
            updater.update_if_needed("test")

        with open(state_path) as f:
            state = json.load(f)

        assert state["update_status"] == "failed"

    def test_unexpected_exception_returns_failure(self, tmp_path):
        """Generic Exception (e.g. FileNotFoundError when pip missing) → success=False."""
        updater = Updater(state_path=str(tmp_path / "state.json"))

        with patch("subprocess.run", side_effect=FileNotFoundError("pip not found")):
            result = updater.update_if_needed("test")

        assert result.success is False
        assert result.error is not None
        assert "pip not found" in result.error

    def test_unexpected_exception_saves_failed_state(self, tmp_path):
        """Generic Exception → state persisted as 'failed'."""
        state_path = tmp_path / "state.json"
        updater = Updater(state_path=str(state_path))

        with patch("subprocess.run", side_effect=RuntimeError("unexpected internal error")):
            updater.update_if_needed("test")

        with open(state_path) as f:
            state = json.load(f)
        assert state["update_status"] == "failed"


# ---------------------------------------------------------------------------
# AC8 — is_updating / concurrent guard
# ---------------------------------------------------------------------------

class TestIsUpdatingConcurrency:
    def test_is_updating_false_when_idle(self, tmp_path):
        updater = Updater(state_path=str(tmp_path / "state.json"))
        assert updater.is_updating() is False

    def test_is_updating_true_during_update(self, tmp_path):
        updater = Updater(state_path=str(tmp_path / "state.json"))
        observed_during = []
        update_started = threading.Event()

        def slow_subprocess(*args, **kwargs):
            update_started.set()
            time.sleep(0.15)
            mock_result = MagicMock()
            mock_result.returncode = 0
            return mock_result

        def run_update():
            with patch("subprocess.run", side_effect=slow_subprocess):
                with patch.object(updater, "_get_installed_version", return_value="2026.03.10"):
                    updater.update_if_needed("test")

        t = threading.Thread(target=run_update)
        t.start()
        update_started.wait(timeout=2.0)  # Wait until subprocess has started
        observed_during.append(updater.is_updating())
        t.join()

        assert True in observed_during  # Was True while lock was held

    def test_concurrent_call_returns_immediately(self, tmp_path):
        updater = Updater(state_path=str(tmp_path / "state.json"))
        results = []

        def slow_subprocess(*args, **kwargs):
            time.sleep(0.2)
            mock_result = MagicMock()
            mock_result.returncode = 0
            return mock_result

        def first_update():
            with patch("subprocess.run", side_effect=slow_subprocess):
                with patch.object(updater, "_get_installed_version", return_value="2026.03.10"):
                    results.append(("first", updater.update_if_needed("test")))

        def second_update():
            time.sleep(0.05)  # Start slightly after first
            results.append(("second", updater.update_if_needed("test2")))

        t1 = threading.Thread(target=first_update)
        t2 = threading.Thread(target=second_update)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        second_result = next(r for key, r in results if key == "second")
        # Second call should have returned quickly without running subprocess
        assert second_result.success is False
        assert "in progress" in second_result.error.lower() or second_result.error is not None

    def test_is_updating_false_after_update_completes(self, tmp_path):
        updater = Updater(state_path=str(tmp_path / "state.json"))
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            with patch.object(updater, "_get_installed_version", return_value="2026.03.10"):
                updater.update_if_needed("test")

        assert updater.is_updating() is False

    def test_is_updating_false_after_failed_update(self, tmp_path):
        updater = Updater(state_path=str(tmp_path / "state.json"))

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="pip", timeout=120)):
            updater.update_if_needed("test")

        assert updater.is_updating() is False


# ---------------------------------------------------------------------------
# AI-Review M3 — stale "updating" state recovery on startup
# ---------------------------------------------------------------------------

class TestStaleUpdatingStateRecovery:
    def test_stale_updating_reset_to_failed_on_startup(self, tmp_path):
        """After a container crash mid-update, state may be left as 'updating'.
        _load_state() must reset this to 'failed' so /health never shows stale 'updating'.
        """
        state_path = tmp_path / "state.json"
        # Write a state file left behind by a crashed update
        stale_state = {
            "current_version": "2026.01.01",
            "latest_version": "2026.01.01",
            "update_status": "updating",  # stale — container crashed mid-update
            "last_update_attempt": "2026-01-01T03:00:00Z",
            "last_successful_update": None,
            "last_error": None,
        }
        state_path.write_text(json.dumps(stale_state))

        updater = Updater(state_path=str(state_path))

        status = updater.get_update_status()
        assert status["update_status"] == "failed", (
            "Stale 'updating' state must be reset to 'failed' on startup"
        )

    def test_stale_updating_persisted_as_failed(self, tmp_path):
        """Recovery must also persist the 'failed' status to the state file."""
        state_path = tmp_path / "state.json"
        stale_state = {
            "current_version": "2026.01.01",
            "latest_version": "2026.01.01",
            "update_status": "updating",
            "last_update_attempt": "2026-01-01T03:00:00Z",
            "last_successful_update": None,
            "last_error": None,
        }
        state_path.write_text(json.dumps(stale_state))

        Updater(state_path=str(state_path))

        with open(state_path) as f:
            saved = json.load(f)
        assert saved["update_status"] == "failed"

    def test_ok_state_not_modified_on_startup(self, tmp_path):
        """Normal 'ok' state must NOT be changed during startup."""
        state_path = tmp_path / "state.json"
        normal_state = {
            "current_version": "2026.03.07",
            "latest_version": "2026.03.07",
            "update_status": "ok",
            "last_update_attempt": "2026-03-07T03:00:00Z",
            "last_successful_update": "2026-03-07T03:00:00Z",
            "last_error": None,
        }
        state_path.write_text(json.dumps(normal_state))

        updater = Updater(state_path=str(state_path))

        assert updater.get_update_status()["update_status"] == "ok"

    def test_failed_state_not_modified_on_startup(self, tmp_path):
        """Existing 'failed' state must stay 'failed' — no double-recovery."""
        state_path = tmp_path / "state.json"
        failed_state = {
            "current_version": "2026.03.07",
            "latest_version": "2026.03.07",
            "update_status": "failed",
            "last_update_attempt": "2026-03-07T03:00:00Z",
            "last_successful_update": None,
            "last_error": "timeout after 120s",
        }
        state_path.write_text(json.dumps(failed_state))

        updater = Updater(state_path=str(state_path))

        assert updater.get_update_status()["update_status"] == "failed"


# ---------------------------------------------------------------------------
# Story 2.2 — HA Persistent Notification (AC1–AC7)
# ---------------------------------------------------------------------------

class TestHaNotification:
    """Story 2.2 tests: _send_ha_notification() + integration with update_if_needed()."""

    @staticmethod
    def _mock_urlopen_success():
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    # 3.1 — SUPERVISOR_TOKEN set + update timeout → urlopen called with correct URL/headers
    def test_timeout_fires_notification_with_correct_url_and_headers(self, tmp_path, ha_supervisor_token):
        updater = Updater(state_path=str(tmp_path / "state.json"))
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="pip", timeout=120)):
            with patch("urllib.request.urlopen", return_value=self._mock_urlopen_success()) as mock_open:
                with patch("time.sleep"):
                    updater.update_if_needed("scheduled")
        mock_open.assert_called()
        req = mock_open.call_args[0][0]
        assert req.full_url == "http://supervisor/core/api/services/persistent_notification/create"
        assert req.get_header("Authorization") == f"Bearer {ha_supervisor_token}"
        assert req.get_header("Content-type") == "application/json"

    # 3.2 — SUPERVISOR_TOKEN set + non-zero returncode → notification fired
    def test_nonzero_returncode_fires_notification(self, tmp_path, ha_supervisor_token):
        updater = Updater(state_path=str(tmp_path / "state.json"))
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error"
        with patch("subprocess.run", return_value=mock_result):
            with patch("urllib.request.urlopen", return_value=self._mock_urlopen_success()) as mock_open:
                updater.update_if_needed("ad-hoc")
        mock_open.assert_called()

    # 3.3 — first HTTP call raises URLError, second succeeds → no logger.critical
    def test_retry_on_first_failure_no_critical_log(self, tmp_path, ha_supervisor_token, caplog):
        import logging
        from urllib.error import URLError
        updater = Updater(state_path=str(tmp_path / "state.json"))
        call_count = [0]

        def urlopen_side_effect(req, timeout=None):
            call_count[0] += 1
            if call_count[0] == 1:
                raise URLError("connection refused")
            return self._mock_urlopen_success()

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="pip", timeout=120)):
            with patch("urllib.request.urlopen", side_effect=urlopen_side_effect):
                with patch("time.sleep"):
                    with caplog.at_level(logging.CRITICAL):
                        updater.update_if_needed("scheduled")

        assert call_count[0] == 2
        assert not any(r.levelno == logging.CRITICAL for r in caplog.records)

    # 3.4 — both HTTP calls fail → logger.critical with [HA-NOTIFY] message
    def test_both_retries_fail_logs_critical(self, tmp_path, ha_supervisor_token, caplog):
        import logging
        from urllib.error import URLError
        updater = Updater(state_path=str(tmp_path / "state.json"))

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="pip", timeout=120)):
            with patch("urllib.request.urlopen", side_effect=URLError("connection refused")):
                with patch("time.sleep"):
                    with caplog.at_level(logging.CRITICAL):
                        updater.update_if_needed("scheduled")

        assert any(
            "[HA-NOTIFY] Failed to send HA notification after retry" in r.message
            for r in caplog.records
        )

    # 3.5 — SUPERVISOR_TOKEN not set → no HTTP call, warning with [HA-NOTIFY]
    def test_no_token_no_http_call_warning_logged(self, tmp_path, no_supervisor_token, caplog):
        import logging
        updater = Updater(state_path=str(tmp_path / "state.json"))

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="pip", timeout=120)):
            with patch("urllib.request.urlopen") as mock_open:
                with caplog.at_level(logging.WARNING):
                    updater.update_if_needed("scheduled")

        mock_open.assert_not_called()
        assert any("[HA-NOTIFY] SUPERVISOR_TOKEN not set" in r.message for r in caplog.records)

    # 3.6 — update succeeds → _send_ha_notification NOT called (AC4)
    def test_update_success_no_notification(self, tmp_path, ha_supervisor_token):
        updater = Updater(state_path=str(tmp_path / "state.json"))
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            with patch.object(updater, "_get_installed_version", return_value="2026.03.10"):
                with patch.object(updater, "_send_ha_notification") as mock_notify:
                    result = updater.update_if_needed("scheduled")
        assert result.success is True
        mock_notify.assert_not_called()

    # 3.8 — generic Exception failure path (e.g. pip not found) triggers HA notification (AC6)
    def test_generic_exception_fires_notification(self, tmp_path, ha_supervisor_token):
        updater = Updater(state_path=str(tmp_path / "state.json"))
        with patch("subprocess.run", side_effect=FileNotFoundError("pip not found")):
            with patch("urllib.request.urlopen", return_value=self._mock_urlopen_success()) as mock_open:
                result = updater.update_if_needed("scheduled")
        assert result.success is False
        assert "pip not found" in result.error
        mock_open.assert_called()

    # 3.7 — notification payload contains error_type, current_version, UTC timestamp (AC1/FR18)
    def test_notification_payload_contains_required_fields(self, tmp_path, ha_supervisor_token):
        import re as re_mod
        state_path = tmp_path / "state.json"
        existing = {
            "current_version": "2026.03.07",
            "latest_version": "2026.03.07",
            "update_status": "ok",
            "last_update_attempt": None,
            "last_successful_update": None,
            "last_error": None,
        }
        state_path.write_text(json.dumps(existing))
        updater = Updater(state_path=str(state_path))

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="pip", timeout=120)):
            with patch("urllib.request.urlopen", return_value=self._mock_urlopen_success()) as mock_open:
                with patch("time.sleep"):
                    updater.update_if_needed("scheduled")

        req = mock_open.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))
        assert payload["title"] == "⚠️ ha-yt-dlp"
        assert "timeout after 120s" in payload["message"]
        assert "2026.03.07" in payload["message"]
        assert re_mod.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", payload["message"])
