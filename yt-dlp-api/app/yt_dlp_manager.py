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
        # Explicit JS runtime for EJS (n-sig challenge). Image has Node and Deno; Node is reliable in Alpine.
        "js_runtimes": "node",
        # Prefer web clients to avoid YouTube's DRM-on-tv experiment (issue #12563).
        # When tv client is used first, some accounts get only DRM formats → "This video is DRM protected".
        # default + web_safari + web_embedded avoid tv; EJS (yt-dlp-ejs + Node) handles n-sig if needed.
        "extractor_args": {
            "youtube": {
                "player_client": ["default", "web_safari", "web_embedded"],
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
