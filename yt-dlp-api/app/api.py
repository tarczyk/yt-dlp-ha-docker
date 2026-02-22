import os
import threading
import uuid
from urllib.parse import urlparse

from flask import Blueprint, jsonify, request

from .yt_dlp_manager import DownloadCancelledError, download_video

api = Blueprint("api", __name__)

_tasks: dict[str, dict] = {}
_tasks_lock = threading.Lock()

DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "/config/media")
MEDIA_SUBDIR = os.environ.get("MEDIA_SUBDIR", "youtube_downloads")


def _run_download(task_id: str, url: str, format_type: str = "mp4") -> None:
    def stop_check() -> bool:
        with _tasks_lock:
            return _tasks.get(task_id, {}).get("cancelled") is True

    with _tasks_lock:
        _tasks[task_id]["status"] = "running"
    try:
        info = download_video(url, output_dir=DOWNLOAD_DIR, stop_check=stop_check, format_type=format_type)
        with _tasks_lock:
            _tasks[task_id]["status"] = "completed"
            _tasks[task_id]["title"] = info.get("title", "")
    except DownloadCancelledError:
        with _tasks_lock:
            _tasks[task_id]["status"] = "cancelled"
            _tasks[task_id]["error"] = "Cancelled by user"
    except Exception as exc:
        with _tasks_lock:
            _tasks[task_id]["status"] = "error"
            _tasks[task_id]["error"] = str(exc)


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
    return jsonify({"status": "healthy"}), 200


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
    return jsonify({"status": "processing", "task_id": task_id}), 202


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
    if task["status"] not in ("queued", "running"):
        return jsonify({"status": task["status"], "message": "Task already finished."}), 200
    with _tasks_lock:
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
