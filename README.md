# ha-yt-dlp

Home Assistant add-on and Lovelace card that download YouTube videos via **yt-dlp**. Install from the HA add-on store or run as a standalone Docker service.

[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2023.1%2B-41BDF5?logo=home-assistant)](https://www.home-assistant.io/)
[![Multi-Arch](https://img.shields.io/badge/arch-amd64%20%7C%20arm64-blue?logo=linux)](https://hub.docker.com/r/tarczyk/ha-yt-dlp/tags)
[![CI](https://img.shields.io/github/actions/workflow/status/tarczyk/ha-yt-dlp/tests.yml?label=Tests&logo=github)](https://github.com/tarczyk/ha-yt-dlp/actions)
[![Security Scan](https://img.shields.io/github/actions/workflow/status/tarczyk/ha-yt-dlp/security-scan.yml?label=Security%20Scan&logo=shield)](https://github.com/tarczyk/ha-yt-dlp/actions)
[![License](https://img.shields.io/github/license/tarczyk/ha-yt-dlp)](LICENSE)

---

## Contents

- [What’s in this repo](#whats-in-this-repo)
- [Repository structure](#repository-structure)
- [Installation](#installation)
  - [Option A – Home Assistant Add-on](#option-a--home-assistant-add-on-recommended)
  - [Option B – Docker Compose (standalone)](#option-b--docker-compose-standalone)
  - [Option C – Windows (Docker Desktop)](#option-c--windows-docker-desktop)
- [API reference](#api-reference)
- [Chrome extension](#chrome-extension)
- [Lovelace card](#lovelace-card)
- [Home Assistant integration (Docker only)](#home-assistant-integration-docker-only)
- [Development](#development)
- [Security](#security)
- [License](#license)

---

## What’s in this repo

| Deliverable | Description |
|-------------|-------------|
| **Home Assistant Add-on** | Install from HA add-on store; runs the API and writes to HA media. |
| **Docker Compose** | Standalone API (no HA); same image for amd64/arm64. |
| **Lovelace card** | HACS-ready card; URL input, download button, task list, progress. |
| **Chrome extension** | Manifest V3; “Download to HA” from any YouTube page. |

All of them talk to the same **Flask REST API** (`POST /download_video`, `GET /tasks`, etc.). yt-dlp + Node (EJS) + ffmpeg for YouTube 2025+ and merging streams.

---

## Repository structure

| Path | Purpose |
|------|--------|
| `yt-dlp-api/` | **Backend**: `app/`, `config.yaml`, add-on `Dockerfile`, `run.sh`. Single source of truth for the API; add-on and root `Dockerfile` both use it. |
| `frontend/ha-card/` | Lovelace card source; root `ha-yt-dlp.js` is the HACS bundle (see card’s `sync-hacs.sh`). |
| `chrome-ext/` | Chrome extension (Manifest V3). |
| `tests/` | Pytest suite (run from repo root; `pytest.ini` sets `pythonpath = yt-dlp-api`). |

Root `Dockerfile` (standalone image) copies from `yt-dlp-api/`; no duplicate `app/` at root.

---

## Installation

### Option A – Home Assistant Add-on (recommended)

**Requires:** Home Assistant OS or Supervised.

1. **Settings → Add-ons → Add-on store → ⋮ → Repositories** → add: `https://github.com/tarczyk/ha-yt-dlp`
2. Install **yt-dlp API** from the store → **Start**.

The add-on runs the API on port **5000** and saves files under HA’s media share (default: **My media → youtube_downloads**).

**Add-on options**

| Option | Default | Description |
|--------|---------|-------------|
| `port` | `5000` | API listen port. |
| `media_subdir` | `youtube_downloads` | Subfolder under `/media` for downloads (only `a–z`, `0–9`, `_`, `-`, `.`). |

Details: [yt-dlp-api/DOCS.md](yt-dlp-api/DOCS.md).

---

### Option B – Docker Compose (standalone)

```bash
git clone https://github.com/tarczyk/ha-yt-dlp.git
cd ha-yt-dlp
docker compose up -d --build
```

Logs:

```bash
docker compose logs -f
```

**Configuration** – edit `.env` in the project root:

| Variable | Default | Description |
|----------|---------|-------------|
| `API_PORT` | `5000` | Host port for the API. |
| `DOWNLOAD_DIR` | `/config/media` | Host path for downloaded files. |
| `YT_DLP_EXTRA_ARGS` | *(empty)* | Extra flags for yt-dlp. |

**Quick test**

```bash
curl http://localhost:5000/health
curl -X POST http://localhost:5000/download_video \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

---

### Option C – Windows (Docker Desktop)

**Requires:** [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop).

See the full step-by-step guide: [docs/windows-installation.md](docs/windows-installation.md).

Quick start:

1. Install **Docker Desktop** and make sure it is running.
2. Clone the repo (or download the ZIP):
   ```powershell
   git clone https://github.com/tarczyk/ha-yt-dlp.git
   cd ha-yt-dlp
   ```
3. Edit `.env` – set `DOWNLOAD_DIR` to a Windows path (e.g. `C:/Users/YourName/Videos/youtube_downloads`).
4. Update the `volumes` line in `docker-compose.yml` to use `${DOWNLOAD_DIR}:/config/media`.
5. Start the container:
   ```powershell
   docker compose up -d --build
   ```
6. Verify: `curl http://localhost:5000/health` → `{"status": "healthy"}`

---

## API reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check; `{"status": "healthy"}`. |
| `POST` | `/download_video` | Start async download; body `{"url": "..."}`; returns `{"status": "processing", "task_id": "..."}`. **Playlist URLs are rejected** (400). |
| `GET` | `/tasks` | List all tasks (each includes `task_id` for cancel). |
| `GET` | `/tasks/<task_id>` | Status of one task. |
| `DELETE` | `/tasks/<task_id>` | Cancel a queued or running task. |
| `GET` | `/files` | List files in the media directory. |

**`POST /download_video`**

- **Request:** `{"url": "https://www.youtube.com/watch?v=..."}`
- **202** – `{"status": "processing", "task_id": "..."}`
- **400** – `{"error": "..."}` (e.g. missing or invalid URL)

---

## Chrome extension

Manifest V3 extension in [chrome-ext/](chrome-ext/).

**Install from the Chrome Web Store (recommended):**

1. Open the [HA yt-dlp Downloader](https://chrome.google.com/webstore/detail/ha-yt-dlp-downloader) listing and click **Add to Chrome**.
2. In the extension, open **Settings** and set your API URL (e.g. `http://192.168.1.100:5000`).
3. On a YouTube video page, open the extension → **Download to HA**.

**Manual install (Developer Mode):** open `chrome://extensions/` → **Developer mode** → **Load unpacked** → select `chrome-ext/`.

Full doc: [chrome-ext/README-chrome.md](chrome-ext/README-chrome.md).

---

## Lovelace card

HACS-ready card that uses the ha-yt-dlp API.

**Install (HACS)**

1. **HACS → Frontend → ⋮ → Custom repositories** → add `https://github.com/tarczyk/ha-yt-dlp` → type **Dashboard**.
2. Search for **yt-dlp Downloader Card** and install.

The card is built as **`ha-yt-dlp.js`** in the repo root (source: `frontend/ha-card/yt-dlp-card.js`). After editing the card, run `./frontend/ha-card/sync-hacs.sh`.

**Add to dashboard**

```yaml
type: custom:yt-dlp-card
api_url: http://host.docker.internal:5000
title: YouTube Downloader
max_tasks: 10
```

| Option | Default | Description |
|--------|---------|-------------|
| `api_url` | `http://localhost:5000` | Base URL of the API. |
| `title` | `YouTube Downloader` | Card title. |
| `max_tasks` | `5` | Max task rows shown. |

Features: URL input, Download button, status badges (Processing / Completed / Failed), task list (polled), progress bar, link to Media Browser.

---

## Home Assistant integration (Docker only)

Use this **only if** you run the API via **Docker Compose** (e.g. on another host). If you use the **add-on**, the API and media are already in HA; skip this.

1. **Clone and configure** – set `API_PORT` and `DOWNLOAD_DIR` in `.env`; ensure `DOWNLOAD_DIR` is also available to HA (e.g. `/config/media`).
2. **Start:** `docker compose up -d`; verify `curl http://localhost:5000/health`.
3. **Media in HA** – in `configuration.yaml`:
   ```yaml
   homeassistant:
     media_dirs:
       youtube: /config/media
   ```
4. **REST command** – so automations can trigger downloads:
   ```yaml
   rest_command:
     download_youtube_video:
       url: "http://<docker-host>:5000/download_video"
       method: POST
       content_type: "application/json"
       payload: '{"url": "{{ url }}"}'
   ```
5. **Optional:** `input_text` for URL, automation on state change, REST sensor for task count.

If HA and Docker are on **different hosts**, expose the API (e.g. change port mapping from `127.0.0.1:5000:5000` to `5000:5000` and restrict with firewall or reverse proxy).

**Troubleshooting**

| Problem | Check |
|---------|--------|
| Connection refused | Container running; port reachable from HA. |
| `invalid url` | URL must start with `http://` or `https://`. |
| No files in Media | `media_dirs` set; HA restarted; `DOWNLOAD_DIR` matches path in HA config. |
| YouTube “Sign in” errors | Update yt-dlp: `docker compose pull && docker compose up -d`. |

---

## Development

**Hot reload (Docker)**

```yaml
# docker-compose.override.yml
services:
  yt-dlp:
    environment:
      FLASK_DEBUG: "1"
    volumes:
      - ./yt-dlp-api/app:/app/app
```

Then:

```bash
docker compose -f docker-compose.yml -f docker-compose.override.yml up --build
```

Flask will reload when you change files under `yt-dlp-api/app/`.

**Multi-arch build**

```bash
docker buildx create --use
docker buildx build --platform linux/amd64,linux/arm64 -t youruser/ha-yt-dlp:latest --push .
```

---

## Security

- Container: non-root user, read-only filesystem (only download dir writable), `no-new-privileges`, minimal base, pinned dependencies.
- Recommended in `docker-compose.yml`: `security_opt: no-new-privileges:true`, `read_only: true`, `cap_drop: [ALL]`, `tmpfs: [/tmp]`.
- Image scanned with **Trivy** in CI. Local: `trivy image tarczyk/ha-yt-dlp:latest`.

---

## License

MIT
