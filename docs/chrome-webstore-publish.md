# Publishing the Chrome Extension to the Chrome Web Store

This guide explains how to set up the required credentials and publish the **HA yt-dlp Downloader** extension to the Chrome Web Store so that users can install it without enabling Developer Mode.

## One-time setup

### 1. Create a Chrome Web Store developer account

1. Go to <https://chrome.google.com/webstore/devconsole> and sign in with a Google account.
2. Pay the one-time $5 developer registration fee (if you haven't already).

### 2. Upload the extension for the first time (manual, initial submission only)

1. Build the zip locally:
   ```bash
   cd chrome-ext
   ./build-zip.sh
   ```
2. In the Chrome Web Store Developer Console click **New item** and upload the zip.
3. Fill in the store listing:
   - **Name:** HA yt-dlp Downloader
   - **Category:** Productivity
   - **Description:** (copy from `chrome-ext/README-chrome.md`)
   - **Privacy policy URL:** `https://github.com/tarczyk/ha-yt-dlp/blob/main/docs/privacy-policy.md`
   - **Screenshots:** at least one image at 1280×800 or 640×400 px (see `chrome-ext/screenshots/`)
   - **Single-purpose description:** explain the broad `host_permissions` (the API URL is user-configured at runtime and is a private local address; no data is sent to third parties)
4. Submit for review. Initial review typically takes 1–3 business days.
5. After approval, note the **Extension ID** shown in the Developer Console (a 32-character string).

### 3. Obtain OAuth2 credentials for automated publishing

The GitHub Actions workflow uses the [Chrome Web Store Publish API](https://developer.chrome.com/docs/webstore/using_webstore_api/).

#### a. Create a Google Cloud project and enable the Chrome Web Store API

1. Go to <https://console.cloud.google.com/> and create a new project (or use an existing one).
2. Navigate to **APIs & Services → Library** and enable the **Chrome Web Store API**.

#### b. Create OAuth2 credentials

1. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
2. Choose **Desktop app** as the application type.
3. Note the **Client ID** and **Client Secret**.

#### c. Obtain a refresh token

Run the following (replace `YOUR_CLIENT_ID` and `YOUR_CLIENT_SECRET`):

```bash
# Step 1 – open this URL in a browser, log in and copy the `code` from the redirect URL
open "https://accounts.google.com/o/oauth2/auth?response_type=code&scope=https://www.googleapis.com/auth/chromewebstore&client_id=YOUR_CLIENT_ID&redirect_uri=urn:ietf:wg:oauth:2.0:oob"

# Step 2 – exchange the code for tokens (replace YOUR_CODE)
curl -s -X POST https://accounts.google.com/o/oauth2/token \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET" \
  -d "code=YOUR_CODE" \
  -d "grant_type=authorization_code" \
  -d "redirect_uri=urn:ietf:wg:oauth:2.0:oob"
```

The response contains a `refresh_token`. Save it securely.

### 4. Add secrets to the GitHub repository

Go to **Settings → Secrets and variables → Actions** in the GitHub repository and add:

| Secret name | Value |
|-------------|-------|
| `CHROME_EXTENSION_ID` | 32-character extension ID from the Developer Console |
| `CHROME_CLIENT_ID` | OAuth2 Client ID |
| `CHROME_CLIENT_SECRET` | OAuth2 Client Secret |
| `CHROME_REFRESH_TOKEN` | Refresh token from step 3c |

## Automated publishing

After the one-time setup, every time a GitHub Release is **published** the workflow `.github/workflows/publish-chrome-ext.yml` will:

1. Build the extension zip from the `chrome-ext/` directory.
2. Upload it to the Chrome Web Store using the Publish API.
3. Submit it for review automatically (`publish: true`).

You can also trigger the workflow manually from the **Actions** tab using the `workflow_dispatch` event.

## Updating the store listing

Store listing text, screenshots, and other metadata must be updated manually in the [Chrome Web Store Developer Console](https://chrome.google.com/webstore/devconsole). Only the extension package (zip) is updated automatically by CI.
