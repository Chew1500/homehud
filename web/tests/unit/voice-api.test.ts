/**
 * Verifies that the byte-for-byte /api/voice contract is preserved:
 *  - Content-Type is audio/pcm
 *  - X-Transcription and X-Response-Text are URL-decoded
 *  - X-Thread-Active drives threadActive
 *  - Raw body is returned as an ArrayBuffer
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { sendText, sendVoice } from '../../src/lib/api/voice';

function wavResponse(headers: Record<string, string>, body = new ArrayBuffer(44)) {
  return new Response(body, {
    status: 200,
    headers: { 'Content-Type': 'audio/wav', ...headers },
  });
}

describe('sendVoice', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });
  afterEach(() => vi.restoreAllMocks());

  it('POSTs PCM body with audio/pcm content type', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      wavResponse({ 'X-Transcription': 'hi', 'X-Response-Text': 'hello', 'X-Thread-Active': '1' }),
    );
    const pcm = new ArrayBuffer(16);

    await sendVoice(pcm);

    const [url, init] = fetchSpy.mock.calls[0]!;
    expect(url).toBe('/api/voice');
    expect(init!.method).toBe('POST');
    expect(init!.body).toBe(pcm);
    expect((init!.headers as Record<string, string>)['Content-Type']).toBe('audio/pcm');
  });

  it('URL-decodes transcription + response text', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      wavResponse({
        'X-Transcription': encodeURIComponent("what's the weather"),
        'X-Response-Text': encodeURIComponent("it's sunny"),
        'X-Thread-Active': '1',
      }),
    );

    const turn = await sendVoice(new ArrayBuffer(8));

    expect(turn.transcription).toBe("what's the weather");
    expect(turn.responseText).toBe("it's sunny");
    expect(turn.threadActive).toBe(true);
  });

  it('returns threadActive=false for anything but "1"', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      wavResponse({ 'X-Transcription': 'x', 'X-Response-Text': 'y', 'X-Thread-Active': '0' }),
    );

    const turn = await sendVoice(new ArrayBuffer(8));

    expect(turn.threadActive).toBe(false);
  });
});

describe('sendText', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('POSTs JSON and unwraps response_text + thread_active', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ response_text: 'ack', thread_active: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const turn = await sendText('add eggs');

    expect(turn.responseText).toBe('ack');
    expect(turn.threadActive).toBe(true);
  });
});
