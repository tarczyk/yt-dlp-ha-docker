import os
import threading
import uuid
from urllib.parse import urlparse

from flask import Blueprint, jsonify, request

from .updater import Updater
from .yt_dlp_manager import (
    DownloadCancelledError,
    TASK_STATUS_DOWNLOADING,
    TASK_STATUS_UPDATING,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    check_ytdlp_version,
    download_video,
)

api = Blueprint("api", __name__)

_tasks: dict[str, dict] = {}
_tasks_lock = threading.Lock()

_MAX_TASK_HISTORY = 100  # Max terminal-state tasks kept in memory; oldest pruned on completion


def _prune_completed_tasks() -> None:
    """Remove oldest terminal-state tasks when count exceeds _MAX_TASK_HISTORY.

    Must be called with _tasks_lock held.
    Only removes tasks in terminal states (completed/failed/cancelled) — never active tasks.
    Preserves insertion order so oldest completed tasks are removed first.
    """
    _TERMINAL = (TASK_STATUS_COMPLETED, TASK_STATUS_FAILED, "cancelled")
    terminal_ids = [tid for tid, t in _tasks.items() if t.get("status") in _TERMINAL]
    excess = len(terminal_ids) - _MAX_TASK_HISTORY
    if excess > 0:
        for tid in terminal_ids[:excess]:
            del _tasks[tid]

_updater: Updater | None = None


def init_updater(updater: Updater) -> None:
    """Called by create_app() to inject the shared Updater instance."""
    global _updater
    _updater = updater


def has_active_tasks() -> bool:
    """Return True if any task is currently downloading or updating."""
    with _tasks_lock:
        return any(
            t.get("status") in (TASK_STATUS_DOWNLOADING, TASK_STATUS_UPDATING)
            for t in _tasks.values()
        )

DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "/config/media")
MEDIA_SUBDIR = os.environ.get("MEDIA_SUBDIR", "youtube_downloads")


def _run_download(task_id: str, url: str, format_type: str = "mp4") -> None:
    def stop_check() -> bool:
        with _tasks_lock:
            return _tasks.get(task_id, {}).get("cancelled") is True

    try:
        with _tasks_lock:
            _tasks[task_id]["status"] = TASK_STATUS_DOWNLOADING
        try:
            formats = ["mp4", "mp3"] if format_type == "both" else [format_type]
            info = {}
            for fmt in formats:
                if stop_check():
                    raise DownloadCancelledError("Cancelled by user")
                info = download_video(url, output_dir=DOWNLOAD_DIR, stop_check=stop_check, format_type=fmt)
            with _tasks_lock:
                _tasks[task_id]["status"] = TASK_STATUS_COMPLETED
                _tasks[task_id]["title"] = info.get("title", "")
        except DownloadCancelledError:
            with _tasks_lock:
                _tasks[task_id]["status"] = "cancelled"
                _tasks[task_id]["error"] = "Cancelled by user"
        except Exception as exc:
            error_str = str(exc)
            if _updater is not None and _updater.contains_error_signal(error_str):
                if stop_check():
                    # Task was cancelled between download failure and update start — skip pip install
                    with _tasks_lock:
                        _tasks[task_id]["status"] = "cancelled"
                        _tasks[task_id]["error"] = "Cancelled by user"
                else:
                    _trigger_adhoc_update_and_retry(task_id, url, format_type, error_str, stop_check)
            else:
                with _tasks_lock:
                    _tasks[task_id]["status"] = TASK_STATUS_FAILED
                    _tasks[task_id]["error"] = error_str
    finally:
        with _tasks_lock:
            _prune_completed_tasks()


