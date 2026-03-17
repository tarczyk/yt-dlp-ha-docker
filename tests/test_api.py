import pytest
import app.api as api_module
from app.updater import Updater, UpdateResult
from app.yt_dlp_manager import (
    TASK_STATUS_DOWNLOADING,
    TASK_STATUS_UPDATING,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
)
from unittest.mock import patch, MagicMock

_TASK_ID = "test-task-adhoc-1"


def _make_task(task_id=_TASK_ID, url="https://youtube.com/watch?v=test", fmt="mp4"):
    with api_module._tasks_lock:
        api_module._tasks[task_id] = {
            "task_id": task_id,
            "status": "queued",
            "url": url,
            "cancelled": False,
            "format": fmt,
        }


def _inject_updater(updater):
    old = api_module._updater
    api_module._updater = updater
    return old


class TestRunDownloadAdHocUpdate:
    def setup_method(self, method):
        with api_module._tasks_lock:
            api_module._tasks.clear()

    def test_run_download_no_update_on_clean_error(self):
        """Non-error-signal exception → TASK_STATUS_FAILED, no update triggered"""
        _make_task()
        updater = MagicMock(spec=Updater)
        updater.contains_error_signal.return_value = False
        old = _inject_updater(updater)
        try:
            with patch("app.api.download_video", side_effect=Exception("network timeout")):
                api_module._run_download(_TASK_ID, "https://youtube.com/watch?v=test", "mp4")
        finally:
            api_module._updater = old

        with api_module._tasks_lock:
            task = api_module._tasks[_TASK_ID]
        assert task["status"] == TASK_STATUS_FAILED
        updater.update_if_needed.assert_not_called()

    def test_run_download_triggers_update_on_error_signal(self):
        """Error signal detected → status = TASK_STATUS_UPDATING before update_if_needed called"""
        _make_task()
        updater = MagicMock(spec=Updater)
        updater.contains_error_signal.return_value = True

        status_at_update_call = []

        def capture_status_then_fail(reason):
            with api_module._tasks_lock:
                status_at_update_call.append(api_module._tasks[_TASK_ID]["status"])
            return UpdateResult(success=False, error="failed")

        updater.update_if_needed.side_effect = capture_status_then_fail
        old = _inject_updater(updater)
        try:
            with patch("app.api.download_video", side_effect=Exception("Sign in to confirm")):
                api_module._run_download(_TASK_ID, "https://youtube.com/watch?v=test", "mp4")
        finally:
            api_module._updater = old

        updater.update_if_needed.assert_called_once_with("ad-hoc")
        assert status_at_update_call == [TASK_STATUS_UPDATING]

    def test_run_download_retry_succeeds_after_update(self):
        """Update success + retry success → TASK_STATUS_COMPLETED"""
        _make_task()
        updater = MagicMock(spec=Updater)
        updater.contains_error_signal.return_value = True
        updater.update_if_needed.return_value = UpdateResult(
            success=True, version_before="2026.01.01", version_after="2026.03.10"
        )
        old = _inject_updater(updater)
        try:
            call_count = [0]

            def download_side_effect(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise Exception("403 Forbidden")
                return {"title": "Test Video"}

            with patch("app.api.download_video", side_effect=download_side_effect):
                api_module._run_download(_TASK_ID, "https://youtube.com/watch?v=test", "mp4")
        finally:
            api_module._updater = old

        with api_module._tasks_lock:
            task = api_module._tasks[_TASK_ID]
        assert task["status"] == TASK_STATUS_COMPLETED

    def test_run_download_retry_fails_after_update(self):
        """Update success + retry fails → TASK_STATUS_FAILED"""
        _make_task()
        updater = MagicMock(spec=Updater)
        updater.contains_error_signal.return_value = True
        updater.update_if_needed.return_value = UpdateResult(
            success=True, version_before="2026.01.01", version_after="2026.03.10"
        )
        old = _inject_updater(updater)
        try:
            with patch("app.api.download_video", side_effect=Exception("still failing")):
                api_module._run_download(_TASK_ID, "https://youtube.com/watch?v=test", "mp4")
        finally:
            api_module._updater = old

        with api_module._tasks_lock:
            task = api_module._tasks[_TASK_ID]
        assert task["status"] == TASK_STATUS_FAILED

    def test_run_download_no_updater_falls_back_to_failed(self):
        """_updater is None → error signal exception still results in TASK_STATUS_FAILED"""
        _make_task()
        old = _inject_updater(None)
        try:
            with patch("app.api.download_video", side_effect=Exception("Sign in to confirm")):
                api_module._run_download(_TASK_ID, "https://youtube.com/watch?v=test", "mp4")
        finally:
            api_module._updater = old

        with api_module._tasks_lock:
            task = api_module._tasks[_TASK_ID]
        assert task["status"] == TASK_STATUS_FAILED
        assert "Sign in" in task["error"]

    def test_run_download_failed_update_no_retry(self):
        """Update fails → TASK_STATUS_FAILED, download_video called only once"""
        _make_task()
        updater = MagicMock(spec=Updater)
        updater.contains_error_signal.return_value = True
        updater.update_if_needed.return_value = UpdateResult(success=False, error="timeout after 120s")
        old = _inject_updater(updater)
        try:
            with patch("app.api.download_video", side_effect=Exception("bot")) as mock_dl:
                api_module._run_download(_TASK_ID, "https://youtube.com/watch?v=test", "mp4")
                assert mock_dl.call_count == 1  # No retry
        finally:
            api_module._updater = old

        with api_module._tasks_lock:
            task = api_module._tasks[_TASK_ID]
        assert task["status"] == TASK_STATUS_FAILED


class TestCancellationFixes:
    """AI-Review H1 + M1 — cancellation correctness in update/retry path."""

    def setup_method(self, method):
        with api_module._tasks_lock:
            api_module._tasks.clear()

    def test_cancelled_during_retry_sets_cancelled_status(self):
        """H1: DownloadCancelledError in retry path → status 'cancelled', not TASK_STATUS_FAILED."""
        from app.yt_dlp_manager import DownloadCancelledError

        _make_task()
        updater = MagicMock(spec=Updater)
        updater.contains_error_signal.return_value = True
        updater.update_if_needed.return_value = UpdateResult(
            success=True, version_before="2026.01.01", version_after="2026.03.10"
        )
        old = _inject_updater(updater)
        try:
            call_count = [0]

            def download_side_effect(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise Exception("403 Forbidden")
                raise DownloadCancelledError("Cancelled by user")

            with patch("app.api.download_video", side_effect=download_side_effect):
                api_module._run_download(_TASK_ID, "https://youtube.com/watch?v=test", "mp4")
        finally:
            api_module._updater = old

        with api_module._tasks_lock:
            task = api_module._tasks[_TASK_ID]
        assert task["status"] == "cancelled", (
            f"Expected 'cancelled' but got '{task['status']}' — DownloadCancelledError in retry must not become FAILED"
        )

    def test_cancelled_after_update_before_retry_skips_download(self):
        """L3: Task cancelled after pip install succeeds but before retry starts — must not attempt retry."""
        _make_task()
        updater = MagicMock(spec=Updater)
        updater.contains_error_signal.return_value = True
        updater.update_if_needed.return_value = UpdateResult(
            success=True, version_before="2026.01.01", version_after="2026.03.10"
        )
        old = _inject_updater(updater)
        try:
            call_count = [0]

            def download_side_effect(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    # Cancel task right as update completes, before retry
                    with api_module._tasks_lock:
                        api_module._tasks[_TASK_ID]["cancelled"] = True
                    raise Exception("403 Forbidden")
                return {"title": "Should not reach here"}

            with patch("app.api.download_video", side_effect=download_side_effect):
                api_module._run_download(_TASK_ID, "https://youtube.com/watch?v=test", "mp4")
        finally:
            api_module._updater = old

        assert call_count[0] == 1, "download_video should only be called once — no retry after cancel"
        with api_module._tasks_lock:
            task = api_module._tasks[_TASK_ID]
        assert task["status"] == "cancelled"

    def test_cancelled_before_update_skips_pip_install(self):
        """M1: Task cancelled between download failure and update start — must not run pip install.

        Scenario: download fails with error signal; user cancels task DURING exception handling
        (i.e. cancelled flag is set after the exception is raised but before the update starts).
        Code must check stop_check() before calling update_if_needed.
        """
        _make_task()
        updater = MagicMock(spec=Updater)
        updater.contains_error_signal.return_value = True
        old = _inject_updater(updater)
        try:
            def download_side_effect(*args, **kwargs):
                # Simulate cancellation happening right as the download fails
                # (before exception handler reaches the update call)
                with api_module._tasks_lock:
                    api_module._tasks[_TASK_ID]["cancelled"] = True
                raise Exception("Sign in to confirm")

            with patch("app.api.download_video", side_effect=download_side_effect):
                api_module._run_download(_TASK_ID, "https://youtube.com/watch?v=test", "mp4")
        finally:
            api_module._updater = old

        updater.update_if_needed.assert_not_called()
        with api_module._tasks_lock:
            task = api_module._tasks[_TASK_ID]
        assert task["status"] == "cancelled"


class TestTaskPruning:
    """AI-Review M2 — _tasks memory leak prevention."""

    def setup_method(self, method):
        with api_module._tasks_lock:
            api_module._tasks.clear()

    def test_completed_tasks_pruned_when_exceeding_max(self):
        """Terminal tasks beyond _MAX_TASK_HISTORY are removed (oldest first)."""
        max_history = api_module._MAX_TASK_HISTORY
        # Fill with completed tasks beyond the limit
        with api_module._tasks_lock:
            for i in range(max_history + 5):
                api_module._tasks[f"old-task-{i}"] = {
                    "task_id": f"old-task-{i}",
                    "status": TASK_STATUS_COMPLETED,
                    "cancelled": False,
                }

        # Run a new download that completes — should trigger pruning
        _make_task("new-task")
        updater = MagicMock(spec=Updater)
        updater.contains_error_signal.return_value = False
        old = _inject_updater(updater)
        try:
            with patch("app.api.download_video", return_value={"title": "Test"}):
                api_module._run_download("new-task", "https://youtube.com/watch?v=test", "mp4")
        finally:
            api_module._updater = old

        with api_module._tasks_lock:
            count = len(api_module._tasks)
        assert count <= max_history, (
            f"_tasks should be pruned to max {max_history}, but has {count}"
        )

    def test_active_tasks_not_pruned(self):
        """Downloading/updating tasks must never be removed by pruning."""
        max_history = api_module._MAX_TASK_HISTORY
        # Fill with completed tasks at the limit
        with api_module._tasks_lock:
            for i in range(max_history):
                api_module._tasks[f"old-task-{i}"] = {
                    "task_id": f"old-task-{i}",
                    "status": TASK_STATUS_COMPLETED,
                    "cancelled": False,
                }
            # Add an active task
            api_module._tasks["active-task"] = {
                "task_id": "active-task",
                "status": TASK_STATUS_DOWNLOADING,
                "cancelled": False,
            }

        # Run another task that completes — pruning fires
        _make_task("new-task")
        updater = MagicMock(spec=Updater)
        updater.contains_error_signal.return_value = False
        old = _inject_updater(updater)
        try:
            with patch("app.api.download_video", return_value={"title": "Test"}):
                api_module._run_download("new-task", "https://youtube.com/watch?v=test", "mp4")
        finally:
            api_module._updater = old

        with api_module._tasks_lock:
            assert "active-task" in api_module._tasks, "Active task must not be pruned"


def test_health_200(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"


def test_download_video_task_id(client):
    with patch("app.api._run_download"):
        response = client.post(
            "/download_video",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )
    assert response.status_code == 202
    data = response.get_json()
    assert "task_id" in data
    assert isinstance(data["task_id"], str)
    assert len(data["task_id"]) > 0
    assert data["status"] == "processing"


def test_download_video_invalid_url_400(client):
    response = client.post("/download_video", json={"url": "not-a-valid-url"})
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data


def test_download_video_playlist_url_400(client):
    response = client.post(
        "/download_video",
        json={"url": "https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"},
    )
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data
    assert "playlist" in data["error"].lower()


def test_tasks_list(client):
    response = client.get("/tasks")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)


def test_task_detail_not_found(client):
    response = client.get("/tasks/nonexistent-id")
    assert response.status_code == 404
    data = response.get_json()
    assert "error" in data


def test_task_detail_found(client):
    with patch("app.api._run_download"):
        post_resp = client.post(
            "/download_video",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )
    task_id = post_resp.get_json()["task_id"]
    response = client.get(f"/tasks/{task_id}")
    assert response.status_code == 200
    data = response.get_json()
    assert "status" in data


def test_files_list(client):
    response = client.get("/files")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)


def test_download_video_mp3_format(client):
    with patch("app.api._run_download") as mock_run:
        response = client.post(
            "/download_video",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "format": "mp3"},
        )
    assert response.status_code == 202
    data = response.get_json()
    assert "task_id" in data
    task_id = data["task_id"]
    # The task should store the format
    import app.api as api_module
    with api_module._tasks_lock:
        task = api_module._tasks.get(task_id)
    assert task is not None
    assert task["format"] == "mp3"


def test_download_video_mp4_format(client):
    with patch("app.api._run_download") as mock_run:
        response = client.post(
            "/download_video",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "format": "mp4"},
        )
    assert response.status_code == 202
    data = response.get_json()
    task_id = data["task_id"]
    import app.api as api_module
    with api_module._tasks_lock:
        task = api_module._tasks.get(task_id)
    assert task is not None
    assert task["format"] == "mp4"


