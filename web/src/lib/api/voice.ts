/**
 * Voice API — thin typed wrappers over POST /api/voice and /api/text.
 *
 * The voice endpoint is unusual: it accepts raw PCM int16 @ 16kHz and
 * returns a WAV audio body with the user transcription + assistant
 * response text in X-* headers. We preserve that contract exactly.
 */

import { apiFetch, rawFetch } from './client';

export interface VoiceTurn {
  transcription: string;
  responseText: string;
  threadActive: boolean;
  /** WAV audio response. ``byteLength <= 44`` means empty (no TTS). */
  wav: ArrayBuffer;
}

export async function sendVoice(pcm: ArrayBuffer): Promise<VoiceTurn> {
  const res = await rawFetch('/api/voice', {
    method: 'POST',
    headers: { 'Content-Type': 'audio/pcm' },
    body: pcm,
  });
  const transcription = decodeURIComponent(res.headers.get('X-Transcription') ?? '');
  const responseText = decodeURIComponent(res.headers.get('X-Response-Text') ?? '');
  const threadActive = res.headers.get('X-Thread-Active') === '1';
  const wav = await res.arrayBuffer();
  return { transcription, responseText, threadActive, wav };
}

export interface TextTurn {
  responseText: string;
  threadActive: boolean;
}

interface TextResponse {
  response_text?: string;
  thread_active?: boolean;
}

export async function sendText(text: string): Promise<TextTurn> {
  const data = await apiFetch<TextResponse>('/api/text', {
    method: 'POST',
    json: { text },
  });
  return {
    responseText: data.response_text ?? '',
    threadActive: Boolean(data.thread_active),
  };
}
