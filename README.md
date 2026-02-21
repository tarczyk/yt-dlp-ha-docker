# yt-dlp-ha-docker

🐳 Docker Compose yt-dlp API for Home Assistant with EJS (Node.js) support.  
Downloads to `/media/youtube_downloads` • Compatible with the `youtube_downloader` integration.

[![Docker Pulls](https://img.shields.io/docker/pulls/tarczyk/yt-dlp-ha-docker?logo=docker&label=Docker%20Pulls)](https://hub.docker.com/r/tarczyk/yt-dlp-ha-docker)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2023.1%2B-41BDF5?logo=home-assistant)](https://www.home-assistant.io/)
[![Multi-Arch](https://img.shields.io/badge/arch-amd64%20%7C%20arm64-blue?logo=linux)](https://hub.docker.com/r/tarczyk/yt-dlp-ha-docker/tags)
[![CI](https://img.shields.io/github/actions/workflow/status/tarczyk/yt-dlp-ha-docker/ci.yml?label=Tests&logo=github)](https://github.com/tarczyk/yt-dlp-ha-docker/actions)
[![Security Scan](https://img.shields.io/github/actions/workflow/status/tarczyk/yt-dlp-ha-docker/security.yml?label=Security%20Scan&logo=shield)](https://github.com/tarczyk/yt-dlp-ha-docker/actions)
[![License](https://img.shields.io/github/license/tarczyk/yt-dlp-ha-docker)](LICENSE)

## Features

- **Flask REST API** – `POST /download_video` and `GET /health`
- **yt-dlp** with Node.js as the JavaScript runtime (EJS) for YouTube 2025+ compatibility
- **ffmpeg** for post-processing (merging video/audio streams)
- **Volume** mounted at `/media/youtube_downloads` – visible in HA Media Browser
- **Multi-arch** image: `linux/amd64` and `linux/arm64` (aarch64 / Raspberry Pi)
- **Healthcheck** + `restart: unless-stopped` for reliable operation

## Quick Start

One command to get up and running:

```bash
git clone https://github.com/tarczyk/yt-dlp-ha-docker.git
cd yt-dlp-ha-docker
docker compose up -d --build
```

Check the logs to confirm the service is ready:

```bash
docker compose logs -f
```

Example output:

```
yt-dlp-api  |  * Running on http://0.0.0.0:8080
yt-dlp-api  |  * Serving Flask app 'app'
yt-dlp-api  |  * Debug mode: off
```

### Configuration

Adjust defaults by editing `.env` in the project root:

| Variable | Default | Description |
|---|---|---|
| `API_PORT` | `8080` | Host port for the Flask API |
| `DOWNLOAD_DIR` | `/media/youtube_downloads` | Host path where videos are saved |
| `YT_DLP_EXTRA_ARGS` | *(empty)* | Extra flags passed to `yt-dlp` |

### Test the API

```bash
# Health check
curl http://localhost:8080/health

# Download a video
curl -X POST http://localhost:8080/download_video \
     -H "Content-Type: application/json" \
     -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

## API Docs

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Returns `{"status": "ok"}` with HTTP 200 when the service is healthy |
| `POST` | `/download_video` | Downloads a video URL to `DOWNLOAD_DIR` |

### `GET /health`

```json
{"status": "ok"}
```

### `POST /download_video`

**Request**

```json
{"url": "https://www.youtube.com/watch?v=..."}
```

**Responses**

| Code | Body | Meaning |
|------|------|---------|
| `200` | `{"status": "downloaded", "output": "..."}` | Download succeeded |
| `400` | `{"error": "..."}` | Missing or invalid request body |
| `500` | `{"error": "..."}` | yt-dlp returned a non-zero exit code |
| `504` | `{"error": "..."}` | Download exceeded the configured timeout |

## Home Assistant Integration

### 1. Expose the download directory as a media source

Add the container's download volume to `configuration.yaml` so videos appear in the **Media Browser**:

```yaml
# configuration.yaml
homeassistant:
  media_dirs:
    youtube: /media/youtube_downloads
```

Restart Home Assistant after adding the entry. The `youtube` source will then be browsable under **Media → My Media**.

### 2. Trigger downloads from automations

```yaml
# configuration.yaml
rest_command:
  download_youtube_video:
    url: "http://<your-docker-host>:8080/download_video"
    method: POST
    headers:
      Content-Type: application/json
    payload: '{"url": "{{ url }}"}'
```

Use the REST command in an automation or script:

```yaml
service: rest_command.download_youtube_video
data:
  url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

### Screenshots

**Docker logs** (`docker compose logs -f`):

```
yt-dlp-api  | [download] Destination: /media/youtube_downloads/Rick Astley - Never Gonna Give You Up.mp4
yt-dlp-api  | [download] 100% of   6.57MiB in 00:03
```

**HA Media Browser** – after adding `media_dirs`, downloaded files appear under *My Media → youtube*:

> 📁 Media Browser → My Media → youtube → `Rick Astley - Never Gonna Give You Up.mp4`

## Development

### Hot reload (watch mode)

Mount the source code into the container and enable Flask's debug mode for instant reloads on file changes:

```yaml
# docker-compose.override.yml
services:
  yt-dlp-api:
    environment:
      FLASK_DEBUG: "1"
    volumes:
      - .:/app               # mount local source
```

Then start with:

```bash
docker compose -f docker-compose.yml -f docker-compose.override.yml up --build
```

Flask will automatically reload whenever you save a file under `./app`.

### Multi-Arch Build

To push a multi-architecture image to a registry:

```bash
docker buildx create --use
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t youruser/yt-dlp-ha-api:latest \
  --push .
```

## Security

### Container hardening

The image applies several hardening measures out of the box:

| Measure | Detail |
|---------|--------|
| **Non-root user** | The Flask process runs as an unprivileged user inside the container |
| **Read-only filesystem** | Only `/media/youtube_downloads` (the download volume) is writable |
| **No new privileges** | `security_opt: no-new-privileges:true` prevents privilege escalation |
| **Minimal base image** | Built on `python:3.12-slim` to reduce the attack surface |
| **Pinned dependencies** | `requirements.txt` pins exact package versions |

### Recommended `docker-compose.yml` security options

```yaml
services:
  yt-dlp-api:
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp
    volumes:
      - /media/youtube_downloads:/media/youtube_downloads
```

### Vulnerability scanning

The image is scanned for known CVEs on every build using [Trivy](https://github.com/aquasecurity/trivy). Scan results are published as GitHub Actions artifacts. To run a scan locally:

```bash
trivy image tarczyk/yt-dlp-ha-docker:latest
```

## License

MIT
🐳 Docker Compose yt-dlp API for Home Assistant with Node.js support. Downloads to `/media/youtube_downloads`. Compatible with the youtube_downloader integration.

## Quick Start

```bash
docker pull tarczyk/yt-dlp-ha-docker
```

Or use Docker Compose:

```bash
docker compose up -d
```
