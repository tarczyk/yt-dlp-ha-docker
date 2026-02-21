/**
 * yt-dlp-card – Home Assistant Lovelace custom card
 * Connects to the ha-yt-dlp Flask API.
 *
 * Config options:
 *   api_url   – base URL of the Flask API  (default: http://localhost:5000)
 *   title     – card heading               (default: "YouTube Downloader")
 *   max_tasks – max rows shown in task list (default: 5)
 */

const DEFAULT_API_URL = "http://localhost:5000";
const DEFAULT_TITLE = "YouTube Downloader";
const DEFAULT_MAX_TASKS = 5;
const POLL_INTERVAL_MS = 2000;

const STATUS_COLORS = {
  queued: "#9e9e9e",
  running: "#2196f3",
  processing: "#2196f3",
  completed: "#4caf50",
  error: "#f44336",
  failed: "#f44336",
};

const STATUS_LABELS = {
  queued: "Queued",
  running: "Processing",
  processing: "Processing",
  completed: "Completed",
  error: "Failed",
  failed: "Failed",
};

const STYLES = `
  :host {
    display: block;
    font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
  }
  ha-card {
    padding: 16px;
  }
  .card-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 1.2rem;
    font-weight: 500;
    margin-bottom: 16px;
    color: var(--primary-text-color);
  }
  .input-row {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 16px;
  }
  .url-input {
    flex: 1;
    min-width: 0;
    padding: 10px 12px;
    border: 1px solid var(--divider-color, #e0e0e0);
    border-radius: 8px;
    font-size: 0.9rem;
    background: var(--card-background-color, #fff);
    color: var(--primary-text-color);
    outline: none;
    transition: border-color 0.2s;
  }
  .url-input:focus {
    border-color: var(--primary-color, #03a9f4);
  }
  .btn-download {
    padding: 10px 18px;
    background: var(--primary-color, #03a9f4);
    color: #fff;
    border: none;
    border-radius: 8px;
    font-size: 0.9rem;
    font-weight: 500;
    cursor: pointer;
    transition: opacity 0.2s, transform 0.1s;
    white-space: nowrap;
  }
  .btn-download:hover:not(:disabled) {
    opacity: 0.88;
  }
  .btn-download:active:not(:disabled) {
    transform: scale(0.97);
  }
  .btn-download:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .status-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
    color: #fff;
    vertical-align: middle;
  }
  .message-bar {
    padding: 8px 12px;
    border-radius: 8px;
    margin-bottom: 12px;
    font-size: 0.85rem;
  }
  .message-bar.error {
    background: #fdecea;
    color: #b71c1c;
    border-left: 4px solid #f44336;
  }
  .message-bar.success {
    background: #e8f5e9;
    color: #1b5e20;
    border-left: 4px solid #4caf50;
  }
  .section-title {
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--secondary-text-color, #888);
    margin-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .tasks-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
  }
  .tasks-table th {
    text-align: left;
    padding: 6px 8px;
    border-bottom: 2px solid var(--divider-color, #e0e0e0);
    color: var(--secondary-text-color, #888);
    font-weight: 500;
  }
  .tasks-table td {
    padding: 7px 8px;
    border-bottom: 1px solid var(--divider-color, #e0e0e0);
    vertical-align: middle;
  }
  .tasks-table tr:last-child td {
    border-bottom: none;
  }
  .progress-bar-wrap {
    background: var(--divider-color, #e0e0e0);
    border-radius: 4px;
    height: 6px;
    overflow: hidden;
    margin-top: 4px;
    min-width: 80px;
  }
  .progress-bar-fill {
    height: 100%;
    background: var(--primary-color, #03a9f4);
    border-radius: 4px;
    transition: width 0.4s ease;
  }
  .media-link {
    color: var(--primary-color, #03a9f4);
    text-decoration: none;
    font-size: 0.8rem;
  }
  .media-link:hover {
    text-decoration: underline;
  }
  .empty-state {
    text-align: center;
    padding: 20px 0;
    color: var(--secondary-text-color, #888);
    font-size: 0.9rem;
  }
  @media (max-width: 480px) {
    .input-row {
      flex-direction: column;
    }
    .btn-download {
      width: 100%;
    }
  }
`;

class YtDlpCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._tasks = [];
    this._url = "";
    this._busy = false;
    this._message = null;
    this._pollHandle = null;
  }

  static getConfigElement() {
    return document.createElement("yt-dlp-card-editor");
  }

  static getStubConfig() {
    return {
      api_url: DEFAULT_API_URL,
      title: DEFAULT_TITLE,
      max_tasks: DEFAULT_MAX_TASKS,
    };
  }

  setConfig(config) {
    this._config = {
      api_url: config.api_url || DEFAULT_API_URL,
      title: config.title !== undefined ? config.title : DEFAULT_TITLE,
      max_tasks: config.max_tasks !== undefined ? Number(config.max_tasks) : DEFAULT_MAX_TASKS,
    };
    this._render();
    this._startPolling();
  }

  connectedCallback() {
    this._startPolling();
  }

  disconnectedCallback() {
    this._stopPolling();
  }

  _apiUrl(path) {
    return `${this._config.api_url}${path}`;
  }

  _startPolling() {
    this._stopPolling();
    this._fetchTasks();
    this._pollHandle = setInterval(() => this._fetchTasks(), POLL_INTERVAL_MS);
  }

  _stopPolling() {
    if (this._pollHandle !== null) {
      clearInterval(this._pollHandle);
      this._pollHandle = null;
    }
  }

  async _fetchTasks() {
    try {
      const resp = await fetch(this._apiUrl("/tasks"));
      if (!resp.ok) return;
      const data = await resp.json();
      if (Array.isArray(data)) {
        this._tasks = data;
        this._updateTasksTable();
      }
    } catch (_e) {
      // Silently suppress network errors during background polling so that
      // temporary API unavailability does not disrupt the UI.
    }
  }

  async _handleDownload() {
    const url = this._url.trim();
    if (!url) return;
    this._busy = true;
    this._message = null;
    this._render();
    try {
      const resp = await fetch(this._apiUrl("/download_video"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        this._message = { type: "error", text: data.error || "Download failed" };
      } else {
        this._message = { type: "success", text: `Download queued (ID: ${data.task_id})` };
        this._url = "";
        await this._fetchTasks();
      }
    } catch (e) {
      this._message = { type: "error", text: "Cannot reach API: " + e.message };
    }
    this._busy = false;
    this._render();
  }

  _progressForStatus(status) {
    const map = { queued: 5, running: 50, processing: 50, completed: 100, error: 100, failed: 100 };
    return map[status] || 0;
  }

  _render() {
    const root = this.shadowRoot;
    root.innerHTML = `
      <style>${STYLES}</style>
      <ha-card>
        <div class="card-header">
          <span>📥</span>
          <span>${this._esc(this._config.title || DEFAULT_TITLE)}</span>
        </div>

        <div class="input-row">
          <input
            class="url-input"
            type="url"
            placeholder="https://www.youtube.com/watch?v=…"
            value="${this._esc(this._url)}"
            id="url-input"
          />
          <button
            class="btn-download"
            id="btn-download"
            ${this._busy ? "disabled" : ""}
          >
            ${this._busy ? "⏳ Downloading…" : "📥 Download Now"}
          </button>
        </div>

        ${this._message ? `
          <div class="message-bar ${this._message.type}">
            ${this._esc(this._message.text)}
          </div>` : ""}

        <div class="section-title">Recent Downloads</div>
        <div id="tasks-container">
          ${this._renderTasksTable()}
        </div>
      </ha-card>
    `;

    root.getElementById("url-input").addEventListener("input", (e) => {
      this._url = e.target.value;
    });
    root.getElementById("btn-download").addEventListener("click", () => {
      this._handleDownload();
    });
    root.getElementById("url-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter") this._handleDownload();
    });

    this._attachMediaLinks();
  }

  _updateTasksTable() {
    const container = this.shadowRoot && this.shadowRoot.getElementById("tasks-container");
    if (!container) {
      this._render();
      return;
    }
    container.innerHTML = this._renderTasksTable();
    this._attachMediaLinks();
  }

  _renderTasksTable() {
    const maxTasks = this._config.max_tasks || DEFAULT_MAX_TASKS;
    const tasks = this._tasks.slice(-maxTasks).reverse();

    if (tasks.length === 0) {
      return `<div class="empty-state">No downloads yet</div>`;
    }

    const rows = tasks.map((t) => {
      const status = t.status || "unknown";
      const color = STATUS_COLORS[status] || "#9e9e9e";
      const label = STATUS_LABELS[status] || status;
      const progress = this._progressForStatus(status);
      const isActive = status === "running" || status === "processing";

      const progressBar = `
        <div class="progress-bar-wrap">
          <div class="progress-bar-fill" style="width:${progress}%;${isActive ? "animation:none" : ""}"></div>
        </div>
      `;

      const mediaCell = status === "completed"
        ? `<a class="media-link" href="#" data-task-id="${this._esc(t.task_id || "")}" data-title="${this._esc(t.title || "")}">
            📂 Open
           </a>`
        : "—";

      return `
        <tr>
          <td title="${this._esc(t.url || "")}">${this._esc(this._truncate(t.title || t.url || "—", 28))}</td>
          <td>
            <span class="status-badge" style="background:${color}">${this._esc(label)}</span>
            ${progressBar}
          </td>
          <td>${mediaCell}</td>
        </tr>
      `;
    }).join("");

    return `
      <table class="tasks-table">
        <thead>
          <tr>
            <th>Title / URL</th>
            <th>Status</th>
            <th>Media</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  }

  _attachMediaLinks() {
    const root = this.shadowRoot;
    if (!root) return;
    root.querySelectorAll(".media-link").forEach((link) => {
      link.addEventListener("click", (e) => {
        e.preventDefault();
        this._openMediaBrowser(link.dataset.title || "");
      });
    });
  }

  _openMediaBrowser(_title) {
    const event = new CustomEvent("hass-action", {
      bubbles: true,
      composed: true,
      detail: {
        action: "navigate",
        navigation_path: `/media-browser/app,media-source://media_source/local/youtube_downloads`,
      },
    });
    this.dispatchEvent(event);
  }

  _truncate(str, max) {
    return str.length <= max ? str : str.slice(0, max) + "…";
  }

  _esc(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // HA Lovelace size hint
  getCardSize() {
    return 4;
  }
}

customElements.define("yt-dlp-card", YtDlpCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "yt-dlp-card",
  name: "yt-dlp Downloader Card",
  description: "Download YouTube videos via ha-yt-dlp API",
  preview: false,
  documentationURL: "https://github.com/tarczyk/ha-yt-dlp/tree/main/frontend/ha-card",
});
