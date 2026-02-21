import pytest
from unittest.mock import patch, MagicMock


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
