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


def test_download_video_mp3_uses_audio_format():
    """Verify that format_type='mp3' sets bestaudio format and FFmpegExtractAudio postprocessor."""
    from app.yt_dlp_manager import download_video

    captured_opts = {}

    def fake_ydl_class(opts):
        captured_opts.update(opts)
        instance = MagicMock()
        instance.__enter__ = MagicMock(return_value=instance)
        instance.__exit__ = MagicMock(return_value=False)
        instance.extract_info.return_value = {"title": "Test"}
        return instance

    with patch("yt_dlp.YoutubeDL", side_effect=fake_ydl_class):
        download_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ", format_type="mp3")

    assert captured_opts["format"] == "bestaudio/best"
    assert any(p["key"] == "FFmpegExtractAudio" for p in captured_opts.get("postprocessors", []))


def test_download_video_mp4_uses_video_format():
    """Verify that format_type='mp4' sets the bestvideo+bestaudio format string."""
    from app.yt_dlp_manager import download_video

    captured_opts = {}

    def fake_ydl_class(opts):
        captured_opts.update(opts)
        instance = MagicMock()
        instance.__enter__ = MagicMock(return_value=instance)
        instance.__exit__ = MagicMock(return_value=False)
        instance.extract_info.return_value = {"title": "Test"}
        return instance

    with patch("yt_dlp.YoutubeDL", side_effect=fake_ydl_class):
        download_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ", format_type="mp4")

    assert "mp4" in captured_opts["format"]
    assert captured_opts.get("merge_output_format") == "mp4"


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
