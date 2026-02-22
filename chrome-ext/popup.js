/* global chrome */
'use strict';

// 2 s balances responsiveness with API load; adjust if your HA host is slow.
const POLL_INTERVAL_MS = 2000;
const STORAGE_KEY_URL = 'haUrl';
const STORAGE_KEY_HA_FRONTEND = 'haFrontendUrl';
const STORAGE_KEY_FORMAT = 'format';

let pollTimer = null;
let currentTaskId = null;
let currentHaUrl = null;

// ── DOM refs ─────────────────────────────────────────────────────────────────
const haUrlInput       = document.getElementById('haUrl');
const haFrontendInput  = document.getElementById('haFrontendUrl');
const videoUrlInput    = document.getElementById('videoUrl');
const formatMp4Radio   = document.getElementById('formatMp4');
const formatMp3Radio   = document.getElementById('formatMp3');
const downloadBtn      = document.getElementById('downloadBtn');
const statusEl         = document.getElementById('status');
const statusTextEl     = document.getElementById('statusText');
const statusDetailEl   = document.getElementById('statusDetail');
const spinnerEl        = document.getElementById('spinner');
const progressBarWrap  = document.getElementById('progressBarWrap');
const mediaLinkEl      = document.getElementById('mediaLink');
const cancelBtn        = document.getElementById('cancelBtn');
const settingsToggle   = document.getElementById('settingsToggle');
const settingsPanel    = document.getElementById('settingsPanel');

// ── Helpers ───────────────────────────────────────────────────────────────────
function setStatus(state, message, options) {
  options = options || {};
  statusEl.className = state;
  statusTextEl.textContent = message;
  statusDetailEl.textContent = options.detail || '';
  statusDetailEl.style.display = options.detail ? 'block' : 'none';
  spinnerEl.style.display = (state === 'processing') ? 'inline-block' : 'none';
  progressBarWrap.style.display = (state === 'processing') ? 'block' : 'none';
  if (options.mediaLinkUrl) {
    mediaLinkEl.href = options.mediaLinkUrl;
    mediaLinkEl.style.display = 'inline-block';
  } else {
    mediaLinkEl.style.display = 'none';
  }
  cancelBtn.style.display = (state === 'processing') ? 'inline-block' : 'none';
}

function setIdle() {
  stopPolling();
  currentTaskId = null;
  currentHaUrl = null;
  setStatus('idle', 'Ready.', { detail: 'Enter a YouTube URL and click Download to HA. Status and progress will appear here.' });
}

function clearStatus() {
  stopPolling();
  setIdle();
}

function stopPolling() {
  if (pollTimer !== null) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function isYouTubeUrl(url) {
  try {
    const u = new URL(url);
    return (
      (u.hostname === 'www.youtube.com' || u.hostname === 'youtube.com') &&
      u.pathname === '/watch' &&
      u.searchParams.has('v')
    );
  } catch {
    return false;
  }
}

/** True if URL is a playlist page (would trigger downloading many videos). */
function isPlaylistUrl(url) {
  try {
    const u = new URL(url);
    if (!u.hostname.includes('youtube.com')) return false;
    if (u.pathname.includes('/playlist')) return true;
    const hasList = u.searchParams.has('list');
    const hasV = u.searchParams.has('v');
    return hasList && !hasV;
  } catch {
    return false;
  }
}

/** For watch?v=XXX&list=... URLs, return only watch?v=XXX so only one video is requested. */
function toSingleVideoUrl(url) {
  try {
    const u = new URL(url);
    if (u.pathname !== '/watch' || !u.searchParams.has('v')) return url;
    const v = u.searchParams.get('v');
    u.search = '';
    u.searchParams.set('v', v);
    return u.toString();
  } catch {
    return url;
  }
}

// ── Init: load saved HA URL and auto-fill YouTube URL ─────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Load saved URLs from storage
  chrome.storage.sync.get([STORAGE_KEY_URL, STORAGE_KEY_HA_FRONTEND, STORAGE_KEY_FORMAT], (result) => {
    if (result[STORAGE_KEY_URL]) {
      haUrlInput.value = result[STORAGE_KEY_URL];
    } else {
      settingsPanel.classList.add('open');
    }
    if (result[STORAGE_KEY_HA_FRONTEND]) {
      haFrontendInput.value = result[STORAGE_KEY_HA_FRONTEND];
    }
    if (result[STORAGE_KEY_FORMAT] === 'mp3') {
      formatMp3Radio.checked = true;
    } else {
      formatMp4Radio.checked = true;
    }
  });

  // Auto-fill video URL from active YouTube tab
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs.length > 0 && tabs[0].url && isYouTubeUrl(tabs[0].url)) {
      videoUrlInput.value = tabs[0].url;
    }
  });

  // Show status area immediately (idle state)
  setIdle();
});

// ── Cancel button ─────────────────────────────────────────────────────────────
cancelBtn.addEventListener('click', async () => {
  if (!currentTaskId || !currentHaUrl) return;
  try {
    await fetch(`${currentHaUrl}/tasks/${currentTaskId}`, { method: 'DELETE' });
  } catch (_) { /* ignore */ }
  stopPolling();
  currentTaskId = null;
  currentHaUrl = null;
  setStatus('cancelled', 'Cancelled.', { detail: 'Download stop requested.' });
  downloadBtn.disabled = false;
  cancelBtn.style.display = 'none';
});

// ── Settings toggle ───────────────────────────────────────────────────────────
settingsToggle.addEventListener('click', () => {
  settingsPanel.classList.toggle('open');
});

