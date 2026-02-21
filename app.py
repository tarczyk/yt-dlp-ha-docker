import os
import subprocess
from urllib.parse import urlparse
from flask import Flask, request, jsonify

app = Flask(__name__)

DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "/media/youtube_downloads")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/download", methods=["POST"])
def download():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "url is required"}), 400
    if not _URL_RE.match(url):
        return jsonify({"error": "invalid url"}), 400

    result = subprocess.run(
        ["yt-dlp", "--no-playlist", "-o", f"{DOWNLOAD_DIR}/%(title)s.%(ext)s", url],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        logger.error("yt-dlp error: %s", result.stderr)
        return jsonify({"error": "download failed"}), 500

    return jsonify({"status": "ok", "output": result.stdout}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
