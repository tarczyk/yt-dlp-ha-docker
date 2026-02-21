import os
import threading
import uuid
from urllib.parse import urlparse

from flask import Blueprint, jsonify, request

from .yt_dlp_manager import download_video

api = Blueprint("api", __name__)

_tasks: dict[str, dict] = {}
_tasks_lock = threading.Lock()

DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "/config/media")


def _run_download(task_id: str, url: str) -> None:
    with _tasks_lock:
        _tasks[task_id]["status"] = "running"
    try:
        info = download_video(url, output_dir=DOWNLOAD_DIR)
        with _tasks_lock:
            _tasks[task_id]["status"] = "completed"
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
    return jsonify({"status": "healthy"}), 200


@api.route("/download_video", methods=["POST"])
def download_video_endpoint():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "")
    if not _is_valid_url(url):
        return jsonify({"error": "invalid url"}), 400
    task_id = str(uuid.uuid4())
    with _tasks_lock:
        _tasks[task_id] = {"status": "queued", "url": url}
    thread = threading.Thread(target=_run_download, args=(task_id, url), daemon=True)
    thread.start()
    return jsonify({"status": "processing", "task_id": task_id}), 202


@api.route("/tasks", methods=["GET"])
def tasks():
    with _tasks_lock:
        snapshot = list(_tasks.values())
    return jsonify(snapshot), 200


@api.route("/tasks/<task_id>", methods=["GET"])
def task_detail(task_id: str):
    with _tasks_lock:
        task = _tasks.get(task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task), 200


@api.route("/files", methods=["GET"])
def files():
    try:
        entries = os.listdir(DOWNLOAD_DIR)
        file_list = [f for f in entries if os.path.isfile(os.path.join(DOWNLOAD_DIR, f))]
    except FileNotFoundError:
        file_list = []
    return jsonify(file_list), 200