def _trigger_adhoc_update_and_retry(
    task_id: str, url: str, format_type: str, original_error: str, stop_check
) -> None:
    """Called when download fails with a recognized error signal."""
    with _tasks_lock:
        _tasks[task_id]["status"] = TASK_STATUS_UPDATING

    result = _updater.update_if_needed("ad-hoc")  # type: ignore[union-attr]

    if not result.success:
        with _tasks_lock:
            _tasks[task_id]["status"] = TASK_STATUS_FAILED
            _tasks[task_id]["error"] = original_error
        return

    # Check cancellation before retry — user may have cancelled during pip install
    if stop_check():
        with _tasks_lock:
            _tasks[task_id]["status"] = "cancelled"
            _tasks[task_id]["error"] = "Cancelled by user"
        return

    # Update succeeded — retry the download
    try:
        formats = ["mp4", "mp3"] if format_type == "both" else [format_type]
        info = {}
        for fmt in formats:
            info = download_video(url, output_dir=DOWNLOAD_DIR, format_type=fmt, stop_check=stop_check)
        with _tasks_lock:
            _tasks[task_id]["status"] = TASK_STATUS_COMPLETED
            _tasks[task_id]["title"] = info.get("title", "")
    except DownloadCancelledError:
        with _tasks_lock:
            _tasks[task_id]["status"] = "cancelled"
            _tasks[task_id]["error"] = "Cancelled by user"
    except Exception as retry_exc:
        with _tasks_lock:
            _tasks[task_id]["status"] = TASK_STATUS_FAILED
            _tasks[task_id]["error"] = str(retry_exc)


def _is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return result.scheme in ("http", "https") and bool(result.netloc)
    except Exception:
        return False


def _is_playlist_url(url: str) -> bool:
    """True if URL is a YouTube playlist page (would download many videos)."""
    try:
        u = urlparse(url)
        if "youtube.com" not in u.netloc and "youtu.be" not in u.netloc:
            return False
        q = u.query or ""
        if "/playlist" in u.path:
            return True
        if "list=" in q and "v=" not in q:
            return True
        return False
    except Exception:
        return False


@api.route("/health", methods=["GET"])
def health():
    response: dict = {"status": "healthy"}
    if _updater is not None:
        status = _updater.get_update_status()
        response["yt_dlp_version"] = status["current_version"]
        response["yt_dlp_latest"] = status["latest_version"]
        response["last_update"] = status["last_update"]
        response["update_status"] = status["update_status"]
        response["service_degraded"] = status["service_degraded"]
    return jsonify(response), 200


@api.route("/config", methods=["GET"])
def config():
    """Return public config (e.g. media path for Lovelace card)."""
    return jsonify({"media_subdir": MEDIA_SUBDIR}), 200


@api.route("/download_video", methods=["POST"])
def download_video_endpoint():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "")
    format_type = data.get("format", "mp4")
    if format_type not in ("mp4", "mp3"):
        format_type = "mp4"
    if not _is_valid_url(url):
        return jsonify({"error": "invalid url"}), 400
    if _is_playlist_url(url):
        return jsonify({
            "error": "Playlist URLs are not allowed. Use a single video URL (e.g. youtube.com/watch?v=...).",
        }), 400
    task_id = str(uuid.uuid4())
    with _tasks_lock:
        _tasks[task_id] = {"task_id": task_id, "status": "queued", "url": url, "cancelled": False, "format": format_type}
    thread = threading.Thread(target=_run_download, args=(task_id, url, format_type), daemon=True)
    thread.start()
    response: dict = {"status": "processing", "task_id": task_id}
    version_info = check_ytdlp_version()
    if version_info.get("is_outdated") and version_info.get("warning"):
        response["yt_dlp_warning"] = version_info["warning"]
    return jsonify(response), 202


@api.route("/tasks", methods=["GET"])
def tasks():
    with _tasks_lock:
        snapshot = [{**t, "task_id": tid} for tid, t in _tasks.items()]
    return jsonify(snapshot), 200


@api.route("/tasks/<task_id>", methods=["GET"])
def task_detail(task_id: str):
    with _tasks_lock:
        task = _tasks.get(task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task), 200


@api.route("/tasks/<task_id>", methods=["DELETE"])
def task_cancel(task_id: str):
    """Request cancellation of a queued or running task. Idempotent."""
    with _tasks_lock:
        task = _tasks.get(task_id)
        if task is None:
            return jsonify({"error": "task not found"}), 404
        if task["status"] not in ("queued", TASK_STATUS_DOWNLOADING, TASK_STATUS_UPDATING):
            return jsonify({"status": task["status"], "message": "Task already finished."}), 200
        task["cancelled"] = True
    return jsonify({"status": "cancelling", "message": "Cancellation requested."}), 200


@api.route("/files", methods=["GET"])
def files():
    try:
        entries = os.listdir(DOWNLOAD_DIR)
        file_list = [f for f in entries if os.path.isfile(os.path.join(DOWNLOAD_DIR, f))]
    except FileNotFoundError:
        file_list = []
    return jsonify(file_list), 200
