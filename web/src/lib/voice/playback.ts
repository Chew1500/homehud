/**
 * Playback of WAV responses from POST /api/voice.
 *
 * Shares the AudioContext with the capture module so mobile browsers
 * don't count two separate user-gesture-authorised contexts. Resolves
 * when playback ends so the caller can transition back to ``idle``.
 */

import { getAudioContext } from './audio-capture';

/** Headers + raw PCM = 44 bytes; anything at or below that is an empty WAV. */
export const MIN_WAV_BYTES = 44;

export async function playWav(wav: ArrayBuffer): Promise<void> {
  if (wav.byteLength <= MIN_WAV_BYTES) return;
  const ctx = await getAudioContext();
  const buffer = await ctx.decodeAudioData(wav.slice(0));
  const source = ctx.createBufferSource();
  source.buffer = buffer;
  source.connect(ctx.destination);
  await new Promise<void>((resolve) => {
    source.onended = () => resolve();
    source.start();
  });
}
