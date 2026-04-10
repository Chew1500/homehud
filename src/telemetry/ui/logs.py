"""Logs tab: real-time color-coded log viewer with level filtering."""

TAB_HTML = """\
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
"""

TAB_JS = """\
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
"""
