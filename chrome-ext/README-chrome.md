# HA yt-dlp – Chrome Extension

A Manifest V3 Chrome extension that lets you download YouTube videos to your Home Assistant media library with a single click.

## Features

- **Auto-detect YouTube URL** – opens on any `youtube.com/watch` tab and pre-fills the video URL automatically
- **1-click download** – sends a `POST /download_video` request to your HA yt-dlp API
- **Progress and status** – indeterminate progress bar and messages: Queued → Downloading → Saved (or error). You can close the popup; the download continues on the server.
- **Folder and link** – on success, shows the destination folder (e.g. *My media → youtube_downloads*) and an optional **Open Media Browser** link if you set the HA Frontend URL in Settings
- **Clear errors** – failed downloads and invalid input show a short title and a detail line (e.g. server error message or hint to check the API URL)
- **Persistent settings** – yt-dlp API URL and optional HA Frontend URL are stored via `chrome.storage.sync`
- **Material Design 3 UI** – 350×300 px popup with dark/light theme support

## Permissions

| Permission | Reason |
|---|---|
| `tabs` | Read the URL of the active tab to auto-fill the YouTube URL |
| `activeTab` | Inspect the current tab without requesting all-tabs access |
| `storage` | Persist the HA API URL via `chrome.storage.sync` |
| `host_permissions` (`http://*/*`, `https://*/*`) | The HA API URL is user-configured at runtime and can be any private IP/hostname. Because the target URL is unknown at install time, a broad pattern is required. No requests are ever sent to third-party servers. |

## Install from the Chrome Web Store (recommended)

> The extension is published on the Chrome Web Store – no Developer Mode required.

1. Open the [HA yt-dlp Downloader](https://chrome.google.com/webstore/detail/ha-yt-dlp-downloader) listing.
2. Click **Add to Chrome**.
3. Confirm the permission prompt.

The extension icon will appear in the Chrome toolbar immediately.

## Install (Developer Mode / manual)

Use this method if you want to test a local build or an unreleased version.

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** (toggle in the top-right corner)
3. Click **Load unpacked**
4. Select the `chrome-ext/` folder from your `ha-yt-dlp` checkout

**Or install from a release zip:** On each [release](https://github.com/tarczyk/ha-yt-dlp/releases) you’ll find `ha-yt-dlp-chrome-ext-<version>.zip`. Download it, unzip, then in Chrome use **Load unpacked** and select the unzipped folder. You can also build the zip locally: from the repo root run `./chrome-ext/build-zip.sh`; the zip is created in `chrome-ext/`.

## Configuration

1. Click the extension icon on any page
2. Click **⚙ Settings** to expand the settings panel
3. **yt-dlp API URL** (required) – where the add-on or Docker API runs (e.g. `http://192.168.1.100:5000`)
4. **HA Frontend URL** (optional) – your Home Assistant UI URL (e.g. `http://homeassistant.local:8123`). If set, a link **Open Media Browser** is shown when a download completes
5. URLs are saved automatically when you leave each field (or when you click Download)

## Usage

1. Go to any YouTube video page (`youtube.com/watch?v=…`)
2. Click the extension icon – the video URL is filled automatically
3. Click **Download to HA**
4. Watch the status: **Queued…** → **Downloading…** (with progress bar) → **Saved: "Video title"** with folder and optional **Open Media Browser** link, or an error message with details

## Chrome Web Store

The extension is listed on the Chrome Web Store under the **Productivity** category.

- **Privacy policy:** [docs/privacy-policy.md](../docs/privacy-policy.md)
- **Automated publishing:** each GitHub Release triggers `.github/workflows/publish-chrome-ext.yml` which builds the zip and uploads it to the Chrome Web Store via the Publish API.
- **Setup guide:** see [docs/chrome-webstore-publish.md](../docs/chrome-webstore-publish.md) for one-time credentials setup.

> No data is sent to third parties. All network requests go directly to the user-configured local API.

## Folder Structure

```
chrome-ext/
├── manifest.json       # Manifest V3 extension descriptor
├── popup.html          # Extension popup UI (350×300 px, Material Design 3)
├── popup.js            # Popup logic (storage, tabs, fetch, polling)
├── background.js       # Service worker (fallback tab opener)
├── icons/
│   ├── icon-16.png
│   ├── icon-48.png
│   └── icon-128.png
├── screenshots/        # Chrome Web Store screenshots (add before publishing)
└── README-chrome.md    # This file
```

## API Endpoints Used

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/download_video` | Start download; returns `{"task_id": "..."}` |
| `GET`  | `/tasks/<task_id>` | Poll task status (`queued` / `running` / `completed` / `error`) |
| `GET`  | `/config`          | Read `media_subdir` to show the destination folder name |

See the root [`README.md`](../README.md) for full API documentation.
