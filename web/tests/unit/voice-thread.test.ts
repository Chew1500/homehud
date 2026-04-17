/**
 * Covers the conversation-thread state that drives the "New conversation"
 * divider and the idle-timeout expiry.
 *
 * The TTL is read at module-load time from config, so we set up the
 * ``#hud-config`` tag before importing.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';

beforeEach(() => {
  document.body.innerHTML = '';
  const cfg = document.createElement('script');
  cfg.id = 'hud-config';
  cfg.type = 'application/json';
  cfg.textContent = JSON.stringify({ voiceThreadTtlMs: 200 });
  document.head.appendChild(cfg);
  vi.resetModules();
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  document.querySelectorAll('#hud-config').forEach((n) => n.remove());
});

describe('voice thread state', () => {
  it('flags pendingDivider when an active thread idles out', async () => {
    const mod = await import('../../src/lib/voice/thread');
    mod.__resetForTest();
    mod.markHistory();
    mod.setThreadActive(true);

    expect(get(mod.threadStore).active).toBe(true);
    expect(get(mod.threadStore).pendingDivider).toBe(false);

    await vi.advanceTimersByTimeAsync(250);

    const s = get(mod.threadStore);
    expect(s.active).toBe(false);
    expect(s.pendingDivider).toBe(true);
  });

  it('does NOT set pendingDivider when no history exists yet', async () => {
    const mod = await import('../../src/lib/voice/thread');
    mod.__resetForTest();
    mod.setThreadActive(true);

    await vi.advanceTimersByTimeAsync(250);

    const s = get(mod.threadStore);
    expect(s.active).toBe(false);
    expect(s.pendingDivider).toBe(false);
  });

  it('clearPendingDivider consumes the flag', async () => {
    const mod = await import('../../src/lib/voice/thread');
    mod.__resetForTest();
    mod.markHistory();
    mod.setThreadActive(true);
    await vi.advanceTimersByTimeAsync(250);
    expect(get(mod.threadStore).pendingDivider).toBe(true);

    mod.clearPendingDivider();
    expect(get(mod.threadStore).pendingDivider).toBe(false);
  });

  it('resetConversation POSTs to /api/conversation/reset and expires thread', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const mod = await import('../../src/lib/voice/thread');
    mod.__resetForTest();
    mod.markHistory();
    mod.setThreadActive(true);

    await mod.resetConversation();

    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/conversation/reset',
      expect.objectContaining({ method: 'POST' }),
    );
    const s = get(mod.threadStore);
    expect(s.active).toBe(false);
    expect(s.pendingDivider).toBe(true);
  });

  it('resetConversation still expires thread on network failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('offline'));

    const mod = await import('../../src/lib/voice/thread');
    mod.__resetForTest();
    mod.markHistory();
    mod.setThreadActive(true);

    await mod.resetConversation();

    const s = get(mod.threadStore);
    expect(s.active).toBe(false);
    expect(s.pendingDivider).toBe(true);
  });
});
