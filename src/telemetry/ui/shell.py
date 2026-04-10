"""Outer HTML shell: head, tab bar, common JS utilities, tab navigation."""

TAB_BAR = """\
<div class="tab-bar">
  <button class="tab-btn active" onclick="switchTab('tab-overview')">Overview</button>
  <button class="tab-btn" onclick="switchTab('tab-sessions')">Sessions</button>
  <button class="tab-btn" onclick="switchTab('tab-logs')">Logs</button>
  <button class="tab-btn" onclick="switchTab('tab-config')">Config</button>
  <button class="tab-btn" onclick="switchTab('tab-voice-cache')">Voice Cache</button>
  <button class="tab-btn" onclick="switchTab('tab-services')">Services</button>
  <button class="tab-btn" onclick="switchTab('tab-garden')">Garden</button>
  <button class="tab-btn" onclick="switchTab('tab-voice')">Voice</button>
</div>
"""

COMMON_JS = """\
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
    const name = isGap ? '&nbsp;&nbsp;\\u2192 gap' : PHASE_LABELS[seg.name] || seg.name;
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
"""

TAB_NAV_JS = """\
// --- Tab navigation ---
const loadedTabs = new Set(['tab-overview']);
const TAB_LOADERS = {
  'tab-sessions': () => loadSessions(0),
  'tab-logs': () => { loadLogs(); setupLogAutoRefresh(); },
  'tab-config': () => loadConfig(),
  'tab-voice-cache': () => loadVoiceCache(),
  'tab-services': () => loadServices(),
  'tab-garden': () => loadGarden(),
  'tab-voice': () => loadVoice(),
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

// --- Auth ---
async function checkAuth() {
  const token = localStorage.getItem('hud_auth_token');
  if (!token) return false;
  try {
    const res = await fetch('/api/auth/status', {
      headers: { 'Authorization': 'Bearer ' + token }
    });
    return res.ok;
  } catch (e) { return false; }
}

function showLoginScreen() {
  document.getElementById('hud-main').style.display = 'none';
  document.getElementById('hud-login').style.display = '';
}

function showMainScreen() {
  document.getElementById('hud-login').style.display = 'none';
  document.getElementById('hud-main').style.display = '';
}

async function submitPairingCode() {
  const code = document.getElementById('pair-code-input').value.trim();
  const errEl = document.getElementById('pair-error');
  errEl.style.display = 'none';
  if (!code) return;

  try {
    const res = await fetch('/api/auth/pair', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code }),
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      errEl.textContent = data.error || 'Pairing failed';
      errEl.style.display = '';
      return;
    }
    localStorage.setItem('hud_auth_token', data.token);
    localStorage.setItem('hud_user_id', data.user_id);
    location.reload();
  } catch (e) {
    errEl.textContent = 'Network error: ' + e.message;
    errEl.style.display = '';
  }
}

function hudLogout() {
  localStorage.removeItem('hud_auth_token');
  localStorage.removeItem('hud_user_id');
  location.reload();
}

// Inject auth token into all fetch calls when available
const _origFetch = window.fetch;
window.fetch = function(url, opts) {
  const token = localStorage.getItem('hud_auth_token');
  if (token) {
    opts = opts || {};
    opts.headers = opts.headers || {};
    if (typeof opts.headers === 'object' && !opts.headers['Authorization']) {
      opts.headers['Authorization'] = 'Bearer ' + token;
    }
  }
  return _origFetch.call(this, url, opts);
};

// Initial load
(async function init() {
  // Check if auth is required by testing /api/auth/status without token
  const testRes = await _origFetch('/api/auth/status').catch(() => null);
  const authRequired = testRes && testRes.status === 401;

  if (authRequired) {
    const authed = await checkAuth();
    if (!authed) { showLoginScreen(); return; }
  }
  showMainScreen();
  loadStats();
  loadDisplay();
  setInterval(loadDisplay, 30000);

  const initTab = location.hash.slice(1);
  if (initTab && initTab !== 'tab-overview'
      && document.getElementById(initTab)) {
    switchTab(initTab);
  }
})();
"""
