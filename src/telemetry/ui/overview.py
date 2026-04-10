"""Overview tab: summary cards, phase performance, display preview."""

TAB_HTML = """\
<div class="tab-panel" id="tab-overview">
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
"""

TAB_JS = """\
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
          + 'font-style:italic"><td>&nbsp;&nbsp;\\u2192 gap</td>'
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
"""
