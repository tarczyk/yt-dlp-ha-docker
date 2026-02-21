"""Integration test: builds the Docker image, starts the container, and verifies
that the health endpoint returns healthy.

Requirements:
  - Docker daemon must be running on the host.

Run with:
    pytest -m integration -v

Skipped during the regular unit-test run (``pytest`` without -m integration).
"""

import os
import subprocess
import time

import pytest
import requests

_IMAGE_TAG = "ha-yt-dlp-integ"
_CONTAINER_NAME = "yt-dlp-ha-integ"
_HOST_PORT = 15000
_BASE_URL = f"http://127.0.0.1:{_HOST_PORT}"

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


@pytest.fixture(scope="module")
def running_container(tmp_path_factory):
    """Build the image, start the container, yield the media dir, then clean up."""
    media_dir = tmp_path_factory.mktemp("media")
    media_dir.chmod(0o777)

    subprocess.run(
        ["docker", "build", "-t", _IMAGE_TAG, "."],
        cwd=_PROJECT_ROOT,
        check=True,
        timeout=300,
    )

    subprocess.run(["docker", "rm", "-f", _CONTAINER_NAME], capture_output=True)

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
