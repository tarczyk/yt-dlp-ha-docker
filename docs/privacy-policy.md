# Privacy Policy – HA yt-dlp Downloader (Chrome Extension)

**Last updated: 2026-02-25**

## Overview

The **HA yt-dlp Downloader** Chrome extension lets you send YouTube video URLs to your own self-hosted [ha-yt-dlp](https://github.com/tarczyk/ha-yt-dlp) API so that videos are downloaded to your Home Assistant media library.

## Data collected and stored

| Data | Where it is stored | Purpose |
|------|--------------------|---------|
| yt-dlp API URL (user-entered) | `chrome.storage.sync` (your Google account) | Remembers the address of your local API between sessions |
| HA Frontend URL (user-entered, optional) | `chrome.storage.sync` (your Google account) | Provides an "Open Media Browser" shortcut link after a download |

No other data is collected, processed, or stored by this extension.

## Network requests

All network requests made by the extension go **exclusively** to the API URL that _you_ entered in the extension settings (e.g. `http://192.168.1.100:5000`). This is a private, local address that you control.

- The extension **never** sends data to the extension developer or any third-party server.
- No analytics, telemetry, or crash-reporting services are used.
- No data about YouTube pages you visit is transmitted anywhere other than the local API you configured.

## Permissions justification

| Permission | Reason |
|------------|--------|
| `tabs` / `activeTab` | Read the URL of the active YouTube tab to pre-fill the video URL field. No other tab data is read or stored. |
| `storage` | Persist your API URL setting via `chrome.storage.sync`. |
| `host_permissions` (`http://*/*`, `https://*/*`) | The HA API URL is configured by the user at runtime and can be any private IP address or hostname. Because the target is not known at install time, a broad host pattern is required. Requests are only sent to the address you explicitly entered. |

## Changes to this policy

If this policy changes materially, the updated version will be committed to this repository and the "Last updated" date above will be revised.

## Contact

Open an issue at <https://github.com/tarczyk/ha-yt-dlp/issues>.
