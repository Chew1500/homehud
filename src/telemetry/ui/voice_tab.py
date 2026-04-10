"""Voice tab: browser-based voice interface for talking to Home HUD."""

TAB_HTML = """\
<div class="tab-panel active" id="tab-voice">
  <div class="voice-container">
    <div class="voice-status" id="voice-status">Tap to talk</div>

    <div class="voice-btn-wrap">
      <div class="voice-level-ring" id="voice-level-ring"></div>
      <button class="voice-btn" id="voice-btn"
        ontouchstart="voiceBtnDown(event)" ontouchend="voiceBtnUp(event)"
        onmousedown="voiceBtnDown(event)" onmouseup="voiceBtnUp(event)">
        <svg viewBox="0 0 24 24" width="48" height="48"
          fill="currentColor">
          <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3
            S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
          <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5
            c0 3.53 2.61 6.43 6 6.92V21h2v-3.08
            c3.39-.49 6-3.39 6-6.92h-2z"/>
        </svg>
      </button>
    </div>

    <div class="voice-transcript" id="voice-transcript">
      <div class="voice-label">You said:</div>
      <div class="voice-text" id="voice-user-text">-</div>
    </div>

    <div class="voice-response" id="voice-response">
      <div class="voice-label">Response:</div>
      <div class="voice-text" id="voice-response-text">-</div>
    </div>

    <div class="voice-hint" id="voice-hint">
      Hold the button to record, release to send.
      <br>Or tap once to start, tap again to stop.
      <br><span style="color:#bbb">Microphone requires HTTPS or localhost.</span>
    </div>
  </div>
</div>
"""

TAB_JS = """\
// --- Voice tab ---
let voiceState = 'idle'; // idle | listening | processing | playing
let voiceAudioCtx = null;
let voiceWorklet = null;
let voiceMediaStream = null;
let voiceSourceNode = null;
let voiceHoldTimer = null;
let voiceTapMode = false; // true = tap-to-toggle, false = push-to-talk

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
  document.getElementById('voice-user-text').textContent = '...';
  document.getElementById('voice-response-text').textContent = '...';

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
    document.getElementById('voice-user-text').textContent = transcription || '(empty)';
    document.getElementById('voice-response-text').textContent = responseText || '(empty)';

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
}
"""
