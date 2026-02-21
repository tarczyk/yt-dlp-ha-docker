/* eslint-disable no-undef */
const info = {
  name: "yt-dlp Downloader Card",
  version: "1.0.0",
  repository: "https://github.com/tarczyk/yt-dlp-ha-docker",
  documentation: "https://github.com/tarczyk/yt-dlp-ha-docker/tree/main/frontend/ha-card",
  issues: "https://github.com/tarczyk/yt-dlp-ha-docker/issues",
};

// Expose info for HACS and other tooling
if (typeof window !== "undefined") {
  window.ytDlpCardInfo = info;
}

module.exports = info;
