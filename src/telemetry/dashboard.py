"""Single-page HTML dashboard for telemetry data."""

DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Home HUD Telemetry</title>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f5f7fa; color: #333; line-height: 1.5;
  padding: 1rem; max-width: 1200px; margin: 0 auto;
}
h1 { font-size: 1.5rem; margin-bottom: 0.5rem; }
h2 { font-size: 1.1rem; margin: 1.5rem 0 0.5rem; color: #555; }
.subtitle { color: #888; font-size: 0.85rem; margin-bottom: 1rem; }

/* Summary cards */
.cards {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 0.75rem; margin-bottom: 1rem;
}
.card {
  background: #fff; border-radius: 8px; padding: 1rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.card .label { font-size: 0.75rem; color: #888; text-transform: uppercase; }
.card .value { font-size: 1.5rem; font-weight: 700; font-family: 'SF Mono', Monaco, monospace; }
.card .value.error { color: #e74c3c; }

/* Tables */
table {
  width: 100%; border-collapse: collapse; background: #fff;
  border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  margin-bottom: 1rem; font-size: 0.85rem;
}
th, td { padding: 0.5rem 0.75rem; text-align: left; }
th { background: #f0f2f5; font-weight: 600; font-size: 0.75rem;
     text-transform: uppercase; color: #666; }
td { border-top: 1px solid #eee; font-family: 'SF Mono', Monaco, monospace; }
tr:hover td { background: #fafbfc; }

/* Breakdown grids */
.breakdown {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 0.75rem; margin-bottom: 1rem;
}
.breakdown-section { background: #fff; border-radius: 8px; padding: 1rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.breakdown-section h3 { font-size: 0.85rem; color: #555; margin-bottom: 0.5rem; }
.breakdown-row { display: flex; justify-content: space-between; padding: 0.25rem 0;
  font-size: 0.85rem; border-bottom: 1px solid #f0f2f5; }
.breakdown-row:last-child { border-bottom: none; }
.breakdown-row .name { color: #555; }
.breakdown-row .count { font-family: 'SF Mono', Monaco, monospace; font-weight: 600; }

/* Session list */
.session-row { cursor: pointer; }
.session-row:hover td { background: #f0f5ff; }
.session-row.expanded td { background: #e8f0fe; }

/* Session detail */
.session-detail { display: none; }
.session-detail td { padding: 0; }
.session-detail-inner { padding: 1rem; background: #fafbfc; }
.session-detail-inner h4 { font-size: 0.85rem; margin: 0.75rem 0 0.25rem; color: #555; }
.session-detail-inner h4:first-child { margin-top: 0; }

/* Exchange detail */
.exchange-row { cursor: pointer; }
.exchange-row:hover td { background: #f0f5ff; }
.exchange-detail { display: none; }
.exchange-detail td { padding: 0; }
.exchange-detail-inner { padding: 0.75rem 1rem; background: #f5f7fa; }

/* LLM call cards */
.llm-card { background: #fff; border: 1px solid #e0e0e0; border-radius: 6px;
  padding: 0.75rem; margin-bottom: 0.5rem; font-size: 0.8rem; }
.llm-card .llm-header { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 0.5rem; }
.llm-card .llm-header span { color: #888; }
.llm-card .llm-header strong { color: #333; }
.llm-content { margin-top: 0.5rem; }
.llm-content label { font-size: 0.75rem; color: #888; text-transform: uppercase; display: block; }
.llm-content pre { background: #f0f2f5; padding: 0.5rem; border-radius: 4px;
  white-space: pre-wrap; word-break: break-word; font-size: 0.8rem;
  max-height: 200px; overflow-y: auto; margin-bottom: 0.5rem; }
.truncated { max-height: 60px; overflow: hidden; position: relative; }
.truncated::after { content: ''; position: absolute; bottom: 0; left: 0; right: 0;
  height: 30px; background: linear-gradient(transparent, #f0f2f5); }
.expand-btn { background: none; border: none; color: #3b82f6; cursor: pointer;
  font-size: 0.8rem; padding: 0; margin-top: 0.25rem; }

/* Flags */
.flag { display: inline-block; padding: 0.1rem 0.4rem; border-radius: 4px;
  font-size: 0.7rem; font-weight: 600; margin-right: 0.25rem; }
.flag-vad { background: #dbeafe; color: #2563eb; }
.flag-bargein { background: #fef3c7; color: #d97706; }
.flag-followup { background: #e0e7ff; color: #4f46e5; }
.flag-error { background: #fee2e2; color: #dc2626; }
.flag-rejected { background: #fde8e8; color: #9b1c1c; }

/* Pagination */
.pagination { display: flex; gap: 0.5rem; align-items: center; margin: 0.5rem 0; }
.pagination button { padding: 0.25rem 0.75rem; border: 1px solid #ddd;
  border-radius: 4px; background: #fff; cursor: pointer; font-size: 0.85rem; }
.pagination button:disabled { opacity: 0.4; cursor: default; }
.pagination button:hover:not(:disabled) { background: #f0f2f5; }
.pagination .info { font-size: 0.8rem; color: #888; }

/* Display preview */
.display-preview {
  background: #fff; border-radius: 8px; padding: 1rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 1rem;
}
.display-preview img {
  max-width: 100%; height: auto; border: 1px solid #eee; border-radius: 4px;
  display: block;
}
.display-preview .meta { font-size: 0.75rem; color: #888; margin-top: 0.5rem; }

/* Log viewer */
.log-viewer {
  background: #1e1e1e; border-radius: 8px; padding: 1rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 1rem;
}
.log-controls {
  display: flex; gap: 0.75rem; align-items: center; margin-bottom: 0.75rem;
  flex-wrap: wrap;
}
.log-controls select, .log-controls button {
  padding: 0.3rem 0.6rem; border: 1px solid #555; border-radius: 4px;
  background: #2d2d2d; color: #ccc; font-size: 0.8rem; cursor: pointer;
}
.log-controls button:hover { background: #3d3d3d; }
.log-controls label { color: #aaa; font-size: 0.8rem; cursor: pointer; }
.log-controls .log-meta { color: #666; font-size: 0.75rem; margin-left: auto; }
.log-entries {
  max-height: 500px; overflow-y: auto; font-family: 'SF Mono', Monaco, monospace;
  font-size: 0.75rem; line-height: 1.4;
}
.log-entry { padding: 0.15rem 0.5rem; white-space: pre-wrap; word-break: break-all; }
.log-entry:hover { background: rgba(255,255,255,0.05); }
.log-entry.level-DEBUG { color: #888; }
.log-entry.level-INFO { color: #6cb6ff; }
.log-entry.level-WARNING { color: #e3b341; }
.log-entry.level-ERROR { color: #f85149; }
.log-entry.level-CRITICAL { color: #ff6b6b; font-weight: 700; }
.log-timestamp { color: #666; }
.log-level { font-weight: 600; min-width: 5ch; display: inline-block; }
.log-logger { color: #999; }

/* Config section */
.config-section { background: #fff; border-radius: 8px; padding: 1rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 1rem; }
.config-group { margin-bottom: 0.75rem; }
.config-group-header {
  display: flex; align-items: center; cursor: pointer; padding: 0.4rem 0;
  border-bottom: 1px solid #eee; user-select: none;
}
.config-group-header h3 { font-size: 0.85rem; color: #555; margin: 0; flex: 1; }
.config-group-header .toggle { font-size: 0.75rem; color: #888; }
.config-group-body { margin-top: 0.25rem; }
.config-row { display: flex; justify-content: space-between; padding: 0.25rem 0;
  font-size: 0.85rem; border-bottom: 1px solid #f0f2f5; }
.config-row:last-child { border-bottom: none; }
.config-row .key { color: #555; }
.config-row .val { font-family: 'SF Mono', Monaco, monospace; font-weight: 500;
  color: #333; max-width: 60%; text-align: right; word-break: break-all; }
.config-row { align-items: center; }
.config-row .desc { font-size: 0.75rem; color: #999; margin-top: 0.1rem; }
.config-row .source-badge {
  display: inline-block; padding: 0.1rem 0.35rem; border-radius: 3px;
  font-size: 0.65rem; font-weight: 600; margin-left: 0.5rem; vertical-align: middle;
}
.source-default { background: #f0f2f5; color: #888; }
.source-env { background: #dbeafe; color: #2563eb; }
.source-file { background: #d1fae5; color: #065f46; }
.config-input {
  padding: 0.3rem 0.5rem; border: 1px solid #d1d5db; border-radius: 4px;
  font-size: 0.85rem; font-family: 'SF Mono', Monaco, monospace;
  background: #fff; width: 200px; text-align: right;
}
.config-input:focus { outline: none; border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59,130,246,0.15); }
.config-input.dirty { border-color: #f59e0b; background: #fffbeb; }
.config-toggle { position: relative; display: inline-block;
  width: 36px; height: 20px; vertical-align: middle; }
.config-toggle input { opacity: 0; width: 0; height: 0; }
.config-toggle .slider {
  position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0;
  background: #ccc; border-radius: 20px; transition: 0.2s;
}
.config-toggle .slider::before {
  content: ''; position: absolute; height: 14px; width: 14px; left: 3px; bottom: 3px;
  background: #fff; border-radius: 50%; transition: 0.2s;
}
.config-toggle input:checked + .slider { background: #3b82f6; }
.config-toggle input:checked + .slider::before { transform: translateX(16px); }
.config-toggle.dirty .slider { background: #f59e0b; }
.config-toggle.dirty input:checked + .slider { background: #f59e0b; }
.config-save-btn {
  padding: 0.5rem 1.5rem; background: #3b82f6; color: #fff;
  border: none; border-radius: 6px; font-size: 0.9rem;
  cursor: pointer; font-weight: 600;
}
.config-save-btn:hover { background: #2563eb; }
.config-save-btn:disabled { opacity: 0.5; cursor: default; }

/* Tab bar */
.tab-bar {
  display: flex; gap: 0; border-bottom: 2px solid #e0e3e8;
  margin-bottom: 1rem; position: sticky; top: 0; background: #f5f7fa;
  z-index: 10; padding-top: 0.25rem;
}
.tab-btn {
  padding: 0.5rem 1.25rem; border: none; background: none; cursor: pointer;
  font-size: 0.9rem; color: #888; font-weight: 500; border-bottom: 2px solid transparent;
  margin-bottom: -2px; transition: color 0.15s, border-color 0.15s;
}
.tab-btn:hover { color: #555; }
.tab-btn.active { color: #3b82f6; border-bottom-color: #3b82f6; font-weight: 700; }
.tab-panel { display: none; }
.tab-panel.active { display: block; }

/* Service monitor form */
.svc-input {
  padding: 0.4rem 0.6rem; border: 1px solid #ddd;
  border-radius: 4px; font-size: 0.85rem; display: block;
}
.svc-add-btn {
  padding: 0.4rem 1rem; background: #3b82f6; color: #fff;
  border: none; border-radius: 4px; cursor: pointer;
  font-size: 0.85rem; font-weight: 600;
}
.svc-sm-btn {
  background: none; border: 1px solid #ddd; border-radius: 4px;
  padding: 0.2rem 0.6rem; cursor: pointer; font-size: 0.8rem;
}
.svc-act-btn {
  cursor: pointer; background: none;
  border: 1px solid #ccc; border-radius: 4px;
  padding: 0.15rem 0.4rem; font-size: 0.75rem;
  margin-right: 0.25rem;
}
.svc-del-btn {
  cursor: pointer; background: none;
  border: 1px solid #e74c3c; color: #e74c3c;
  border-radius: 4px; padding: 0.15rem 0.4rem;
  font-size: 0.75rem;
}
.svc-editable { cursor: pointer; }
.svc-editable:hover { background: #f0f5ff; }
.svc-edit-input {
  padding: 0.2rem 0.4rem; border: 1px solid #3b82f6;
  border-radius: 3px; font-size: 0.85rem;
  font-family: inherit; width: 100%;
}

/* Loading / error */
.loading { text-align: center; padding: 2rem; color: #888; }
.error-msg { text-align: center; padding: 1rem; color: #e74c3c; background: #fee2e2;
  border-radius: 8px; margin: 1rem 0; }

/* Timeline bar */
.timeline-bar {
  display: flex; height: 28px; border-radius: 6px; overflow: hidden;
  background: #f0f2f5; width: 100%; min-width: 120px;
}
.timeline-seg {
  min-width: 2px; height: 100%; position: relative;
  transition: opacity 0.15s;
}
.timeline-seg:hover { opacity: 0.8; }
.timeline-seg.phase-recording { background: #3b82f6; }
.timeline-seg.phase-stt { background: #22c55e; }
.timeline-seg.phase-routing { background: #f59e0b; }
.timeline-seg.phase-tts { background: #a855f7; }
.timeline-seg.phase-playback { background: #14b8a6; }
.timeline-seg.gap { background: #e5e7eb; }
.timeline-legend {
  display: flex; gap: 0.75rem; flex-wrap: wrap; font-size: 0.75rem;
  color: #666; margin-bottom: 0.5rem;
}
.timeline-legend .dot {
  display: inline-block; width: 10px; height: 10px; border-radius: 50%;
  margin-right: 0.25rem; vertical-align: middle;
}
.phase-breakdown { font-size: 0.8rem; margin: 0.5rem 0; }
.phase-breakdown td { padding: 0.2rem 0.5rem; border-top: 1px solid #eee; }
.phase-breakdown .gap-row td { color: #999; font-style: italic; }

/* Responsive */
@media (max-width: 600px) {
  body { padding: 0.5rem; }
  .cards { grid-template-columns: repeat(2, 1fr); }
  td, th { padding: 0.35rem 0.5rem; font-size: 0.8rem; }
  .tab-btn { padding: 0.5rem 0.75rem; font-size: 0.8rem; }
}
</style>
</head>
<body>
<h1>Home HUD Telemetry</h1>
<p class="subtitle">Voice pipeline performance and usage data</p>

<div class="tab-bar">
  <button class="tab-btn active" onclick="switchTab('tab-overview')">Overview</button>
  <button class="tab-btn" onclick="switchTab('tab-sessions')">Sessions</button>
  <button class="tab-btn" onclick="switchTab('tab-logs')">Logs</button>
  <button class="tab-btn" onclick="switchTab('tab-config')">Config</button>
  <button class="tab-btn" onclick="switchTab('tab-voice-cache')">Voice Cache</button>
  <button class="tab-btn" onclick="switchTab('tab-services')">Services</button>
</div>

<div class="tab-panel active" id="tab-overview">
  <div id="stats-loading" class="loading">Loading stats...</div>
  <div id="stats-error" class="error-msg" style="display:none"></div>

  <div id="stats-content" style="display:none">
    <div class="cards" id="summary-cards"></div>

    <h2>Phase Performance (avg ms)</h2>
    <table id="perf-table">
      <thead><tr><th>Phase</th><th>Avg Duration (ms)</th></tr></thead>
      <tbody></tbody>
    </table>

    <div class="breakdown" id="breakdown-grid"></div>
  </div>

  <h2>Display Preview</h2>
  <div class="display-preview" id="display-preview">
    <div id="display-img-container" class="loading">Loading display...</div>
    <div class="meta" id="display-meta"></div>
  </div>
</div>

<div class="tab-panel" id="tab-sessions">
  <div class="pagination" id="pagination-top"></div>
  <table id="sessions-table">
    <thead>
      <tr>
        <th>Time</th><th>Exchanges</th><th>Duration</th>
        <th>Feature</th><th>Transcription</th>
      </tr>
    </thead>
    <tbody id="sessions-body">
      <tr><td colspan="5" class="loading">Loading sessions...</td></tr>
    </tbody>
  </table>
  <div class="pagination" id="pagination-bottom"></div>
</div>

<div class="tab-panel" id="tab-logs">
  <div class="log-viewer" id="log-viewer">
    <div class="log-controls">
      <select id="log-level-filter">
        <option value="">All Levels</option>
        <option value="DEBUG">DEBUG</option>
        <option value="INFO" selected>INFO</option>
        <option value="WARNING">WARNING</option>
        <option value="ERROR">ERROR</option>
        <option value="CRITICAL">CRITICAL</option>
      </select>
      <button onclick="loadLogs()">Refresh</button>
      <label><input type="checkbox" id="log-auto-refresh" checked> Auto-refresh (10s)</label>
      <span class="log-meta" id="log-meta"></span>
    </div>
    <div class="log-entries" id="log-entries">
      <div style="color:#888;padding:1rem">Loading logs...</div>
    </div>
  </div>
</div>

<div class="tab-panel" id="tab-config">
  <div id="config-banner" class="error-msg"
    style="display:none;background:#fef3c7;color:#92400e;
    margin-bottom:1rem"></div>
  <div class="config-section" id="config-section">
    <div class="loading" id="config-loading">Loading config...</div>
    <div id="config-content"></div>
    <div id="config-actions" style="display:none;margin-top:1rem;
      padding-top:0.75rem;border-top:1px solid #eee">
      <button id="config-save-btn" onclick="saveConfig()"
        class="config-save-btn">Save Changes</button>
      <span id="config-save-status"
        style="margin-left:0.75rem;font-size:0.85rem;
        color:#888"></span>
    </div>
  </div>
</div>

<div class="tab-panel" id="tab-voice-cache">
  <div id="vc-loading" class="loading">Loading voice cache...</div>
  <div id="vc-error" class="error-msg" style="display:none"></div>
  <div id="vc-content" style="display:none">
    <div class="cards" id="vc-cards"></div>
    <table id="vc-table">
      <thead>
        <tr>
          <th>Play</th><th>Text</th><th>Voice</th><th>Model</th>
          <th>Hits</th><th>Size</th><th>Created</th>
        </tr>
      </thead>
      <tbody id="vc-body"></tbody>
    </table>
  </div>
</div>

<div class="tab-panel" id="tab-services">
  <div id="svc-loading" class="loading">Loading services...</div>
  <div id="svc-error" class="error-msg" style="display:none"></div>
  <div id="svc-content" style="display:none">
    <div class="card" style="margin-bottom:1rem">
      <h3 class="label" style="margin-bottom:0.75rem">Add Service</h3>
      <div style="display:flex;gap:0.5rem;flex-wrap:wrap;align-items:end">
        <div>
          <label class="label">Name</label>
          <input id="svc-name" type="text" placeholder="My Service"
            class="svc-input" style="width:160px">
        </div>
        <div>
          <label class="label">URL / Host</label>
          <input id="svc-url" type="text"
            placeholder="http://192.168.1.1 or 192.168.1.1"
            class="svc-input" style="width:260px">
        </div>
        <div>
          <label class="label">Type</label>
          <select id="svc-type" class="svc-input">
            <option value="http">HTTP</option>
            <option value="ping">Ping</option>
          </select>
        </div>
        <button onclick="addService()" class="svc-add-btn">Add</button>
        <button onclick="testNewService()" class="svc-sm-btn">Test</button>
      </div>
      <div id="svc-test-result"
        style="font-size:0.8rem;margin-top:0.5rem;display:none"></div>
      <div id="svc-add-error" class="error-msg"
        style="font-size:0.8rem;margin-top:0.5rem;display:none"></div>
    </div>
    <table id="svc-table">
      <thead>
        <tr>
          <th>Status</th><th>Name</th><th>URL</th><th>Type</th>
          <th>Response</th><th>Uptime (30d)</th>
          <th>Last Checked</th><th>Actions</th>
        </tr>
      </thead>
      <tbody id="svc-body"></tbody>
    </table>
    <div id="svc-history-panel" class="card"
      style="display:none;margin-top:1rem">
      <div style="display:flex;justify-content:space-between;
        align-items:center;margin-bottom:0.75rem">
        <h3 id="svc-history-title" class="label"></h3>
        <button onclick="closeSvcHistory()"
          class="svc-sm-btn">Close</button>
      </div>
      <canvas id="svc-history-canvas" height="60"
        style="width:100%;border-radius:4px"></canvas>
      <div id="svc-history-stats"
        style="font-size:0.8rem;color:#888;margin-top:0.5rem"></div>
    </div>
  </div>
</div>

<script>
const PAGE_SIZE = 50;
let currentOffset = 0;
let totalSessions = 0;

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function fmt(v) { return v != null ? v.toLocaleString() : '-'; }
function fmtMs(v) { return v != null && Number.isFinite(v) ? Math.round(v).toLocaleString() : '-'; }
function fmtPct(n, total) { return total ? (n / total * 100).toFixed(1) + '%' : '0%'; }

function fmtTime(iso) {
  if (!iso) return '-';
  const d = new Date(iso);
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString();
}

function fmtDuration(ms) {
  if (ms == null || !Number.isFinite(ms)) return '-';
  if (ms < 1000) return ms + 'ms';
  return (ms / 1000).toFixed(1) + 's';
}

function truncate(s, len) {
  if (!s) return '-';
  return s.length > len ? s.slice(0, len) + '...' : s;
}

function makeCard(label, value, cls) {
  return `<div class="card"><div class="label">${label}</div>`
    + `<div class="value${cls ? ' ' + cls : ''}">${value}</div></div>`;
}

// --- Timeline helpers ---
const PHASE_ORDER = ['recording', 'stt', 'routing', 'tts', 'playback'];
const PHASE_LABELS = {
  recording:'Recording', stt:'STT', routing:'Routing',
  tts:'TTS', playback:'Playback'
};

function tsMs(iso) {
  if (!iso) return null;
  const ms = new Date(iso.replace('+00:00', 'Z').replace('+0000', 'Z')).getTime();
  return Number.isFinite(ms) ? ms : null;
}

function exchangeWallClock(ex) {
  let first = null, last = null;
  for (const p of PHASE_ORDER) {
    const s = tsMs(ex[p + '_started_at']);
    const e = tsMs(ex[p + '_ended_at']);
    if (s != null && (first == null || s < first)) first = s;
    if (e != null && (last == null || e > last)) last = e;
  }
  return (first != null && last != null) ? last - first : null;
}

function computeSegments(ex) {
  const segs = [];
  let prevEnd = null;
  for (const p of PHASE_ORDER) {
    const s = tsMs(ex[p + '_started_at']);
    const e = tsMs(ex[p + '_ended_at']);
    if (s == null || e == null) continue;
    if (prevEnd != null) {
      const gap = Math.max(0, s - prevEnd);
      if (gap > 0) segs.push({name: 'gap', type: 'gap', duration_ms: gap, from: p});
    }
    segs.push({name: p, type: 'phase', duration_ms: Math.max(0, e - s)});
    prevEnd = e;
  }
  return segs;
}

function renderTimeline(ex) {
  const wall = exchangeWallClock(ex);
  if (!wall || wall <= 0) return '<span style="color:#888">-</span>';
  const segs = computeSegments(ex);
  let html = '<div class="timeline-bar">';
  for (const seg of segs) {
    const pct = Math.max(0.5, seg.duration_ms / wall * 100);
    const cls = seg.type === 'gap' ? 'gap' : 'phase-' + seg.name;
    const label = seg.type === 'gap'
      ? 'gap: ' + Math.round(seg.duration_ms) + 'ms'
      : PHASE_LABELS[seg.name] + ': ' + Math.round(seg.duration_ms) + 'ms';
    const extra = (seg.name === 'tts' && seg.duration_ms < 10)
      ? ' (streaming — actual synthesis during playback)' : '';
    html += '<div class="timeline-seg ' + cls + '" style="width:' + pct.toFixed(2)
      + '%" title="' + label + extra + '"></div>';
  }
  html += '</div>';
  return html;
}

function renderTimelineLegend() {
  const colors = {
    recording:'#3b82f6', stt:'#22c55e', routing:'#f59e0b',
    tts:'#a855f7', playback:'#14b8a6', gap:'#e5e7eb'
  };
  let html = '<div class="timeline-legend">';
  for (const [key, color] of Object.entries(colors)) {
    const label = key === 'gap' ? 'Gap' : PHASE_LABELS[key] || key;
    html += '<span><span class="dot" style="background:' + color + '"></span>' + label + '</span>';
  }
  html += '</div>';
  return html;
}

function renderPhaseBreakdown(ex) {
  const wall = exchangeWallClock(ex);
  const segs = computeSegments(ex);
  if (!segs.length) return '<p style="color:#888;font-size:0.8rem">No phase timing data.</p>';
  let html = '<table class="phase-breakdown"><thead><tr>'
    + '<th>Phase</th><th>Duration</th><th>% of Total</th>'
    + '</tr></thead><tbody>';
  let sumPhases = 0;
  for (const seg of segs) {
    const isGap = seg.type === 'gap';
    const cls = isGap ? ' class="gap-row"' : '';
    const name = isGap ? '&nbsp;&nbsp;→ gap' : PHASE_LABELS[seg.name] || seg.name;
    const dur = Math.round(seg.duration_ms);
    const pct = wall ? (seg.duration_ms / wall * 100).toFixed(1) + '%' : '-';
    if (!isGap) sumPhases += seg.duration_ms;
    html += '<tr' + cls + '><td>' + name + '</td>'
      + '<td>' + fmtMs(dur) + ' ms</td>'
      + '<td>' + pct + '</td></tr>';
  }
  // Totals
  if (wall) {
    const unaccounted = Math.max(0, wall - segs.reduce((a, s) => a + s.duration_ms, 0));
    html += '<tr style="font-weight:600;border-top:2px solid #ccc">'
      + '<td>Total (wall)</td>'
      + '<td>' + fmtMs(Math.round(wall)) + ' ms</td>'
      + '<td>100%</td></tr>';
    const pPct = (sumPhases / wall * 100).toFixed(1);
    html += '<tr><td>Sum of phases</td>'
      + '<td>' + fmtMs(Math.round(sumPhases)) + ' ms</td>'
      + '<td>' + pPct + '%</td></tr>';
    if (unaccounted > 0.5) {
      const uPct = (unaccounted / wall * 100).toFixed(1);
      html += '<tr class="gap-row"><td>Unaccounted</td>'
        + '<td>' + fmtMs(Math.round(unaccounted)) + ' ms</td>'
        + '<td>' + uPct + '%</td></tr>';
    }
  }
  html += '</tbody></table>';
  return html;
}

async function loadStats() {
  try {
    const data = await fetchJSON('/api/stats');
    const el = document.getElementById('summary-cards');
    const totalTokens = (data.total_input_tokens || 0) + (data.total_output_tokens || 0);
    el.innerHTML = [
      makeCard('Sessions', fmt(data.total_sessions)),
      makeCard('Exchanges', fmt(data.total_exchanges)),
      makeCard('LLM Calls', fmt(data.total_llm_calls)),
      makeCard('Tokens Used', fmt(totalTokens)),
      makeCard('Errors', fmt(data.error_count), data.error_count > 0 ? 'error' : ''),
      makeCard('Rejected', fmt(data.rejected_count), data.rejected_count > 0 ? 'error' : ''),
      makeCard('Today', `${fmt(data.sessions_today)}s / ${fmt(data.exchanges_today)}e`),
    ].join('');

    // Performance table with gaps
    const phases = ['recording', 'stt', 'routing', 'tts', 'playback'];
    const gapKeys = [
      'avg_rec_to_stt_gap_ms', 'avg_stt_to_routing_gap_ms',
      'avg_routing_to_tts_gap_ms', 'avg_tts_to_playback_gap_ms'
    ];
    const tbody = document.querySelector('#perf-table tbody');
    let totalAvg = 0;
    let rows = '';
    phases.forEach((p, i) => {
      const v = data['avg_' + p + '_ms'];
      if (v != null) totalAvg += v;
      rows += `<tr><td>${p}</td><td>${fmtMs(v)}</td></tr>`;
      if (i < gapKeys.length) {
        const g = data[gapKeys[i]];
        rows += '<tr class="gap-row" style="color:#999;'
          + 'font-style:italic"><td>&nbsp;&nbsp;→ gap</td>'
          + '<td>' + fmtMs(g) + '</td></tr>';
      }
    });
    const wallAvg = data.avg_wall_clock_ms;
    rows += '<tr style="font-weight:600;border-top:2px solid #ccc">'
      + '<td>Total (wall clock)</td>'
      + '<td>' + fmtMs(wallAvg) + '</td></tr>';
    rows += `<tr><td>Sum of phases</td><td>${fmtMs(totalAvg)}</td></tr>`;
    if (wallAvg != null && totalAvg) {
      const unaccounted = Math.round(wallAvg - totalAvg);
      if (unaccounted > 0) {
        rows += '<tr style="color:#999;font-style:italic">'
          + '<td>&nbsp;&nbsp;Unaccounted</td>'
          + '<td>' + fmtMs(unaccounted) + '</td></tr>';
      }
    }
    tbody.innerHTML = rows;

    // Breakdowns
    const grid = document.getElementById('breakdown-grid');
    let html = '';

    // Feature counts
    const fc = data.feature_counts || {};
    const fcTotal = Object.values(fc).reduce((a, b) => a + b, 0);
    if (fcTotal > 0) {
      html += '<div class="breakdown-section"><h3>Features</h3>';
      const sorted = Object.entries(fc).sort((a, b) => b[1] - a[1]);
      html += sorted.map(([name, count]) =>
        `<div class="breakdown-row"><span class="name">${name || '(none)'}</span>`
        + `<span class="count">${count} (${fmtPct(count, fcTotal)})</span></div>`
      ).join('');
      html += '</div>';
    }

    // Routing counts
    const rc = data.routing_counts || {};
    const rcTotal = Object.values(rc).reduce((a, b) => a + b, 0);
    if (rcTotal > 0) {
      html += '<div class="breakdown-section"><h3>Routing Paths</h3>';
      const sorted = Object.entries(rc).sort((a, b) => b[1] - a[1]);
      html += sorted.map(([name, count]) =>
        `<div class="breakdown-row"><span class="name">${name || '(none)'}</span>`
        + `<span class="count">${count} (${fmtPct(count, rcTotal)})</span></div>`
      ).join('');
      html += '</div>';
    }

    grid.innerHTML = html;

    document.getElementById('stats-loading').style.display = 'none';
    document.getElementById('stats-content').style.display = '';
  } catch (e) {
    document.getElementById('stats-loading').style.display = 'none';
    const err = document.getElementById('stats-error');
    err.textContent = 'Failed to load stats: ' + e.message;
    err.style.display = '';
  }
}

async function loadSessions(offset) {
  currentOffset = offset || 0;
  const tbody = document.getElementById('sessions-body');
  tbody.innerHTML = '<tr><td colspan="5" class="loading">Loading...</td></tr>';

  try {
    const data = await fetchJSON(`/api/sessions?limit=${PAGE_SIZE}&offset=${currentOffset}`);
    totalSessions = data.total;
    renderPagination();

    if (data.sessions.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="loading">No sessions yet.</td></tr>';
      return;
    }

    tbody.innerHTML = data.sessions.map(s => {
      const features = (s.features_used || []).join(', ') || '-';
      const trans = truncate(s.first_transcription, 40);
      return `<tr class="session-row" data-id="${s.id}">`
        + `<td>${fmtTime(s.started_at)}</td>`
        + `<td>${s.exchange_count}</td>`
        + `<td>${fmtDuration(s.duration_ms)}</td>`
        + `<td>${features}</td>`
        + `<td>${trans}</td></tr>`
        + `<tr class="session-detail" data-detail="${s.id}">`
        + `<td colspan="5"><div class="session-detail-inner">`
        + `<div class="loading">Loading detail...</div></div></td></tr>`;
    }).join('');

    // Attach click handlers
    tbody.querySelectorAll('.session-row').forEach(row => {
      row.addEventListener('click', () => toggleSession(row.dataset.id));
    });
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="5" class="error-msg">Error: ${e.message}</td></tr>`;
  }
}

function renderPagination() {
  const html = (id) => {
    const el = document.getElementById(id);
    const page = Math.floor(currentOffset / PAGE_SIZE) + 1;
    const pages = Math.ceil(totalSessions / PAGE_SIZE) || 1;
    el.innerHTML = `<button onclick="loadSessions(${currentOffset - PAGE_SIZE})" `
      + `${currentOffset <= 0 ? 'disabled' : ''}>Prev</button>`
      + `<span class="info">Page ${page} of ${pages} (${totalSessions} total)</span>`
      + `<button onclick="loadSessions(${currentOffset + PAGE_SIZE})" `
      + `${currentOffset + PAGE_SIZE >= totalSessions ? 'disabled' : ''}>Next</button>`;
  };
  html('pagination-top');
  html('pagination-bottom');
}

async function toggleSession(id) {
  const detail = document.querySelector(`tr[data-detail="${id}"]`);
  const row = document.querySelector(`tr[data-id="${id}"]`);
  if (detail.style.display === 'table-row') {
    detail.style.display = 'none';
    row.classList.remove('expanded');
    return;
  }
  row.classList.add('expanded');
  detail.style.display = 'table-row';

  const inner = detail.querySelector('.session-detail-inner');
  try {
    const data = await fetchJSON(`/api/sessions/${id}`);
    let html = `<h4>Session</h4>`
      + `<div style="font-size:0.8rem;margin-bottom:0.5rem">`
      + `Wake model: <strong>${data.session.wake_model || '-'}</strong> | `
      + `Started: ${fmtTime(data.session.started_at)} | `
      + `Ended: ${fmtTime(data.session.ended_at)}</div>`;

    if (data.exchanges.length === 0) {
      html += '<p style="color:#888">No exchanges.</p>';
    } else {
      html += '<h4>Exchanges</h4>';
      html += renderTimelineLegend();
      html += '<table><thead><tr>'
        + '<th>#</th><th>Transcription</th><th>Route</th>'
        + '<th style="min-width:200px">Timeline</th><th>Total</th><th>Flags</th>'
        + '</tr></thead><tbody>';

      data.exchanges.forEach((ex, i) => {
        let flags = '';
        if (ex.used_vad) flags += '<span class="flag flag-vad">VAD</span>';
        if (ex.had_bargein) flags += '<span class="flag flag-bargein">BARGE</span>';
        if (ex.is_follow_up) flags += '<span class="flag flag-followup">FOLLOW</span>';
        if (ex.error) flags += '<span class="flag flag-error">ERR</span>';
        if (ex.routing_path && ex.routing_path.startsWith('rejected_'))
          flags += '<span class="flag flag-rejected">REJ</span>';

        const wall = exchangeWallClock(ex);
        html += `<tr class="exchange-row" data-exid="${ex.id}">`
          + `<td>${ex.sequence}</td>`
          + `<td>${truncate(ex.transcription, 40)}</td>`
          + `<td>${ex.routing_path || '-'}`
          + `${ex.matched_feature ? ' > ' + ex.matched_feature : ''}</td>`
          + `<td>${renderTimeline(ex)}</td>`
          + `<td>${fmtDuration(wall != null ? Math.round(wall) : null)}</td>`
          + `<td>${flags || '-'}</td></tr>`;

        // Exchange detail row
        html += `<tr class="exchange-detail" data-exdetail="${ex.id}"><td colspan="6">`
          + `<div class="exchange-detail-inner">`;

        // Response text (moved from table to detail)
        if (ex.response_text) {
          html += '<h4>Response</h4>';
          html += '<pre style="background:#f0f2f5;padding:0.5rem;border-radius:4px;'
            + 'white-space:pre-wrap;word-break:break-word;font-size:0.8rem;'
            + 'max-height:200px;overflow-y:auto;margin-bottom:0.5rem">'
            + escapeHtml(ex.response_text) + '</pre>';
        }

        // Phase breakdown
        html += '<h4>Phase Breakdown</h4>';
        html += renderPhaseBreakdown(ex);

        if (ex.error) {
          html += `<p style="color:#dc2626;margin-bottom:0.5rem">Error: ${ex.error}</p>`;
        }

        if (ex.stt_no_speech_prob != null || ex.stt_avg_logprob != null) {
          html += '<h4>STT Confidence</h4>';
          html += '<div style="font-size:0.8rem;'
            + 'font-family:SF Mono,Monaco,monospace;'
            + 'margin-bottom:0.5rem">';
          const nsp = ex.stt_no_speech_prob;
          const alp = ex.stt_avg_logprob;
          html += '<span style="margin-right:1.5rem">'
            + 'no_speech_prob: <strong>'
            + (nsp != null ? nsp.toFixed(4) : '-')
            + '</strong></span>';
          html += '<span>avg_logprob: <strong>'
            + (alp != null ? alp.toFixed(4) : '-')
            + '</strong></span>';
          if (ex.routing_path
              && ex.routing_path.startsWith('rejected_')) {
            const reason = ex.routing_path
              .replace('rejected_', '')
              .replace(/_/g, ' ');
            html += '<span style="margin-left:1.5rem;'
              + 'color:#9b1c1c;font-weight:600">'
              + ` (${reason})</span>`;
          }
          html += '</div>';
        }

        if (ex.llm_calls && ex.llm_calls.length > 0) {
          html += '<h4>LLM Calls</h4>';
          ex.llm_calls.forEach(call => {
            html += `<div class="llm-card">`;
            html += `<div class="llm-header">`
              + `<span>Type: <strong>${call.call_type}</strong></span>`
              + `<span>Model: <strong>${call.model || '-'}</strong></span>`
              + `<span>Duration: <strong>${fmtMs(call.duration_ms)}ms</strong></span>`
              + `<span>Tokens: <strong>${fmt(call.input_tokens)} in`
              + ` / ${fmt(call.output_tokens)} out</strong></span>`
              + `<span>Stop: <strong>${call.stop_reason || '-'}</strong></span>`
              + `</div>`;

            if (call.error) {
              html += `<p style="color:#dc2626">Error: ${call.error}</p>`;
            }

            html += '<div class="llm-content">';
            if (call.system_prompt) {
              const spId = 'sp-' + Math.random().toString(36).slice(2);
              html += `<label>System Prompt</label>`
                + `<pre class="truncated" id="${spId}">${escapeHtml(call.system_prompt)}</pre>`
                + `<button class="expand-btn" onclick="toggleExpand('${spId}')">Show full</button>`;
            }
            if (call.user_message) {
              html += `<label>User Message</label><pre>${escapeHtml(call.user_message)}</pre>`;
            }
            if (call.response_text) {
              html += `<label>Response</label><pre>${escapeHtml(call.response_text)}</pre>`;
            }
            html += '</div></div>';
          });
        } else {
          html += '<p style="color:#888;font-size:0.8rem">No LLM calls for this exchange.</p>';
        }

        html += '</div></td></tr>';
      });
      html += '</tbody></table>';
    }

    inner.innerHTML = html;

    // Attach exchange row click handlers
    inner.querySelectorAll('.exchange-row').forEach(row => {
      row.addEventListener('click', () => {
        const detail = inner.querySelector(`tr[data-exdetail="${row.dataset.exid}"]`);
        detail.style.display = detail.style.display === 'table-row' ? 'none' : 'table-row';
      });
    });
  } catch (e) {
    inner.innerHTML = `<p class="error-msg">Failed to load: ${e.message}</p>`;
  }
}

function toggleExpand(id) {
  const el = document.getElementById(id);
  const btn = el.nextElementSibling;
  if (el.classList.contains('truncated')) {
    el.classList.remove('truncated');
    btn.textContent = 'Show less';
  } else {
    el.classList.add('truncated');
    btn.textContent = 'Show full';
  }
}

function escapeHtml(s) {
  if (!s) return '';
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

async function loadDisplay() {
  const container = document.getElementById('display-img-container');
  const meta = document.getElementById('display-meta');
  try {
    const res = await fetch('/api/display');
    if (!res.ok) {
      container.innerHTML = '<span style="color:#888">No display snapshot available.</span>';
      container.classList.remove('loading');
      meta.textContent = '';
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    container.innerHTML = `<img src="${url}" alt="Display snapshot">`;
    container.classList.remove('loading');
    meta.textContent = 'Last refreshed: ' + new Date().toLocaleTimeString();
  } catch (e) {
    container.innerHTML = '<span style="color:#888">Could not load display snapshot.</span>';
    container.classList.remove('loading');
    meta.textContent = '';
  }
}

// --- Log viewer ---
let logAutoRefreshTimer = null;

async function loadLogs() {
  const container = document.getElementById('log-entries');
  const level = document.getElementById('log-level-filter').value;
  const url = '/api/logs?lines=200' + (level ? '&level=' + level : '');

  // Check if user is scrolled to bottom before update
  const wasAtBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 30;

  try {
    const data = await fetchJSON(url);
    if (data.lines.length === 0) {
      container.innerHTML = '<div style="color:#888;padding:1rem">No log entries found.</div>';
    } else {
      container.innerHTML = data.lines.map(e => {
        const ts = '<span class="log-timestamp">' + escapeHtml(e.timestamp) + '</span>';
        const lv = '<span class="log-level">' + escapeHtml(e.level) + '</span>';
        const lg = '<span class="log-logger">' + escapeHtml(e.logger) + '</span>';
        return '<div class="log-entry level-' + escapeHtml(e.level) + '">'
          + ts + ' ' + lv + ' ' + lg + ': ' + escapeHtml(e.message) + '</div>';
      }).join('');
    }

    // Auto-scroll to bottom only if user was already at bottom
    if (wasAtBottom) container.scrollTop = container.scrollHeight;

    document.getElementById('log-meta').textContent =
      data.total_lines + ' entries | ' + new Date().toLocaleTimeString();
  } catch (e) {
    container.innerHTML = '<div style="color:#f85149;padding:1rem">Failed to load logs: '
      + escapeHtml(e.message) + '</div>';
  }
}

function setupLogAutoRefresh() {
  const cb = document.getElementById('log-auto-refresh');
  function toggle() {
    if (logAutoRefreshTimer) { clearInterval(logAutoRefreshTimer); logAutoRefreshTimer = null; }
    if (cb.checked) logAutoRefreshTimer = setInterval(loadLogs, 10000);
  }
  cb.addEventListener('change', toggle);
  toggle();
}

document.getElementById('log-level-filter').addEventListener('change', () => {
  if (loadedTabs.has('tab-logs')) loadLogs();
});

// --- Config editor ---
let configOriginal = {};  // original values keyed by param key
let configDirty = {};     // changed values keyed by param key

function renderConfigInput(p) {
  const id = 'cfg-input-' + p.key;
  if (p.sensitive) {
    return '<span class="val">********</span>';
  }
  if (p.type === 'bool') {
    const checked = p.value === true ? ' checked' : '';
    return '<label class="config-toggle" id="toggle-' + p.key + '">'
      + '<input type="checkbox" id="' + id + '"' + checked
      + ' onchange="onConfigChange(\\'' + p.key + '\\', this.checked, \\'' + p.type + '\\')">'
      + '<span class="slider"></span></label>';
  }
  const inputType = (p.type === 'int' || p.type === 'float') ? 'number' : 'text';
  const step = p.type === 'float' ? ' step="any"' : '';
  const val = p.value != null ? escapeHtml(String(p.value)) : '';
  return '<input type="' + inputType + '" class="config-input" id="' + id + '"'
    + ' value="' + val + '"' + step
    + ' oninput="onConfigChange(\\'' + p.key + '\\', this.value, \\'' + p.type + '\\')"'
    + ' onchange="onConfigChange(\\'' + p.key + '\\', this.value, \\'' + p.type + '\\')">';
}

function onConfigChange(key, rawValue, type) {
  let value = rawValue;
  if (type === 'int') value = rawValue === '' ? '' : parseInt(rawValue, 10);
  else if (type === 'float') value = rawValue === '' ? '' : parseFloat(rawValue);
  else if (type === 'bool') value = rawValue;
  else value = String(rawValue);

  const orig = configOriginal[key];
  const changed = value !== orig && String(value) !== String(orig);
  const el = document.getElementById('cfg-input-' + key);

  if (changed) {
    configDirty[key] = value;
    if (el) el.classList.add('dirty');
    const toggle = document.getElementById('toggle-' + key);
    if (toggle) toggle.classList.add('dirty');
  } else {
    delete configDirty[key];
    if (el) el.classList.remove('dirty');
    const toggle = document.getElementById('toggle-' + key);
    if (toggle) toggle.classList.remove('dirty');
  }

  const btn = document.getElementById('config-save-btn');
  const actions = document.getElementById('config-actions');
  if (!btn || !actions) return;
  const count = Object.keys(configDirty).length;
  if (count > 0) {
    actions.style.display = '';
    btn.textContent = 'Save ' + count + ' Change' + (count > 1 ? 's' : '');
  } else {
    actions.style.display = 'none';
  }
}

async function saveConfig() {
  const btn = document.getElementById('config-save-btn');
  const status = document.getElementById('config-save-status');
  btn.disabled = true;
  btn.textContent = 'Saving...';
  status.textContent = '';

  // Convert values to strings for the config file
  const payload = {};
  for (const [k, v] of Object.entries(configDirty)) {
    payload[k] = typeof v === 'boolean' ? (v ? 'true' : 'false') : String(v);
  }

  try {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      status.textContent = data.error || 'Save failed';
      status.style.color = '#e74c3c';
      btn.disabled = false;
      btn.textContent = 'Save Changes';
      return;
    }
    // Update originals so fields are no longer dirty
    for (const k of Object.keys(configDirty)) {
      configOriginal[k] = configDirty[k];
      const el = document.getElementById('cfg-input-' + k);
      if (el) el.classList.remove('dirty');
      const toggle = document.getElementById('toggle-' + k);
      if (toggle) toggle.classList.remove('dirty');
    }
    configDirty = {};
    btn.textContent = 'Save Changes';
    btn.disabled = false;
    document.getElementById('config-actions').style.display = 'none';

    const banner = document.getElementById('config-banner');
    banner.textContent = 'Changes saved to config file. Restart to apply.';
    banner.style.display = '';
  } catch (e) {
    status.textContent = 'Error: ' + e.message;
    status.style.color = '#e74c3c';
    btn.disabled = false;
    btn.textContent = 'Save Changes';
  }
}

async function loadConfig() {
  const loading = document.getElementById('config-loading');
  const content = document.getElementById('config-content');
  try {
    const data = await fetchJSON('/api/config');
    if (data.error) {
      loading.textContent = data.error;
      return;
    }
    loading.style.display = 'none';
    configOriginal = {};
    configDirty = {};

    let html = '';
    for (const group of data.groups) {
      const groupParams = data.params.filter(p => p.group === group);
      if (groupParams.length === 0) continue;

      const gid = 'cfg-' + group.toLowerCase().replace(/\\s+/g, '-');
      html += '<div class="config-group" id="' + gid + '">';
      html += '<div class="config-group-header" onclick="toggleConfigGroup(\\'' + gid + '\\')">';
      html += '<h3>' + escapeHtml(group) + '</h3>';
      html += '<span class="toggle">&#9660;</span></div>';
      html += '<div class="config-group-body">';

      groupParams.forEach(p => {
        configOriginal[p.key] = p.value;
        const sourceCls = 'source-' + p.source;
        html += '<div class="config-row">'
          + '<div style="flex:1;min-width:0">'
          + '<span class="key">' + escapeHtml(p.key) + '</span>'
          + '<span class="source-badge ' + sourceCls + '">' + p.source + '</span>'
          + '<div class="desc">' + escapeHtml(p.description) + '</div>'
          + '</div>'
          + '<div style="flex-shrink:0;margin-left:0.75rem">' + renderConfigInput(p) + '</div>'
          + '</div>';
      });

      html += '</div></div>';
    }
    content.innerHTML = html;
    document.getElementById('config-actions').style.display = 'none';
  } catch (e) {
    loading.textContent = 'Failed to load config: ' + e.message;
    loading.style.color = '#e74c3c';
  }
}

function toggleConfigGroup(id) {
  const group = document.getElementById(id);
  const body = group.querySelector('.config-group-body');
  const toggle = group.querySelector('.toggle');
  if (body.style.display === 'none') {
    body.style.display = '';
    toggle.innerHTML = '&#9660;';
  } else {
    body.style.display = 'none';
    toggle.innerHTML = '&#9654;';
  }
}

// --- Voice Cache ---
function fmtBytes(b) {
  if (b == null) return '-';
  if (b < 1024) return b + ' B';
  if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
  return (b / 1048576).toFixed(1) + ' MB';
}

let vcAudioEl = null;
function playCache(hash) {
  if (vcAudioEl) { vcAudioEl.pause(); vcAudioEl = null; }
  vcAudioEl = new Audio('/api/tts-cache/' + hash + '/audio');
  vcAudioEl.play();
}

async function loadVoiceCache() {
  try {
    const data = await fetchJSON('/api/tts-cache');
    const cards = document.getElementById('vc-cards');
    const totalHits = data.entries.reduce((a, e) => a + (e.hit_count || 0), 0);
    cards.innerHTML = [
      makeCard('Entries', fmt(data.total_entries)),
      makeCard('Total Size', fmtBytes(data.total_size_bytes)),
      makeCard('Total Hits', fmt(totalHits)),
    ].join('');

    const tbody = document.getElementById('vc-body');
    if (data.entries.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="loading">No cached clips.</td></tr>';
    } else {
      tbody.innerHTML = data.entries.map(e =>
        '<tr>'
        + '<td><button onclick="playCache(\\'' + e.hash + '\\')" '
        + 'style="cursor:pointer;background:none;border:1px solid #ccc;border-radius:4px;'
        + 'padding:0.2rem 0.5rem;font-size:0.8rem">&#9654;</button></td>'
        + '<td>' + truncate(e.text, 50) + '</td>'
        + '<td>' + escapeHtml(e.voice || '-') + '</td>'
        + '<td>' + escapeHtml(e.model || '-') + '</td>'
        + '<td>' + fmt(e.hit_count) + '</td>'
        + '<td>' + fmtBytes(e.size_bytes) + '</td>'
        + '<td>' + fmtTime(e.created_at) + '</td>'
        + '</tr>'
      ).join('');
    }

    document.getElementById('vc-loading').style.display = 'none';
    document.getElementById('vc-content').style.display = '';
  } catch (e) {
    document.getElementById('vc-loading').style.display = 'none';
    const err = document.getElementById('vc-error');
    err.textContent = 'Failed to load voice cache: ' + e.message;
    err.style.display = '';
  }
}

// --- Services Monitor ---
let svcRefreshTimer = null;

async function loadServices() {
  try {
    const data = await fetchJSON('/api/monitor/services');
    if (!data.monitoring_enabled) {
      document.getElementById('svc-loading').style.display = 'none';
      const err = document.getElementById('svc-error');
      err.textContent = 'Service monitoring is disabled. '
        + 'Enable it in Config > Monitor > monitor_enabled.';
      err.style.display = '';
      return;
    }

    const tbody = document.getElementById('svc-body');
    if (data.services.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" class="loading">'
        + 'No services configured. Add one above.</td></tr>';
    } else {
      tbody.innerHTML = data.services.map(s => {
        const isUp = s.is_up === 1;
        const hasResult = s.checked_at != null;
        const statusBadge = !hasResult
          ? '<span style="color:#888">Pending</span>'
          : isUp
            ? '<span style="color:#22c55e;font-weight:700">UP</span>'
            : '<span style="color:#e74c3c;font-weight:700">DOWN</span>';
        const enabledBadge = s.enabled
          ? ''
          : ' <span style="color:#888;font-size:0.75rem">(disabled)</span>';
        const eName = escapeHtml(s.name);
        const eUrl = escapeHtml(s.url);
        return '<tr>'
          + '<td>' + statusBadge + '</td>'
          + '<td class="svc-editable" ondblclick='
          + '"editSvcCell(this,' + s.id + ',\\'name\\')">'
          + eName + enabledBadge + '</td>'
          + '<td class="svc-editable" style="font-size:0.8rem"'
          + ' ondblclick="editSvcCell(this,'
          + s.id + ',\\'url\\')">' + eUrl + '</td>'
          + '<td class="svc-editable" ondblclick='
          + '"editSvcType(this,' + s.id + ',\\''
          + escapeHtml(s.check_type) + '\\')">'
          + escapeHtml(s.check_type) + '</td>'
          + '<td>' + (s.response_time_ms != null
            ? s.response_time_ms.toFixed(0) + 'ms'
            : '-') + '</td>'
          + '<td>' + (s.uptime_pct != null
            ? s.uptime_pct + '%' : '-') + '</td>'
          + '<td>' + fmtTime(s.checked_at) + '</td>'
          + '<td>'
          + '<button onclick="testExistingSvc(\\''
          + eUrl + '\\',\\''
          + escapeHtml(s.check_type) + '\\')"'
          + ' class="svc-act-btn" title="Test"'
          + '>&#9889;</button>'
          + '<button onclick="showSvcHistory('
          + s.id + ',\\'' + eName + '\\')"'
          + ' class="svc-act-btn" title="History"'
          + '>&#128200;</button>'
          + '<button onclick="toggleSvc('
          + s.id + ',' + (s.enabled ? 'false' : 'true')
          + ')" class="svc-act-btn" title="'
          + (s.enabled ? 'Disable' : 'Enable') + '">'
          + (s.enabled ? '&#9724;' : '&#9654;')
          + '</button>'
          + '<button onclick="removeSvc(' + s.id
          + ')" class="svc-del-btn" title="Remove"'
          + '>&#10005;</button>'
          + '</td></tr>';
      }).join('');
    }

    document.getElementById('svc-loading').style.display = 'none';
    document.getElementById('svc-content').style.display = '';

    // Auto-refresh every 60s while on this tab
    if (!svcRefreshTimer) {
      svcRefreshTimer = setInterval(() => {
        const panel = document.getElementById('tab-services');
        if (panel && panel.classList.contains('active')) loadServices();
      }, 60000);
    }
  } catch (e) {
    document.getElementById('svc-loading').style.display = 'none';
    const err = document.getElementById('svc-error');
    err.textContent = 'Failed to load services: ' + e.message;
    err.style.display = '';
  }
}

async function addService() {
  const name = document.getElementById('svc-name').value.trim();
  const url = document.getElementById('svc-url').value.trim();
  const checkType = document.getElementById('svc-type').value;
  const errEl = document.getElementById('svc-add-error');
  errEl.style.display = 'none';

  if (!name || !url) {
    errEl.textContent = 'Name and URL are required.';
    errEl.style.display = '';
    return;
  }

  try {
    const res = await fetch('/api/monitor/services', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name, url, check_type: checkType}),
    });
    const data = await res.json();
    if (!res.ok) {
      errEl.textContent = data.error || 'Failed to add service.';
      errEl.style.display = '';
      return;
    }
    document.getElementById('svc-name').value = '';
    document.getElementById('svc-url').value = '';
    loadServices();
  } catch (e) {
    errEl.textContent = 'Error: ' + e.message;
    errEl.style.display = '';
  }
}

async function testNewService() {
  const url = document.getElementById('svc-url').value.trim();
  const checkType = document.getElementById('svc-type').value;
  const el = document.getElementById('svc-test-result');
  el.style.display = 'none';
  if (!url) {
    el.textContent = 'Enter a URL first.';
    el.style.color = '#e74c3c';
    el.style.display = '';
    return;
  }
  el.textContent = 'Testing...';
  el.style.color = '#888';
  el.style.display = '';
  try {
    const res = await fetch('/api/monitor/test', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url, check_type: checkType}),
    });
    const d = await res.json();
    if (d.is_up) {
      el.style.color = '#22c55e';
      el.textContent = 'Reachable'
        + (d.response_time_ms != null
          ? ' — ' + d.response_time_ms.toFixed(0) + 'ms'
          : '')
        + (d.status_code ? ' (HTTP ' + d.status_code + ')' : '');
    } else {
      el.style.color = '#e74c3c';
      el.textContent = 'Unreachable — '
        + (d.error || 'unknown error');
    }
  } catch (e) {
    el.style.color = '#e74c3c';
    el.textContent = 'Test failed: ' + e.message;
  }
}

async function testExistingSvc(url, checkType) {
  alert(await testSvcInline(url, checkType));
}

async function testSvcInline(url, checkType) {
  try {
    const res = await fetch('/api/monitor/test', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url, check_type: checkType}),
    });
    const d = await res.json();
    if (d.is_up) {
      return 'UP'
        + (d.response_time_ms != null
          ? ' — ' + d.response_time_ms.toFixed(0) + 'ms'
          : '')
        + (d.status_code ? ' (HTTP ' + d.status_code + ')' : '');
    }
    return 'DOWN — ' + (d.error || 'unknown error');
  } catch (e) {
    return 'Test failed: ' + e.message;
  }
}

function editSvcCell(td, id, field) {
  if (td.querySelector('input')) return;
  const orig = td.textContent.replace(/\\(disabled\\)/, '').trim();
  const input = document.createElement('input');
  input.type = 'text';
  input.value = orig;
  input.className = 'svc-edit-input';
  td.textContent = '';
  td.appendChild(input);
  input.focus();
  input.select();

  async function save() {
    const val = input.value.trim();
    if (!val || val === orig) { loadServices(); return; }
    const body = {};
    body[field] = val;
    try {
      await fetch('/api/monitor/services/' + id, {
        method: 'PATCH',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body),
      });
    } catch (e) { /* ignore */ }
    loadServices();
  }
  input.addEventListener('blur', save);
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); save(); }
    if (e.key === 'Escape') loadServices();
  });
}

function editSvcType(td, id, current) {
  if (td.querySelector('select')) return;
  const sel = document.createElement('select');
  sel.className = 'svc-edit-input';
  ['http', 'ping'].forEach(v => {
    const opt = document.createElement('option');
    opt.value = v; opt.textContent = v.toUpperCase();
    if (v === current) opt.selected = true;
    sel.appendChild(opt);
  });
  td.textContent = '';
  td.appendChild(sel);
  sel.focus();

  async function save() {
    const val = sel.value;
    if (val === current) { loadServices(); return; }
    try {
      await fetch('/api/monitor/services/' + id, {
        method: 'PATCH',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({check_type: val}),
      });
    } catch (e) { /* ignore */ }
    loadServices();
  }
  sel.addEventListener('blur', save);
  sel.addEventListener('change', save);
  sel.addEventListener('keydown', e => {
    if (e.key === 'Escape') loadServices();
  });
}

async function removeSvc(id) {
  if (!confirm('Remove this service and all its history?')) return;
  try {
    await fetch('/api/monitor/services/' + id, {method: 'DELETE'});
    loadServices();
  } catch (e) { /* ignore */ }
}

async function toggleSvc(id, enabled) {
  try {
    await fetch('/api/monitor/services/' + id, {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({enabled}),
    });
    loadServices();
  } catch (e) { /* ignore */ }
}

async function showSvcHistory(id, name) {
  document.getElementById('svc-history-title').textContent = name + ' — 30 Day History';
  document.getElementById('svc-history-panel').style.display = '';
  document.getElementById('svc-history-stats').textContent = 'Loading...';

  try {
    const data = await fetchJSON('/api/monitor/services/' + id + '/history?days=30');
    const canvas = document.getElementById('svc-history-canvas');
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = 60 * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, rect.width, 60);

    const checks = data.checks;
    if (checks.length === 0) {
      ctx.fillStyle = '#888';
      ctx.font = '12px sans-serif';
      ctx.fillText('No check history yet.', 10, 35);
      document.getElementById('svc-history-stats').textContent = '';
      return;
    }

    // Draw bar segments
    const w = rect.width;
    const segW = Math.max(1, w / checks.length);
    checks.forEach((c, i) => {
      ctx.fillStyle = c.is_up ? '#22c55e' : '#e74c3c';
      ctx.fillRect(i * segW, 0, Math.ceil(segW), 60);
    });

    const upCount = checks.filter(c => c.is_up).length;
    const pct = (upCount / checks.length * 100).toFixed(2);
    document.getElementById('svc-history-stats').textContent =
      pct + '% uptime over ' + checks.length + ' checks (' + data.days + ' days)';
  } catch (e) {
    document.getElementById('svc-history-stats').textContent = 'Failed to load history.';
  }
}

function closeSvcHistory() {
  document.getElementById('svc-history-panel').style.display = 'none';
}

// --- Tab navigation ---
const loadedTabs = new Set(['tab-overview']);
const TAB_LOADERS = {
  'tab-sessions': () => loadSessions(0),
  'tab-logs': () => { loadLogs(); setupLogAutoRefresh(); },
  'tab-config': () => loadConfig(),
  'tab-voice-cache': () => loadVoiceCache(),
  'tab-services': () => loadServices(),
};

function switchTab(tabId) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));

  const panel = document.getElementById(tabId);
  if (panel) panel.classList.add('active');
  const btn = document.querySelector(`.tab-btn[onclick*="${tabId}"]`);
  if (btn) btn.classList.add('active');

  // Lazy-load on first activation
  if (!loadedTabs.has(tabId) && TAB_LOADERS[tabId]) {
    loadedTabs.add(tabId);
    TAB_LOADERS[tabId]();
  }

  // Pause/resume log auto-refresh
  if (tabId === 'tab-logs') {
    const cb = document.getElementById('log-auto-refresh');
    if (cb.checked && !logAutoRefreshTimer) {
      logAutoRefreshTimer = setInterval(loadLogs, 10000);
    }
  } else if (logAutoRefreshTimer) {
    clearInterval(logAutoRefreshTimer);
    logAutoRefreshTimer = null;
  }

  // Update URL hash without triggering hashchange handler
  history.replaceState(null, '', '#' + tabId);
}

window.addEventListener('hashchange', () => {
  const tabId = location.hash.slice(1);
  if (document.getElementById(tabId)) switchTab(tabId);
});

// Initial load — overview only, then check hash
loadStats();
loadDisplay();
setInterval(loadDisplay, 30000);

const initTab = location.hash.slice(1);
if (initTab && initTab !== 'tab-overview' && document.getElementById(initTab)) {
  switchTab(initTab);
}
</script>
</body>
</html>
"""
