/* eslint-disable no-undef */
const info = {
  name: "yt-dlp Downloader Card",
  version: "1.0.3",
  repository: "https://github.com/tarczyk/ha-yt-dlp",
  documentation: "https://github.com/tarczyk/ha-yt-dlp/tree/main/frontend/ha-card",
  issues: "https://github.com/tarczyk/ha-yt-dlp/issues",
};

// Expose info for HACS and other tooling
if (typeof window !== "undefined") {
  window.ytDlpCardInfo = info;
}

module.exports = info;
