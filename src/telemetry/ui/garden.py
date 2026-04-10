"""Garden tab: watering zone status, water balance history, and forecast."""

TAB_HTML = """\
<div class="tab-panel" id="tab-garden">
  <div id="garden-loading" class="loading">Loading garden data...</div>
  <div id="garden-error" class="error-msg" style="display:none"></div>
  <div id="garden-content" style="display:none">
    <div id="garden-disabled" style="display:none">
      <p style="color:#888">Garden watering advisory is not enabled.
      Set <code>garden_enabled = true</code> in Config to activate.</p>
    </div>
    <div id="garden-active" style="display:none">
      <h2>Zone Status</h2>
      <div id="garden-zones"></div>

      <h2 style="margin-top:1.5rem">Water Balance (7-day history)</h2>
      <table class="garden-table" id="garden-history-table">
        <thead>
          <tr>
            <th>Date</th><th>Rain (mm)</th><th>ET&#8320; (mm)</th>
            <th>Net (mm)</th><th>Temp (&deg;F)</th>
          </tr>
        </thead>
        <tbody id="garden-history-body"></tbody>
        <tfoot id="garden-history-foot"></tfoot>
      </table>

      <h2 style="margin-top:1.5rem">Forecast</h2>
      <table class="garden-table" id="garden-forecast-table">
        <thead>
          <tr>
            <th>Date</th><th>Rain (mm)</th><th>Prob</th>
            <th>ET&#8320; (mm)</th><th>Temp (&deg;F)</th>
          </tr>
        </thead>
        <tbody id="garden-forecast-body"></tbody>
      </table>

      <h2 style="margin-top:1.5rem">Watering Log (14 days)</h2>
      <div id="garden-watering-log"></div>
    </div>
  </div>
</div>
"""

TAB_JS = """\
// --- Garden ---

async function loadGarden() {
  const loading = document.getElementById('garden-loading');
  const error = document.getElementById('garden-error');
  const content = document.getElementById('garden-content');

  try {
    loading.style.display = '';
    error.style.display = 'none';

    const data = await fetchJSON('/api/garden');

    if (!data.enabled) {
      document.getElementById('garden-disabled').style.display = '';
      document.getElementById('garden-active').style.display = 'none';
      loading.style.display = 'none';
      content.style.display = '';
      return;
    }

    document.getElementById('garden-disabled').style.display = 'none';
    document.getElementById('garden-active').style.display = '';

    // Zone status bars
    const zonesEl = document.getElementById('garden-zones');
    if (data.zones.length === 0) {
      zonesEl.innerHTML = '<p style="color:#888">No zone data available.</p>';
    } else {
      zonesEl.innerHTML = data.zones.map(z => {
        const pct = Math.min(z.pct_of_threshold, 200);
        const barPct = Math.min(pct, 100);
        const badgeCls = 'badge-' + z.urgency;
        const urgencyLabel = z.urgency.replace('_', ' ');
        let detail = `Deficit: ${z.deficit_inches.toFixed(2)}" / `
          + `${z.threshold_inches.toFixed(2)}" threshold`;
        if (z.days_since_rain !== null)
          detail += ` \\u2022 Rain: ${z.days_since_rain}d ago`;
        if (z.days_since_watered !== null)
          detail += ` \\u2022 Watered: ${z.days_since_watered}d ago`;
        return `<div class="garden-zone urgency-${z.urgency}">
          <span class="zone-name">${z.label}</span>
          <div class="zone-bar">
            <div class="zone-fill" style="width:${barPct}%"></div>
          </div>
          <span class="garden-badge ${badgeCls}">${urgencyLabel}</span>
          <span class="zone-label">${detail}</span>
        </div>`;
      }).join('');
    }

    // Forecast rain summary
    if (data.zones.length > 0) {
      const fr = data.zones[0].forecast_rain_inches;
      if (fr > 0) {
        zonesEl.innerHTML += `<p style="font-size:0.85rem;color:#555;margin-top:0.5rem">`
          + `Expected rain (3-day forecast): ${fr.toFixed(2)}"</p>`;
      }
    }

    // History table
    const histBody = document.getElementById('garden-history-body');
    const histFoot = document.getElementById('garden-history-foot');
    let totalRain = 0, totalEt = 0;
    histBody.innerHTML = (data.history || []).map(d => {
      const net = d.precipitation_mm - d.et0_mm;
      totalRain += d.precipitation_mm;
      totalEt += d.et0_mm;
      const netCls = net >= 0 ? 'garden-net-pos' : 'garden-net-neg';
      return `<tr>
        <td>${d.date}</td>
        <td>${d.precipitation_mm.toFixed(1)}</td>
        <td>${d.et0_mm.toFixed(1)}</td>
        <td class="${netCls}">${net >= 0 ? '+' : ''}${net.toFixed(1)}</td>
        <td>${d.temp_max_f.toFixed(0)}</td>
      </tr>`;
    }).join('');
    const totalNet = totalRain - totalEt;
    const totalNetCls = totalNet >= 0 ? 'garden-net-pos' : 'garden-net-neg';
    histFoot.innerHTML = `<tr>
      <td>Total</td>
      <td>${totalRain.toFixed(1)}</td>
      <td>${totalEt.toFixed(1)}</td>
      <td class="${totalNetCls}">${totalNet >= 0 ? '+' : ''}${totalNet.toFixed(1)}</td>
      <td></td>
    </tr>`;

    // Forecast table
    const fcBody = document.getElementById('garden-forecast-body');
    fcBody.innerHTML = (data.forecast || []).map(d => {
      return `<tr>
        <td>${d.date}</td>
        <td>${d.precipitation_mm.toFixed(1)}</td>
        <td>${d.precipitation_probability}%</td>
        <td>${d.et0_mm.toFixed(1)}</td>
        <td>${d.temp_max_f.toFixed(0)}</td>
      </tr>`;
    }).join('');

    // Watering log
    const logEl = document.getElementById('garden-watering-log');
    if (!data.watering_events || data.watering_events.length === 0) {
      logEl.innerHTML = '<p class="garden-watering-empty">No watering events recorded.</p>';
    } else {
      logEl.innerHTML = '<table class="garden-table"><thead><tr>'
        + '<th>Date</th><th>Zone</th><th>Amount</th></tr></thead><tbody>'
        + data.watering_events.map(e => {
          const ts = e.timestamp.slice(0, 16).replace('T', ' ');
          return `<tr><td>${ts}</td><td>${e.zone}</td>`
            + `<td>${e.amount_inches.toFixed(2)}"</td></tr>`;
        }).join('')
        + '</tbody></table>';
    }

    loading.style.display = 'none';
    content.style.display = '';
  } catch (e) {
    error.textContent = 'Error: ' + e.message;
    error.style.display = '';
    loading.style.display = 'none';
  }
}
"""
