"""Voice Cache tab: TTS cache management and playback."""

TAB_HTML = """\
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
"""

TAB_JS = """\
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
"""