// Persist URLs when fields lose focus
haUrlInput.addEventListener('blur', () => {
  const url = haUrlInput.value.trim();
  chrome.storage.sync.set({ [STORAGE_KEY_URL]: url || '' });
});
haFrontendInput.addEventListener('blur', () => {
  const url = haFrontendInput.value.trim();
  chrome.storage.sync.set({ [STORAGE_KEY_HA_FRONTEND]: url || '' });
});

// ── Download button ───────────────────────────────────────────────────────────
downloadBtn.addEventListener('click', async () => {
  clearStatus();

  const haApiUrl  = haUrlInput.value.trim().replace(/\/$/, '');
  const videoUrl = videoUrlInput.value.trim();

  if (!haApiUrl) {
    setStatus('error', 'Please enter the yt-dlp API URL in Settings.', { detail: 'Open Settings and set the URL where the add-on or Docker API runs (e.g. http://192.168.1.100:5000).' });
    settingsPanel.classList.add('open');
    return;
  }

  if (!videoUrl) {
    setStatus('error', 'Please enter a YouTube URL.', { detail: 'Paste a link from youtube.com/watch?v=... or use the extension on an open YouTube tab.' });
    return;
  }

  if (!isYouTubeUrl(videoUrl)) {
    setStatus('error', 'Invalid YouTube URL.', { detail: 'Use a link like https://www.youtube.com/watch?v=...' });
    return;
  }

  if (isPlaylistUrl(videoUrl)) {
    setStatus('error', 'Playlist links are not allowed.', {
      detail: 'Use a single video URL (e.g. youtube.com/watch?v=...). Opening a video from the playlist and using that link is OK.',
    });
    return;
  }

  // Send only the single-video URL (strip list= / start_radio=) so only this video is downloaded
  const singleVideoUrl = toSingleVideoUrl(videoUrl);
  const selectedFormat = formatMp3Radio.checked ? 'mp3' : 'mp4';

  // Persist URLs
  const haFrontendUrl = haFrontendInput.value.trim();
  chrome.storage.sync.set({
    [STORAGE_KEY_URL]: haApiUrl,
    [STORAGE_KEY_HA_FRONTEND]: haFrontendUrl,
    [STORAGE_KEY_FORMAT]: selectedFormat,
  });

  downloadBtn.disabled = true;
  setStatus('processing', 'Queued…', { detail: 'Sending request to the API.' });

  try {
    const response = await fetch(`${haApiUrl}/download_video`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: singleVideoUrl, format: selectedFormat }),
    });

    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body.error || `Server error: ${response.status}`);
    }

    const taskId = body.task_id;
    if (!taskId) {
      throw new Error('API did not return a task ID.');
    }

    currentTaskId = taskId;
    currentHaUrl = haApiUrl;
    setStatus('processing', 'Downloading…', { detail: 'The file is being downloaded. You can close this popup; the download continues on the server.' });
    startPolling(haApiUrl, taskId);
  } catch (err) {
    const detail = err.message || 'Check that the API URL is correct and the add-on or Docker service is running.';
    setStatus('error', 'Download failed.', { detail });
    downloadBtn.disabled = false;
  }
});

// ── Polling ───────────────────────────────────────────────────────────────────
function startPolling(haUrl, taskId) {
  stopPolling();
  pollTimer = setInterval(() => pollTask(haUrl, taskId), POLL_INTERVAL_MS);
}

async function pollTask(haUrl, taskId) {
  try {
    const response = await fetch(`${haUrl}/tasks/${taskId}`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const task = await response.json();

    switch (task.status) {
      case 'cancelled':
        stopPolling();
        currentTaskId = null;
        currentHaUrl = null;
        setStatus('cancelled', 'Cancelled.', { detail: 'Download was stopped.' });
        downloadBtn.disabled = false;
        break;

      case 'completed': {
        stopPolling();
        currentTaskId = null;
        currentHaUrl = null;
        let folderLabel = 'My media';
        try {
          const configRes = await fetch(`${haUrl}/config`);
          if (configRes.ok) {
            const config = await configRes.json();
            const subdir = config.media_subdir || 'youtube_downloads';
            folderLabel = `My media → ${subdir}`;
          }
        } catch (_) { /* ignore */ }
        const title = task.title ? `"${task.title}"` : 'File';
        chrome.storage.sync.get(STORAGE_KEY_HA_FRONTEND, (result) => {
          const haFrontend = (result[STORAGE_KEY_HA_FRONTEND] || '').trim().replace(/\/$/, '');
          // URL must be encoded: comma %2C, colon %3A, slashes %2F (HA Media Browser expects this)
          const mediaPath = 'media-browser/browser/app%2Cmedia-source%3A%2F%2Fmedia_source';
          const mediaLinkUrl = haFrontend ? `${haFrontend}/${mediaPath}` : null;
          setStatus('success', `Saved: ${title}`, {
            detail: `Folder: ${folderLabel}.`,
            mediaLinkUrl: mediaLinkUrl || undefined,
          });
        });
        downloadBtn.disabled = false;
        break;
      }

      case 'error':
        stopPolling();
        currentTaskId = null;
        currentHaUrl = null;
        setStatus('error', 'Download failed.', {
          detail: task.error || 'Unknown error from the server.',
        });
        downloadBtn.disabled = false;
        break;

      case 'queued':
        setStatus('processing', 'Queued…', { detail: 'Waiting for the server to start the download.' });
        break;

      case 'running':
      default:
        setStatus('processing', 'Downloading…', {
          detail: 'The file is being downloaded. You can close this popup; the download continues on the server.',
        });
        break;
    }
  } catch (err) {
    setStatus('processing', 'Downloading…', {
      detail: `Connection issue (retrying): ${err.message}`,
    });
  }
}
