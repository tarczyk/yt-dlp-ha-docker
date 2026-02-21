"""Integration test: builds the Docker image, starts the container, and verifies
that a real YouTube video can be downloaded via POST /download_video.

Requirements:
  - Docker daemon must be running on the host.
  - The host must have outbound internet access to reach YouTube.

Run with:
    pytest -m integration -v

Skipped automatically during the regular unit-test run (``pytest`` without flags).
"""

import os
import subprocess
import time

import pytest
import requests

_IMAGE_TAG = "yt-dlp-ha-docker-integ"
_CONTAINER_NAME = "yt-dlp-ha-integ"
_HOST_PORT = 15000
_BASE_URL = f"http://127.0.0.1:{_HOST_PORT}"

# "Me at the zoo" – first YouTube video, ~19 seconds.
# The `tv` player client (configured in yt_dlp_manager.py) + the `yt-dlp-ejs`
# Node.js EJS solver bypass YouTube's "Sign in to confirm you're not a bot"
# detection that affects headless/CI environments.
_SAMPLE_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _wait_for_healthy(base_url: str, timeout: int = 60) -> None:
    """Poll /health until the container reports healthy or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = requests.get(f"{base_url}/health", timeout=5)
            if resp.status_code == 200 and resp.json().get("status") == "healthy":
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    raise RuntimeError(f"Container did not become healthy within {timeout}s")


def _poll_task(base_url: str, task_id: str, timeout: int = 180) -> str:
    """Poll GET /tasks/<task_id> until status is terminal or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = requests.get(f"{base_url}/tasks/{task_id}", timeout=10)
            status = resp.json().get("status", "")
            if status in ("completed", "error"):
                return status
        except requests.RequestException:
            pass
        time.sleep(5)
    return "timeout"


@pytest.fixture(scope="module")
def running_container(tmp_path_factory):
    """Build the image, start the container, yield the media dir, then clean up."""
    media_dir = tmp_path_factory.mktemp("media")
    # Make writable by the container's non-root appuser.
    media_dir.chmod(0o777)

    # Build the image.
    subprocess.run(
        ["docker", "build", "-t", _IMAGE_TAG, "."],
        cwd=_PROJECT_ROOT,
        check=True,
        timeout=300,
    )

    # Remove any stale container left by a previous interrupted run.
    subprocess.run(["docker", "rm", "-f", _CONTAINER_NAME], capture_output=True)

    # Start the container.  /tmp as tmpfs mirrors the production compose config
    # without restricting the entire FS to read-only so yt-dlp can write cache.
    subprocess.run(
        [
            "docker", "run", "-d",
            "--name", _CONTAINER_NAME,
            "-p", f"127.0.0.1:{_HOST_PORT}:5000",
            "-v", f"{media_dir}:/config/media",
            "--tmpfs", "/tmp",
            _IMAGE_TAG,
        ],
        check=True,
        timeout=30,
    )

    try:
        _wait_for_healthy(_BASE_URL)
        yield media_dir
    finally:
        subprocess.run(["docker", "rm", "-f", _CONTAINER_NAME], capture_output=True)
        subprocess.run(["docker", "rmi", "-f", _IMAGE_TAG], capture_output=True)


@pytest.mark.integration
def test_container_is_healthy(running_container):
    """Container health endpoint must return {"status": "healthy"}."""
    resp = requests.get(f"{_BASE_URL}/health", timeout=10)
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


@pytest.mark.integration
def test_download_video_creates_file(running_container):
    """POSTing a real YouTube URL must result in a downloaded file."""
    media_dir = running_container

    # Submit download request.
    resp = requests.post(
        f"{_BASE_URL}/download_video",
        json={"url": _SAMPLE_URL},
        timeout=10,
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "processing"
    task_id = data["task_id"]

    # Wait for the task to finish (up to 3 minutes for download + processing).
    status = _poll_task(_BASE_URL, task_id, timeout=180)

    # Fetch full task detail for a useful failure message.
    detail = requests.get(f"{_BASE_URL}/tasks/{task_id}", timeout=10).json()
    assert status == "completed", (
        f"Download task ended with status: {status!r}. "
        f"Task detail: {detail}"
    )

    # Verify a file actually appeared in the mounted media directory.
    downloaded = [f for f in media_dir.iterdir() if f.is_file()]
    assert len(downloaded) > 0, "No files found in /config/media after download"
