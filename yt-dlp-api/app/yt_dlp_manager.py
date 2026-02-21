import yt_dlp


def download_video(url: str, output_dir: str = "/config/media", timeout: int = 1800) -> dict:
    """Download a video using yt-dlp and return info dict."""
    ydl_opts = {
        "outtmpl": f"{output_dir}/%(title)s.%(ext)s",
        "quiet": True,
        "socket_timeout": timeout,
        # Prefer MP4 for better compatibility (HA Media Browser, TVs, phones).
        # Without this, yt-dlp defaults to "best" and YouTube often serves WebM (VP9).
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        # Keep yt-dlp's cache in /tmp so it works even when the container runs
        # as a non-root user without a writable home directory.
        "cachedir": "/tmp/yt-dlp",
        # Use the TV HTML5 client which does not require a PO (Proof-of-Origin)
        # token, avoiding YouTube's "Sign in to confirm you're not a bot" error
        # in headless/CI environments.  The `yt-dlp-ejs` package (Node.js based
        # EJS solver, installed via requirements.txt) handles the n-sig JS
        # challenge so that the download actually succeeds.
        "extractor_args": {
            "youtube": {
                "player_client": ["tv", "default"],
            },
        },
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
