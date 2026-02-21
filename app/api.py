import threading
import uuid
from urllib.parse import urlparse

from flask import Blueprint, jsonify, request

from .yt_dlp_manager import download_video

api = Blueprint("api", __name__)

_tasks: dict[str, dict] = {}
_tasks_lock = threading.Lock()


def _run_download(task_id: str, url: str) -> None:
    with _tasks_lock:
        _tasks[task_id]["status"] = "running"
    try:
        info = download_video(url)
        with _tasks_lock:
            _tasks[task_id]["status"] = "done"
            _tasks[task_id]["title"] = info.get("title", "")
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


@api.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@api.route("/download", methods=["POST"])
def download():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "")
    if not _is_valid_url(url):
        return jsonify({"error": "invalid url"}), 400
    task_id = str(uuid.uuid4())
    with _tasks_lock:
        _tasks[task_id] = {"status": "queued", "url": url}
    thread = threading.Thread(target=_run_download, args=(task_id, url), daemon=True)
    thread.start()
    return jsonify({"task_id": task_id}), 202


@api.route("/tasks", methods=["GET"])
def tasks():
    with _tasks_lock:
        snapshot = list(_tasks.values())
    return jsonify(snapshot), 200
