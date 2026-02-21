import json
import subprocess
from unittest.mock import patch, MagicMock
import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "ok"


def test_download_missing_url(client):
    response = client.post("/download", json={})
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data


def test_download_no_body(client):
    response = client.post("/download", content_type="application/json", data="")
    assert response.status_code == 400


def test_download_success(client, tmp_path):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Download complete"
    mock_result.stderr = ""

    with patch("app.DOWNLOAD_DIR", str(tmp_path)), \
         patch("subprocess.run", return_value=mock_result):
        response = client.post("/download", json={"url": "https://example.com/video"})

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "success"


def test_download_failure(client, tmp_path):
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "Error downloading"

    with patch("app.DOWNLOAD_DIR", str(tmp_path)), \
         patch("subprocess.run", return_value=mock_result):
        response = client.post("/download", json={"url": "https://example.com/video"})

    assert response.status_code == 500
    data = json.loads(response.data)
    assert "error" in data


def test_download_timeout(client, tmp_path):
    with patch("app.DOWNLOAD_DIR", str(tmp_path)), \
         patch("subprocess.run", side_effect=subprocess.TimeoutExpired("yt-dlp", 300)):
        response = client.post("/download", json={"url": "https://example.com/video"})

    assert response.status_code == 504
    data = json.loads(response.data)
    assert "error" in data


def test_download_invalid_url(client):
    response = client.post("/download", json={"url": "not-a-url"})
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data


def test_download_ytdlp_not_found(client, tmp_path):
    with patch("app.DOWNLOAD_DIR", str(tmp_path)), \
         patch("subprocess.run", side_effect=FileNotFoundError):
        response = client.post("/download", json={"url": "https://example.com/video"})

    assert response.status_code == 500
    data = json.loads(response.data)
    assert "error" in data
