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

/* Loading / error */
.loading { text-align: center; padding: 2rem; color: #888; }
.error-msg { text-align: center; padding: 1rem; color: #e74c3c; background: #fee2e2;
  border-radius: 8px; margin: 1rem 0; }

/* Responsive */
@media (max-width: 600px) {
  body { padding: 0.5rem; }
  .cards { grid-template-columns: repeat(2, 1fr); }
  td, th { padding: 0.35rem 0.5rem; font-size: 0.8rem; }
}
</style>
</head>
<body>
<h1>Home HUD Telemetry</h1>
<p class="subtitle">Voice pipeline performance and usage data</p>

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

<h2>Application Logs</h2>
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

<h2>Sessions</h2>
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
function fmtMs(v) { return v != null ? Math.round(v).toLocaleString() : '-'; }
function fmtPct(n, total) { return total ? (n / total * 100).toFixed(1) + '%' : '0%'; }

function fmtTime(iso) {
  if (!iso) return '-';
  const d = new Date(iso);
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString();
}

function fmtDuration(ms) {
  if (ms == null) return '-';
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

    // Performance table
    const phases = ['recording', 'stt', 'routing', 'tts', 'playback'];
    const tbody = document.querySelector('#perf-table tbody');
    let totalAvg = 0;
    let totalCount = 0;
    tbody.innerHTML = phases.map(p => {
      const v = data['avg_' + p + '_ms'];
      if (v != null) { totalAvg += v; totalCount++; }
      return `<tr><td>${p}</td><td>${fmtMs(v)}</td></tr>`;
    }).join('');
    tbody.innerHTML += `<tr><td><strong>Total (sum of avgs)</strong></td>`
      + `<td><strong>${totalCount ? fmtMs(totalAvg) : '-'}</strong></td></tr>`;

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
      html += '<table><thead><tr>'
        + '<th>#</th><th>Transcription</th><th>Response</th><th>Route</th>'
        + '<th>Rec</th><th>STT</th><th>Route</th><th>TTS</th><th>Play</th><th>Flags</th>'
        + '</tr></thead><tbody>';

      data.exchanges.forEach((ex, i) => {
        let flags = '';
        if (ex.used_vad) flags += '<span class="flag flag-vad">VAD</span>';
        if (ex.had_bargein) flags += '<span class="flag flag-bargein">BARGE</span>';
        if (ex.is_follow_up) flags += '<span class="flag flag-followup">FOLLOW</span>';
        if (ex.error) flags += '<span class="flag flag-error">ERR</span>';
        if (ex.routing_path && ex.routing_path.startsWith('rejected_'))
          flags += '<span class="flag flag-rejected">REJ</span>';

        html += `<tr class="exchange-row" data-exid="${ex.id}">`
          + `<td>${ex.sequence}</td>`
          + `<td>${truncate(ex.transcription, 30)}</td>`
          + `<td>${truncate(ex.response_text, 30)}</td>`
          + `<td>${ex.routing_path || '-'}`
          + `${ex.matched_feature ? ' > ' + ex.matched_feature : ''}</td>`
          + `<td>${fmtMs(ex.recording_duration_ms)}</td>`
          + `<td>${fmtMs(ex.stt_duration_ms)}</td>`
          + `<td>${fmtMs(ex.routing_duration_ms)}</td>`
          + `<td>${fmtMs(ex.tts_duration_ms)}</td>`
          + `<td>${fmtMs(ex.playback_duration_ms)}</td>`
          + `<td>${flags || '-'}</td></tr>`;

        // Exchange detail row (LLM calls)
        html += `<tr class="exchange-detail" data-exdetail="${ex.id}"><td colspan="10">`
          + `<div class="exchange-detail-inner">`;

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

document.getElementById('log-level-filter').addEventListener('change', loadLogs);

// Initial load
loadStats();
loadSessions(0);
loadDisplay();
loadLogs();
setupLogAutoRefresh();
setInterval(loadDisplay, 30000);
</script>
</body>
</html>
"""
