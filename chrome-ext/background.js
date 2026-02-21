/* global chrome */
'use strict';

/**
 * background.js – Manifest V3 service worker
 *
 * NOTE: Because `default_popup` is set in manifest.json, `chrome.action.onClicked`
 * will never fire in normal operation – the popup handles all user interaction.
 * This listener is intentionally kept as a future-proofing safety net: if the
 * popup is ever removed from the manifest, clicking the icon on a non-YouTube
 * tab will open youtube.com instead of doing nothing.
 */
chrome.action.onClicked.addListener((tab) => {
  // This listener only fires when there is no popup configured.
  // With default_popup set in manifest.json it will never be called,
  // but it is kept as a safety net for future configuration changes.
  const youtubeBase = 'https://www.youtube.com/';
  if (!tab.url || !tab.url.startsWith(youtubeBase)) {
    chrome.tabs.create({ url: youtubeBase });
  }
});
