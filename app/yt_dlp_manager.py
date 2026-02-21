import yt_dlp


def download_video(url: str, output_dir: str = "/config/media", timeout: int = 1800) -> dict:
    """Download a video using yt-dlp and return info dict."""
    ydl_opts = {
        "outtmpl": f"{output_dir}/%(title)s.%(ext)s",
        "quiet": True,
        "socket_timeout": timeout,
        # Keep yt-dlp's cache in /tmp so it works even when the container runs
        # as a non-root user without a writable home directory.
        "cachedir": "/tmp/yt-dlp",
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
    return info or {}


def extract_info(url: str) -> dict:
    """Extract video info without downloading."""
    ydl_opts = {"quiet": True, "skip_download": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return info or {}
