/**
 * Audio capture: owns AudioContext + MediaStream + AudioWorklet.
 *
 * The worklet itself is the byte-for-byte copy of the classic UI's
 * processor at ``web/static/audio-processor.js`` (served at root).
 * Everything else — lifecycle, permissions, RMS fan-out — lives here.
 *
 * Exposes two paths back to consumers:
 *   - ``onLevel(rms)``  for the ring visualisation
 *   - ``onAudio(buf)`` for the final PCM int16 buffer
 */

import { setVoiceRms } from './state-machine';

type LevelHandler = (rms: number) => void;
type AudioHandler = (pcm: ArrayBuffer) => void;

export interface CaptureHandle {
  stop(): void;
}

interface WorkletMessage {
  type: 'level' | 'audio';
  rms?: number;
  samples?: ArrayBuffer;
}

let audioCtx: AudioContext | null = null;
let worklet: AudioWorkletNode | null = null;
let mediaStream: MediaStream | null = null;
let sourceNode: MediaStreamAudioSourceNode | null = null;

async function ensureContext(): Promise<AudioContext> {
  if (audioCtx) return audioCtx;
  const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
  const ctx = new Ctx();
  await ctx.audioWorklet.addModule('/audio-processor.js');
  audioCtx = ctx;
  return ctx;
}

/** Return the shared AudioContext, creating it if needed. Consumers that
 *  need the context for playback call this so we don't double-instantiate. */
export function getAudioContext(): Promise<AudioContext> {
  return ensureContext();
}

export class MicPermissionError extends Error {
  readonly code: 'insecure' | 'denied' | 'unsupported' | 'unknown';
  constructor(code: MicPermissionError['code'], message: string) {
    super(message);
    this.code = code;
    this.name = 'MicPermissionError';
  }
}

function diagnosePermissionError(err: unknown): MicPermissionError {
  if (
    typeof location !== 'undefined' &&
    location.protocol !== 'https:' &&
    location.hostname !== 'localhost' &&
    location.hostname !== '127.0.0.1'
  ) {
    return new MicPermissionError(
      'insecure',
      'Microphone requires HTTPS. Use Tailscale for remote access, or localhost.',
    );
  }
  if (err instanceof DOMException) {
    if (err.name === 'NotAllowedError' || err.name === 'SecurityError') {
      return new MicPermissionError(
        'denied',
        'Microphone permission denied. Check browser settings.',
      );
    }
    if (err.name === 'NotFoundError') {
      return new MicPermissionError(
        'unsupported',
        'No microphone found on this device.',
      );
    }
  }
  const msg = err instanceof Error ? err.message : String(err);
  return new MicPermissionError('unknown', `Microphone error: ${msg}`);
}

export async function startCapture(onAudio: AudioHandler, onLevel?: LevelHandler): Promise<CaptureHandle> {
  let ctx: AudioContext;
  try {
    ctx = await ensureContext();
  } catch (err) {
    throw diagnosePermissionError(err);
  }

  let stream: MediaStream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
    });
  } catch (err) {
    throw diagnosePermissionError(err);
  }

  const source = ctx.createMediaStreamSource(stream);
  const node = new AudioWorkletNode(ctx, 'audio-capture-processor');

  node.port.onmessage = (ev: MessageEvent<WorkletMessage>) => {
    const data = ev.data;
    if (data.type === 'level' && typeof data.rms === 'number') {
      setVoiceRms(data.rms);
      onLevel?.(data.rms);
    } else if (data.type === 'audio' && data.samples) {
      onAudio(data.samples);
    }
  };

  source.connect(node);
  // AudioWorklet only processes while connected to a destination. The
  // worklet itself doesn't emit audio, so nothing is actually heard.
  node.connect(ctx.destination);
  node.port.postMessage({ command: 'start' });

  mediaStream = stream;
  sourceNode = source;
  worklet = node;

  return {
    stop: () => {
      if (!worklet || !sourceNode || !mediaStream) return;
      // Ask the worklet to flush its buffer; it posts the final 'audio'
      // message on its own timeline, so cleanup is deferred slightly to
      // avoid tearing down the node before the message arrives.
      worklet.port.postMessage({ command: 'stop' });
      const toStop = { worklet, sourceNode, mediaStream };
      worklet = null;
      sourceNode = null;
      mediaStream = null;
      setTimeout(() => {
        toStop.sourceNode.disconnect();
        toStop.worklet.disconnect();
        toStop.mediaStream.getTracks().forEach((t) => t.stop());
      }, 120);
    },
  };
}
