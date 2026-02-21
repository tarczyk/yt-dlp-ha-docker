# yt-dlp API – Home Assistant Add-on

**Icon:** The add-on uses a custom icon (play + download arrow). To regenerate `logo.png` / `icon.png` from `icon.svg`, run `./build-icon.sh` in this directory (requires ImageMagick, rsvg-convert, or macOS).

This add-on runs the **yt-dlp REST API** inside Home Assistant OS, enabling you to download YouTube videos directly to your HA media library using the [ha-yt-dlp Lovelace card](../frontend/ha-card/).

## Installation

1. In Home Assistant, go to **Settings → Add-ons → Add-on store → ⋮ (overflow menu) → Repositories**.
2. Add the repository URL: `https://github.com/tarczyk/ha-yt-dlp`
3. Refresh the page. The **yt-dlp API** add-on will appear in the store.
4. Click **Install**, then **Start**.

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `port` | `5000` | TCP port the Flask API listens on inside the container |
| `media_subdir` | `youtube_downloads` | Subfolder under HA `/media` where downloads are saved (e.g. `youtube_downloads`, `videos`, `downloads`) |

Example:

```yaml
port: 5000
media_subdir: youtube_downloads
```

To save videos to a different folder in **Media Browser** (e.g. **My media → videos**), set `media_subdir: videos`. Only letters, numbers, underscores, hyphens and dots are allowed.

## Media storage

Downloaded files are written to `/media/<media_subdir>` inside the container, which is mapped to the HA `/media` share. They appear in **Media Browser → My media → &lt;media_subdir&gt;**.

## Using with the Lovelace card

Install the **yt-dlp Downloader Card** via HACS (add `https://github.com/tarczyk/ha-yt-dlp` as a custom Lovelace repository). Then add the card to your dashboard:

```yaml
type: custom:yt-dlp-card
api_url: http://homeassistant.local:5000
title: YouTube Downloader
max_tasks: 10
```

## API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Returns `{"status": "healthy"}` |
| `POST` | `/download_video` | Queue a download: `{"url": "https://..."}` |
| `GET` | `/tasks` | List all download tasks |
| `GET` | `/tasks/<id>` | Get status of a specific task |
| `GET` | `/files` | List downloaded files |
