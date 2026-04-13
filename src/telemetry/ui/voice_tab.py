"""Voice tab: browser-based voice + text interface for talking to Home HUD."""

TAB_HTML = """\
<div class="tab-panel active" id="tab-voice">
  <style>
    #tab-voice .voice-container {
      padding-bottom: calc(1.5rem + env(safe-area-inset-bottom, 0px));
    }
    .voice-thread {
      width: 100%;
      display: flex; flex-direction: column; gap: 0.5rem;
      margin-bottom: 1rem;
      max-height: 50vh; overflow-y: auto;
      padding: 0.25rem;
    }
    .voice-thread:empty::before {
      content: "Say something or type below to get started.";
      color: #aaa; font-size: 0.85rem; text-align: center;
      display: block; padding: 1rem 0;
    }
    .voice-bubble {
      max-width: 85%; padding: 0.6rem 0.85rem; border-radius: 14px;
      font-size: 0.95rem; line-height: 1.4; word-break: break-word;
      box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .voice-bubble.user {
      align-self: flex-end;
      background: #3b82f6; color: #fff;
      border-bottom-right-radius: 4px;
    }
    .voice-bubble.assistant {
      align-self: flex-start;
      background: #fff; color: #222;
      border-bottom-left-radius: 4px;
    }
    .voice-bubble .modality {
      display: inline-block; font-size: 0.65rem; opacity: 0.6;
      margin-right: 0.3rem; text-transform: uppercase; font-weight: 600;
      letter-spacing: 0.04em;
    }
    .voice-thread-divider {
      display: flex; align-items: center; gap: 0.5rem;
      color: #aaa; font-size: 0.7rem; text-transform: uppercase;
      font-weight: 600; letter-spacing: 0.05em;
      margin: 0.5rem 0; text-align: center;
    }
    .voice-thread-divider::before,
    .voice-thread-divider::after {
      content: ""; flex: 1; border-top: 1px dashed #ddd;
    }
    .voice-thread-header {
      display: flex; justify-content: space-between; align-items: center;
      width: 100%; margin-bottom: 0.5rem;
      font-size: 0.75rem; color: #888;
    }
    .voice-thread-reset {
      background: none; border: 1px solid #ddd; color: #555;
      padding: 0.3rem 0.7rem; border-radius: 999px; cursor: pointer;
      font-size: 0.72rem; font-weight: 600;
      -webkit-tap-highlight-color: transparent;
    }
    .voice-thread-reset:hover { background: #f5f5f5; }
    .voice-thread-reset:disabled {
      opacity: 0.4; cursor: default;
    }
    .voice-input-row {
      width: 100%; display: flex; gap: 0.5rem; align-items: flex-end;
      margin-top: 0.75rem;
    }
    .voice-input-row textarea {
      flex: 1; resize: none; min-height: 44px; max-height: 120px;
      padding: 0.7rem 0.9rem;
      border: 1px solid #ddd; border-radius: 12px;
      font-size: 1rem; font-family: inherit; line-height: 1.4;
      background: #fff; color: #222;
    }
    .voice-input-row textarea:focus {
      outline: none; border-color: #3b82f6;
    }
    .voice-send-btn {
      height: 44px; padding: 0 1rem; border-radius: 12px;
      background: #3b82f6; color: #fff; border: none;
      font-size: 0.9rem; font-weight: 600; cursor: pointer;
      -webkit-tap-highlight-color: transparent;
    }
    .voice-send-btn:disabled {
      background: #c7d2fe; cursor: default;
    }
    @media (max-width: 600px) {
      .voice-thread { max-height: 40vh; }
    }
  </style>

  <div class="voice-container">
    <div class="voice-status" id="voice-status">Tap to talk</div>

    <div class="voice-btn-wrap">
      <div class="voice-level-ring" id="voice-level-ring"></div>
      <button class="voice-btn" id="voice-btn"
        ontouchstart="voiceBtnDown(event)" ontouchend="voiceBtnUp(event)"
        onmousedown="voiceBtnDown(event)" onmouseup="voiceBtnUp(event)">
        <svg viewBox="0 0 24 24" width="52" height="52"
          fill="currentColor">
          <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3
            S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
          <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5
            c0 3.53 2.61 6.43 6 6.92V21h2v-3.08
            c3.39-.49 6-3.39 6-6.92h-2z"/>
        </svg>
      </button>
    </div>

    <div class="voice-thread-header">
      <span id="voice-thread-state">No active conversation</span>
      <button class="voice-thread-reset" id="voice-thread-reset"
        onclick="resetVoiceConversation()" disabled>New conversation</button>
    </div>

    <div class="voice-thread" id="voice-thread"></div>

    <div class="voice-input-row">
      <textarea id="voice-text-input" rows="1" placeholder="Type a message..."
        onkeydown="voiceTextKeydown(event)" oninput="voiceTextAutosize(this)"></textarea>
      <button class="voice-send-btn" id="voice-send-btn"
        onclick="sendVoiceText()">Send</button>
    </div>

    <div class="voice-hint" id="voice-hint">
      Hold the button to record, release to send. Or tap once to start,
      tap again to stop. Type and hit Enter to message instead.
      <br><span style="color:#bbb">Microphone requires HTTPS or localhost.</span>
    </div>
  </div>
</div>
"""