def test_download_video_invalid_format_defaults_to_mp4(client):
    with patch("app.api._run_download"):
        response = client.post(
            "/download_video",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "format": "avi"},
        )
    assert response.status_code == 202
    data = response.get_json()
    task_id = data["task_id"]
    import app.api as api_module
    with api_module._tasks_lock:
        task = api_module._tasks.get(task_id)
    assert task["format"] == "mp4"


def test_task_cancel(client):
    with patch("app.api._run_download"):
        post_resp = client.post(
            "/download_video",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )
    task_id = post_resp.get_json()["task_id"]
    response = client.delete(f"/tasks/{task_id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data.get("status") == "cancelling"


# ---------------------------------------------------------------------------
# Story 2.1: /health endpoint with yt-dlp version data
# ---------------------------------------------------------------------------

def test_health_includes_updater_fields(client):
    """GET /health with live updater returns yt_dlp_version, yt_dlp_latest, last_update, update_status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"
    assert "yt_dlp_version" in data
    assert "yt_dlp_latest" in data
    assert "last_update" in data
    assert "update_status" in data


def test_health_update_status_ok_by_default(client):
    """GET /health returns update_status 'ok' on fresh state."""
    response = client.get("/health")
    data = response.get_json()
    assert data["update_status"] == "ok"


def test_health_no_network_calls(client):
    """GET /health must not make external network calls — verify via mock."""
    with patch("app.updater.subprocess.run") as mock_sub:
        response = client.get("/health")
    assert response.status_code == 200
    mock_sub.assert_not_called()


def test_health_updating_status_reflected(client):
    """GET /health returns update_status 'updating' when update is in progress (AC4)."""
    mock_updater = MagicMock(spec=Updater)
    mock_updater.get_update_status.return_value = {
        "current_version": "2026.01.01",
        "latest_version": "2026.03.07",
        "last_update": None,
        "update_status": "updating",
        "service_degraded": False,
    }
    old = api_module._updater
    api_module._updater = mock_updater
    try:
        response = client.get("/health")
    finally:
        api_module._updater = old
    assert response.status_code == 200
    data = response.get_json()
    assert data["update_status"] == "updating"


def test_health_updater_none_returns_healthy(monkeypatch, client):
    """If _updater is None, /health returns {status: healthy} without crashing."""
    monkeypatch.setattr(api_module, "_updater", None)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"
    assert "yt_dlp_version" not in data


# ---------------------------------------------------------------------------
# Prep sprint: has_active_tasks()
# ---------------------------------------------------------------------------

class TestHasActiveTasks:
    def setup_method(self, method):
        with api_module._tasks_lock:
            api_module._tasks.clear()

    def test_no_tasks_returns_false(self):
        assert api_module.has_active_tasks() is False

    def test_downloading_task_returns_true(self):
        with api_module._tasks_lock:
            api_module._tasks["t1"] = {"status": TASK_STATUS_DOWNLOADING, "cancelled": False}
        assert api_module.has_active_tasks() is True

    def test_updating_task_returns_true(self):
        with api_module._tasks_lock:
            api_module._tasks["t1"] = {"status": TASK_STATUS_UPDATING, "cancelled": False}
        assert api_module.has_active_tasks() is True

    def test_completed_task_returns_false(self):
        with api_module._tasks_lock:
            api_module._tasks["t1"] = {"status": TASK_STATUS_COMPLETED, "cancelled": False}
        assert api_module.has_active_tasks() is False

    def test_failed_task_returns_false(self):
        with api_module._tasks_lock:
            api_module._tasks["t1"] = {"status": TASK_STATUS_FAILED, "cancelled": False}
        assert api_module.has_active_tasks() is False

    def test_mixed_tasks_returns_true_if_any_active(self):
        with api_module._tasks_lock:
            api_module._tasks["t1"] = {"status": TASK_STATUS_COMPLETED, "cancelled": False}
            api_module._tasks["t2"] = {"status": TASK_STATUS_DOWNLOADING, "cancelled": False}
        assert api_module.has_active_tasks() is True
