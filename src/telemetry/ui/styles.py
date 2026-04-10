"""Dashboard CSS styles."""

DASHBOARD_STYLES = """\
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

/* Garden */
.garden-table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; }
.garden-table th, .garden-table td {
  padding: 0.4rem 0.75rem; text-align: right; border-bottom: 1px solid #eee;
  font-size: 0.85rem;
}
.garden-table th { text-align: right; color: #888; font-size: 0.75rem;
  text-transform: uppercase; }
.garden-table th:first-child, .garden-table td:first-child { text-align: left; }
.garden-table tfoot td { font-weight: 700; border-top: 2px solid #333; }
.garden-zone {
  display: flex; align-items: center; gap: 1rem; padding: 0.75rem;
  border-radius: 8px; margin-bottom: 0.5rem; background: #f8f9fa;
}
.garden-zone .zone-name { font-weight: 600; min-width: 140px; }
.garden-zone .zone-bar {
  flex: 1; height: 24px; background: #e5e7eb; border-radius: 4px;
  overflow: hidden; position: relative;
}
.garden-zone .zone-fill {
  height: 100%; border-radius: 4px; transition: width 0.3s;
}
.garden-zone .zone-label {
  font-size: 0.8rem; color: #555; min-width: 180px; text-align: right;
}
.urgency-ok .zone-fill { background: #22c55e; }
.urgency-monitor .zone-fill { background: #f59e0b; }
.urgency-water_today .zone-fill { background: #ef4444; }
.urgency-urgent .zone-fill { background: #dc2626; }
.garden-badge {
  display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px;
  font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
  min-width: 80px; text-align: center;
}
.badge-ok { background: #dcfce7; color: #166534; }
.badge-monitor { background: #fef3c7; color: #92400e; }
.badge-water_today { background: #fee2e2; color: #991b1b; }
.badge-urgent { background: #fca5a5; color: #7f1d1d; }
.garden-net-pos { color: #22c55e; }
.garden-net-neg { color: #ef4444; }
.garden-watering-empty { color: #888; font-style: italic; padding: 0.5rem 0; }

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

/* Voice tab */
.voice-container {
  display: flex; flex-direction: column; align-items: center;
  padding: 2rem 1rem; max-width: 400px; margin: 0 auto;
}
.voice-status {
  font-size: 1.1rem; color: #555; margin-bottom: 1.5rem;
  font-weight: 500; text-align: center; min-height: 1.5em;
}
.voice-btn-wrap {
  position: relative; width: 120px; height: 120px;
  margin-bottom: 2rem;
}
.voice-level-ring {
  position: absolute; inset: -8px; border-radius: 50%;
  background: rgba(59, 130, 246, 0.15);
  transform: scale(1); opacity: 0;
  transition: transform 0.05s, opacity 0.1s;
  pointer-events: none;
}
.voice-btn {
  width: 120px; height: 120px; border-radius: 50%;
  border: none; cursor: pointer;
  background: #3b82f6; color: #fff;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 15px rgba(59,130,246,0.3);
  transition: background 0.2s, transform 0.1s, box-shadow 0.2s;
  -webkit-tap-highlight-color: transparent;
  touch-action: none; user-select: none;
}
.voice-btn:active, .voice-btn.voice-listening {
  background: #ef4444; transform: scale(0.95);
  box-shadow: 0 4px 15px rgba(239,68,68,0.3);
}
.voice-btn.voice-processing {
  background: #f59e0b; cursor: wait;
  animation: voice-pulse 1.2s infinite;
}
.voice-btn.voice-playing {
  background: #22c55e; cursor: default;
  animation: voice-pulse 1.5s infinite;
}
@keyframes voice-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}
.voice-transcript, .voice-response {
  width: 100%; background: #fff; border-radius: 8px; padding: 0.75rem 1rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 0.75rem;
}
.voice-label {
  font-size: 0.7rem; color: #888; text-transform: uppercase;
  font-weight: 600; margin-bottom: 0.25rem;
}
.voice-text {
  font-size: 0.9rem; color: #333; line-height: 1.4;
  word-break: break-word;
}
.voice-hint {
  font-size: 0.8rem; color: #aaa; text-align: center;
  margin-top: 0.5rem; line-height: 1.5;
}

/* Responsive */
@media (max-width: 600px) {
  body { padding: 0.5rem; }
  .cards { grid-template-columns: repeat(2, 1fr); }
  td, th { padding: 0.35rem 0.5rem; font-size: 0.8rem; }
  .tab-btn { padding: 0.5rem 0.75rem; font-size: 0.8rem; }
}
"""