TAB_JS = r"""
// --- Voice tab ---
let voiceState = 'idle'; // idle | listening | processing | playing
let voiceAudioCtx = null;
let voiceWorklet = null;
let voiceMediaStream = null;
let voiceSourceNode = null;
let voiceHoldTimer = null;
let voiceTapMode = false; // true = tap-to-toggle, false = push-to-talk

// Conversation thread state. TTL matches the server-side llm_history_ttl
// default (300s); when the thread expires (via idle timer, manual reset,
// or a server response saying thread_active=false), the *next* user turn
// is preceded by a "New conversation" divider.
const VOICE_THREAD_TTL_MS = 300000;
let voiceThread = {
  active: false,
  hasHistory: false,     // any bubble ever been drawn?
  pendingDivider: false, // next appended user bubble should be prefaced
};
let voiceThreadTimer = null;

function updateVoiceUI(state, statusText) {
  voiceState = state;
  const btn = document.getElementById('voice-btn');
  const status = document.getElementById('voice-status');
  const ring = document.getElementById('voice-level-ring');

  status.textContent = statusText || {
    idle: 'Tap to talk',
    listening: 'Listening...',
    processing: 'Processing...',
    playing: 'Playing response...'
  }[state];

  btn.className = 'voice-btn voice-' + state;
  if (state !== 'listening') {
    ring.style.transform = 'scale(1)';
    ring.style.opacity = '0';
  }
}

function voiceEscape(s) {
  const div = document.createElement('div');
  div.textContent = s == null ? '' : String(s);
  return div.innerHTML;
}

function appendVoiceBubble(role, modality, text) {
  const thread = document.getElementById('voice-thread');
  if (!thread) return;

  // A pending divider is drawn just before the first user bubble of the
  // new thread — never before an assistant bubble (which belongs to the
  // same turn as the preceding user bubble).
  if (voiceThread.pendingDivider && role === 'user') {
    const div = document.createElement('div');
    div.className = 'voice-thread-divider';
    div.textContent = 'New conversation';
    thread.appendChild(div);
    voiceThread.pendingDivider = false;
  }

  const bubble = document.createElement('div');
  bubble.className = 'voice-bubble ' + role;
  bubble.innerHTML = '<span class="modality">' + voiceEscape(modality)
    + '</span>' + voiceEscape(text || '(empty)');
  thread.appendChild(bubble);
  thread.scrollTop = thread.scrollHeight;
  voiceThread.hasHistory = true;
}

function setVoiceThreadActive(active) {
  voiceThread.active = !!active;
  const label = document.getElementById('voice-thread-state');
  const btn = document.getElementById('voice-thread-reset');
  if (label) {
    label.textContent = active
      ? 'Conversation active'
      : 'No active conversation';
  }
  if (btn) btn.disabled = !active;

  if (voiceThreadTimer) { clearTimeout(voiceThreadTimer); voiceThreadTimer = null; }
  if (active) {
    voiceThreadTimer = setTimeout(() => {
      // Idle timeout — next turn starts a new thread.
      voiceThread.active = false;
      if (voiceThread.hasHistory) voiceThread.pendingDivider = true;
      if (label) label.textContent = 'No active conversation';
      if (btn) btn.disabled = true;
    }, VOICE_THREAD_TTL_MS);
  }
}

async function resetVoiceConversation() {
  try {
    await fetch('/api/conversation/reset', { method: 'POST' });
  } catch (err) {
    console.warn('Reset failed:', err);
  }
  if (voiceThread.hasHistory) voiceThread.pendingDivider = true;
  setVoiceThreadActive(false);
}

async function initVoiceAudio() {
  if (voiceAudioCtx) return;
  voiceAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
  await voiceAudioCtx.audioWorklet.addModule('/audio-processor.js');
}

async function startRecording() {
  if (voiceState === 'listening') return;
  try {
    await initVoiceAudio();
    voiceMediaStream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true }
    });
    voiceSourceNode = voiceAudioCtx.createMediaStreamSource(voiceMediaStream);
    voiceWorklet = new AudioWorkletNode(voiceAudioCtx, 'audio-capture-processor');

    voiceWorklet.port.onmessage = (e) => {
      if (e.data.type === 'level') {
        const ring = document.getElementById('voice-level-ring');
        const scale = 1 + Math.min(e.data.rms * 8, 0.5);
        ring.style.transform = 'scale(' + scale + ')';
        ring.style.opacity = Math.min(e.data.rms * 10, 0.6).toString();
      } else if (e.data.type === 'audio') {
        sendVoiceAudio(e.data.samples);
      }
    };

    voiceSourceNode.connect(voiceWorklet);
    voiceWorklet.connect(voiceAudioCtx.destination); // required for processing
    voiceWorklet.port.postMessage({ command: 'start' });
    updateVoiceUI('listening');
  } catch (err) {
    console.error('Mic access error:', err);
    const isInsecure = location.protocol !== 'https:'
      && location.hostname !== 'localhost'
      && location.hostname !== '127.0.0.1';
    if (isInsecure) {
      updateVoiceUI('idle',
        'Microphone requires HTTPS. Set up Tailscale for remote access, '
        + 'or use localhost.');
    } else if (err.name === 'NotAllowedError') {
      updateVoiceUI('idle', 'Microphone permission denied. Check browser settings.');
    } else {
      updateVoiceUI('idle', 'Microphone error: ' + err.message);
    }
  }
}

function stopRecording() {
  if (voiceState !== 'listening') return;
  if (voiceWorklet) {
    voiceWorklet.port.postMessage({ command: 'stop' });
  }
  // Clean up after a short delay to allow the worklet to send final audio
  setTimeout(() => {
    if (voiceSourceNode) { voiceSourceNode.disconnect(); voiceSourceNode = null; }
    if (voiceWorklet) { voiceWorklet.disconnect(); voiceWorklet = null; }
    if (voiceMediaStream) {
      voiceMediaStream.getTracks().forEach(t => t.stop());
      voiceMediaStream = null;
    }
  }, 100);
  updateVoiceUI('processing');
}

async function sendVoiceAudio(arrayBuffer) {
  updateVoiceUI('processing');

  try {
    const res = await fetch('/api/voice', {
      method: 'POST',
      headers: { 'Content-Type': 'audio/pcm' },
      body: arrayBuffer,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || 'HTTP ' + res.status);
    }

    const transcription = decodeURIComponent(res.headers.get('X-Transcription') || '');
    const responseText = decodeURIComponent(res.headers.get('X-Response-Text') || '');
    const threadActive = res.headers.get('X-Thread-Active') === '1';

    appendVoiceBubble('user', 'voice', transcription);
    appendVoiceBubble('assistant', 'voice', responseText);
    setVoiceThreadActive(threadActive);

    // Play response audio
    const audioData = await res.arrayBuffer();
    if (audioData.byteLength > 44) {
      updateVoiceUI('playing');
      await playVoiceResponse(audioData);
    }
    updateVoiceUI('idle');
  } catch (err) {
    console.error('Voice request failed:', err);
    updateVoiceUI('idle', 'Error: ' + err.message);
  }
}

async function sendVoiceText() {
  const input = document.getElementById('voice-text-input');
  const sendBtn = document.getElementById('voice-send-btn');
  if (!input) return;
  const text = (input.value || '').trim();
  if (!text) return;
  if (voiceState === 'processing' || voiceState === 'playing') return;

  input.value = '';
  voiceTextAutosize(input);
  sendBtn.disabled = true;
  updateVoiceUI('processing');

  // Draw the user bubble immediately for responsive feedback.
  appendVoiceBubble('user', 'text', text);

  try {
    const res = await fetch('/api/text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || 'HTTP ' + res.status);

    appendVoiceBubble('assistant', 'text', data.response_text || '');
    setVoiceThreadActive(!!data.thread_active);
    updateVoiceUI('idle');
  } catch (err) {
    console.error('Text request failed:', err);
    appendVoiceBubble('assistant', 'text', 'Error: ' + err.message);
    updateVoiceUI('idle', 'Error: ' + err.message);
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

function voiceTextKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendVoiceText();
  }
}

function voiceTextAutosize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

async function playVoiceResponse(wavBuffer) {
  try {
    if (!voiceAudioCtx) await initVoiceAudio();
    const audioBuffer = await voiceAudioCtx.decodeAudioData(wavBuffer);
    const source = voiceAudioCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(voiceAudioCtx.destination);
    return new Promise(resolve => {
      source.onended = resolve;
      source.start();
    });
  } catch (err) {
    console.error('Playback error:', err);
  }
}

function voiceBtnDown(e) {
  e.preventDefault();
  if (voiceState === 'processing' || voiceState === 'playing') return;

  if (voiceState === 'listening' && voiceTapMode) {
    // Second tap in tap mode: stop recording
    voiceTapMode = false;
    stopRecording();
    return;
  }

  // Start a hold timer — if released quickly, treat as tap-to-toggle
  voiceTapMode = false;
  voiceHoldTimer = setTimeout(() => {
    voiceHoldTimer = null;
    voiceTapMode = false;
  }, 300);
  startRecording();
}

function voiceBtnUp(e) {
  e.preventDefault();
  if (voiceState !== 'listening') return;

  if (voiceHoldTimer) {
    // Released before 300ms — tap mode
    clearTimeout(voiceHoldTimer);
    voiceHoldTimer = null;
    voiceTapMode = true;
    // Don't stop — user will tap again to stop
    return;
  }

  // Push-to-talk release
  stopRecording();
}

function loadVoice() {
  // No initial data to load — just make sure UI is ready
  updateVoiceUI('idle');
  setVoiceThreadActive(false);
}
"""
