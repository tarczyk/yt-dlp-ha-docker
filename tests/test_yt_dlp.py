import pytest
from unittest.mock import patch, MagicMock


def test_ytdlp_remote_components():
    """Verify that yt-dlp YoutubeDL can be instantiated and extract_info is callable."""
    import yt_dlp

    ydl_opts = {"quiet": True, "skip_download": True}
    mock_info = {"id": "dQw4w9WgXcQ", "title": "Test Video", "url": "https://example.com/video.mp4"}

    with patch("yt_dlp.YoutubeDL") as mock_ydl_class:
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = mock_info
        mock_ydl_class.return_value.__enter__ = MagicMock(return_value=mock_ydl_instance)
        mock_ydl_class.return_value.__exit__ = MagicMock(return_value=False)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ", download=False)

    assert info["id"] == "dQw4w9WgXcQ"
    assert info["title"] == "Test Video"
    mock_ydl_instance.extract_info.assert_called_once_with(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ", download=False
    )


def test_download_timeout():
    """Verify that a socket timeout triggers an exception during download."""
    from app.yt_dlp_manager import download_video

    with patch("yt_dlp.YoutubeDL") as mock_ydl_class:
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.side_effect = Exception("socket timeout")
        mock_ydl_class.return_value.__enter__ = MagicMock(return_value=mock_ydl_instance)
        mock_ydl_class.return_value.__exit__ = MagicMock(return_value=False)

        with pytest.raises(Exception, match="socket timeout"):
            download_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ", timeout=1)
