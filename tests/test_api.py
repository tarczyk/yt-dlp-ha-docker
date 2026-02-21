import pytest
from unittest.mock import patch, MagicMock


def test_health_200(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"


def test_download_video_task_id(client):
    with patch("app.api._run_download"):
        response = client.post(
            "/download",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )
    assert response.status_code == 202
    data = response.get_json()
    assert "task_id" in data
    assert isinstance(data["task_id"], str)
    assert len(data["task_id"]) > 0


def test_download_video_invalid_url_400(client):
    response = client.post("/download", json={"url": "not-a-valid-url"})
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data


def test_tasks_list(client):
    response = client.get("/tasks")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
