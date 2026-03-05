# Installing ha-yt-dlp on Windows

ha-yt-dlp runs inside a Docker container, so the easiest way to use it on Windows is with **Docker Desktop**.  
No Linux or Home Assistant OS is required.

---

## Prerequisites

| Tool | Download |
|------|----------|
| **Docker Desktop** (includes Docker Compose) | <https://www.docker.com/products/docker-desktop> |
| **Git for Windows** *(optional – needed only to clone the repo)* | <https://git-scm.com/download/win> |

After installing Docker Desktop, make sure it is running (the whale icon in the system tray should be visible).

---

## Step-by-step installation

### 1. Get the repository

Open **PowerShell** or **Git Bash** and run:

```powershell
git clone https://github.com/tarczyk/ha-yt-dlp.git
cd ha-yt-dlp
```

*No Git?* Download the ZIP from GitHub (**Code → Download ZIP**), extract it, and open a terminal in the extracted folder.

---

### 2. Configure the environment

Edit the `.env` file in the project root (you can open it with Notepad or any text editor):

```ini
# Port exposed on the host for the Flask API
API_PORT=5000

# Folder on Windows where downloaded videos will be saved
# Use forward slashes or double back-slashes, e.g.:
#   C:/Users/YourName/Videos/youtube_downloads
#   C:\\Users\\YourName\\Videos\\youtube_downloads
DOWNLOAD_DIR=C:/Users/YourName/Videos/youtube_downloads

# Optional extra flags for yt-dlp (leave empty if unsure)
YT_DLP_EXTRA_ARGS=
```

> **Tip:** Make sure the folder set in `DOWNLOAD_DIR` already exists, or Docker will create it automatically when the container starts.

---

### 3. Update `docker-compose.yml` to use the `.env` variable

The default `docker-compose.yml` uses a hardcoded Linux path for the volume.  
Replace the `volumes` line so it picks up `DOWNLOAD_DIR` from `.env`:

**Before:**
```yaml
    volumes:
      - ./config/media:/config/media
```

**After:**
```yaml
    volumes:
      - ${DOWNLOAD_DIR}:/config/media
```

---

### 4. Start the container

```powershell
docker compose up -d --build
```

Docker will pull/build the image and start the service in the background.

Check that it is running:

```powershell
docker compose ps
```

You should see the `yt-dlp-ha` container with status **Up**.

---

### 5. Verify the API

```powershell
curl http://localhost:5000/health
```

Expected response: `{"status": "healthy"}`

Test a download:

```powershell
curl -X POST http://localhost:5000/download_video `
  -H "Content-Type: application/json" `
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

Downloaded files will appear in the folder you set in `DOWNLOAD_DIR`.

---

## Stopping and restarting

```powershell
# Stop
docker compose down

# Start again (no rebuild needed)
docker compose up -d
```

---

## Connecting the Chrome extension or Lovelace card

Use `http://localhost:5000` (or `http://127.0.0.1:5000`) as the API URL in the extension or card settings.

If Home Assistant is running on a **different machine** and needs to reach the API, change the port binding in `docker-compose.yml` from:

```yaml
ports:
  - "127.0.0.1:5000:5000"
```

to:

```yaml
ports:
  - "5000:5000"
```

Then use `http://<your-windows-pc-ip>:5000` in HA.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `docker: command not found` | Docker Desktop is not installed or not running. Start it from the Start menu. |
| Port 5000 already in use | Change `API_PORT` in `.env` and restart. |
| Container exits immediately | Run `docker compose logs yt-dlp` to see the error. |
| Files not appearing in `DOWNLOAD_DIR` | Check the path in `.env`; make sure the folder exists and Docker Desktop has access to that drive (**Docker Desktop → Settings → Resources → File Sharing**). |
| YouTube "Sign in" errors | Update yt-dlp: `docker compose pull && docker compose up -d`. |

---

## Updating

```powershell
docker compose pull
docker compose up -d
```

---

*For Home Assistant Add-on installation (requires HA OS/Supervised) see the main [README](../README.md).*
