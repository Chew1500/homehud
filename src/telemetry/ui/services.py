"""Services tab: service health monitoring with history visualization."""

TAB_HTML = """\
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
"""

TAB_JS = """\
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
"""
