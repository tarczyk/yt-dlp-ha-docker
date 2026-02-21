/* global chrome */
'use strict';

// 2 s balances responsiveness with API load; adjust if your HA host is slow.
const POLL_INTERVAL_MS = 2000;
const STORAGE_KEY_URL = 'haUrl';

let pollTimer = null;

// ── DOM refs ─────────────────────────────────────────────────────────────────
const haUrlInput    = document.getElementById('haUrl');
const videoUrlInput = document.getElementById('videoUrl');
const downloadBtn   = document.getElementById('downloadBtn');
const statusEl      = document.getElementById('status');
const statusTextEl  = document.getElementById('statusText');
const spinnerEl     = document.getElementById('spinner');
const settingsToggle = document.getElementById('settingsToggle');
const settingsPanel  = document.getElementById('settingsPanel');

// ── Helpers ───────────────────────────────────────────────────────────────────
function setStatus(state, message) {
  statusEl.className = state;
  statusTextEl.textContent = message;
  spinnerEl.style.display = state === 'processing' ? 'inline-block' : 'none';
}

function clearStatus() {
  statusEl.className = '';
  statusEl.style.display = 'none';
  stopPolling();
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

// ── Init: load saved HA URL and auto-fill YouTube URL ─────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Load saved HA URL from storage
  chrome.storage.sync.get(STORAGE_KEY_URL, (result) => {
    if (result[STORAGE_KEY_URL]) {
      haUrlInput.value = result[STORAGE_KEY_URL];
    } else {
      // Show settings panel so the user can configure the URL on first run
      settingsPanel.classList.add('open');
    }
  });

  // Auto-fill video URL from active YouTube tab
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs.length > 0 && tabs[0].url && isYouTubeUrl(tabs[0].url)) {
      videoUrlInput.value = tabs[0].url;
    }
  });
});

// ── Settings toggle ───────────────────────────────────────────────────────────
settingsToggle.addEventListener('click', () => {
  settingsPanel.classList.toggle('open');
});

// Persist HA URL whenever the field loses focus
haUrlInput.addEventListener('blur', () => {
  const url = haUrlInput.value.trim();
  if (url) {
    chrome.storage.sync.set({ [STORAGE_KEY_URL]: url });
  }
});

// ── Download button ───────────────────────────────────────────────────────────
downloadBtn.addEventListener('click', async () => {
  clearStatus();

  const haApiUrl  = haUrlInput.value.trim().replace(/\/$/, '');
  const videoUrl = videoUrlInput.value.trim();

  if (!haApiUrl) {
    setStatus('error', '❌ Please enter your HA API URL in Settings.');
    settingsPanel.classList.add('open');
    return;
  }

  if (!videoUrl) {
    setStatus('error', '❌ Please enter a YouTube URL.');
    return;
  }

  if (!isYouTubeUrl(videoUrl)) {
    setStatus('error', '❌ URL does not look like a YouTube watch page.');
    return;
  }

  // Persist HA URL
  chrome.storage.sync.set({ [STORAGE_KEY_URL]: haApiUrl });

  downloadBtn.disabled = true;
  setStatus('processing', 'Loading…');

  try {
    const response = await fetch(`${haApiUrl}/download_video`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: videoUrl }),
    });

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.error || `HTTP ${response.status}`);
    }

    const data = await response.json();
    const taskId = data.task_id;

    if (!taskId) {
      throw new Error('No task_id returned by the API.');
    }

    setStatus('processing', 'Processing…');
    startPolling(haApiUrl, taskId);
  } catch (err) {
    setStatus('error', `❌ ${err.message}`);
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
      case 'completed':
        stopPolling();
        setStatus('success', '✅ Saved to HA Media Browser!');
        downloadBtn.disabled = false;
        break;

      case 'failed':
        stopPolling();
        setStatus('error', `❌ Failed: ${task.error || 'unknown error'}`);
        downloadBtn.disabled = false;
        break;

      case 'processing':
      default:
        // Update progress if available
        // task.progress is an optional numeric 0-100 percentage reported by the API
        if (task.progress !== undefined) {
          setStatus('processing', `Processing… ${task.progress}%`);
        }
        break;
    }
  } catch (err) {
    // Transient network error – keep polling but surface a warning
    setStatus('processing', `Processing… (retrying: ${err.message})`);
  }
}
