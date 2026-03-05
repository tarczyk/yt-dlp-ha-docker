"""Tests for yt-dlp version checking (check_ytdlp_version) and API warning."""
import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_github_response(tag_name: str):
    """Return a mock urlopen context manager that emits a GitHub-style payload."""
    payload = json.dumps({"tag_name": tag_name}).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = payload
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _clear_version_cache():
    import app.yt_dlp_manager as m
    m._version_cache = {}


# ---------------------------------------------------------------------------
# check_ytdlp_version unit tests
# ---------------------------------------------------------------------------

class TestCheckYtdlpVersion:
    def setup_method(self):
        _clear_version_cache()

    def test_up_to_date_returns_not_outdated(self):
        from app.yt_dlp_manager import check_ytdlp_version
        local = "2024.12.23"
        with patch("yt_dlp.version.__version__", local), \
             patch("urllib.request.urlopen", return_value=_make_github_response("2024.12.23")):
            result = check_ytdlp_version()

        assert result["local"] == local
        assert result["latest"] == "2024.12.23"
        assert result["is_outdated"] is False
        assert result["warning"] is None

    def test_outdated_sets_is_outdated_and_warning(self):
        from app.yt_dlp_manager import check_ytdlp_version
        with patch("yt_dlp.version.__version__", "2024.01.01"), \
             patch("urllib.request.urlopen", return_value=_make_github_response("2025.03.01")):
            result = check_ytdlp_version()

        assert result["is_outdated"] is True
        assert result["warning"] is not None
        assert "outdated" in result["warning"].lower()
        assert "2024.01.01" in result["warning"]
        assert "2025.03.01" in result["warning"]

    def test_newer_local_returns_not_outdated(self):
        """If local is newer than GitHub (e.g. nightly build), do NOT warn."""
        from app.yt_dlp_manager import check_ytdlp_version
        with patch("yt_dlp.version.__version__", "2025.06.01"), \
             patch("urllib.request.urlopen", return_value=_make_github_response("2025.03.01")):
            result = check_ytdlp_version()

        assert result["is_outdated"] is False
        assert result["warning"] is None

    def test_github_api_failure_is_non_fatal(self):
        """Network errors must not raise – just return is_outdated=False."""
        from app.yt_dlp_manager import check_ytdlp_version
        with patch("yt_dlp.version.__version__", "2024.01.01"), \
             patch("urllib.request.urlopen", side_effect=OSError("network error")):
            result = check_ytdlp_version()

        assert result["is_outdated"] is False
        assert result["warning"] is None
        assert result["latest"] is None

    def test_result_is_cached(self):
        """Second call must not hit GitHub again."""
        from app.yt_dlp_manager import check_ytdlp_version
        with patch("yt_dlp.version.__version__", "2024.01.01"), \
             patch("urllib.request.urlopen", return_value=_make_github_response("2025.03.01")) as mock_open:
            check_ytdlp_version()
            check_ytdlp_version()

        mock_open.assert_called_once()

    def test_github_tag_with_v_prefix_is_stripped(self):
        """Tags like 'v2025.03.01' should be handled the same as '2025.03.01'."""
        from app.yt_dlp_manager import check_ytdlp_version
        with patch("yt_dlp.version.__version__", "2024.01.01"), \
             patch("urllib.request.urlopen", return_value=_make_github_response("v2025.03.01")):
            result = check_ytdlp_version()

        assert result["latest"] == "2025.03.01"
        assert result["is_outdated"] is True

    def test_outdated_logs_warning(self, caplog):
        import logging
        from app.yt_dlp_manager import check_ytdlp_version
        with patch("yt_dlp.version.__version__", "2024.01.01"), \
             patch("urllib.request.urlopen", return_value=_make_github_response("2025.03.01")), \
             caplog.at_level(logging.WARNING, logger="app.yt_dlp_manager"):
            check_ytdlp_version()

        assert any("outdated" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# API endpoint includes yt_dlp_warning when outdated
# ---------------------------------------------------------------------------

class TestDownloadVideoWarning:
    def setup_method(self):
        _clear_version_cache()

    def test_warning_included_when_outdated(self, client):
        with patch("app.api._run_download"), \
             patch("yt_dlp.version.__version__", "2024.01.01"), \
             patch("urllib.request.urlopen", return_value=_make_github_response("2025.03.01")):
            response = client.post(
                "/download_video",
                json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
            )

        assert response.status_code == 202
        data = response.get_json()
        assert "yt_dlp_warning" in data
        assert "outdated" in data["yt_dlp_warning"].lower()

    def test_no_warning_when_up_to_date(self, client):
        with patch("app.api._run_download"), \
             patch("yt_dlp.version.__version__", "2025.03.01"), \
             patch("urllib.request.urlopen", return_value=_make_github_response("2025.03.01")):
            response = client.post(
                "/download_video",
                json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
            )

        assert response.status_code == 202
        data = response.get_json()
        assert "yt_dlp_warning" not in data

    def test_no_warning_when_github_unreachable(self, client):
        with patch("app.api._run_download"), \
             patch("yt_dlp.version.__version__", "2024.01.01"), \
             patch("urllib.request.urlopen", side_effect=OSError("timeout")):
            response = client.post(
                "/download_video",
                json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
            )

        assert response.status_code == 202
        data = response.get_json()
        assert "yt_dlp_warning" not in data
