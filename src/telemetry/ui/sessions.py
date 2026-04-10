"""Sessions tab: paginated voice session list with expandable details."""

TAB_HTML = """\
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
"""

TAB_JS = """\
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

        // Response text
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
"""
