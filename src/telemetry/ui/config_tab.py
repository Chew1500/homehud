"""Config tab: live editable configuration with dirty state tracking."""

TAB_HTML = """\
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
"""

TAB_JS = """\
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
"""
