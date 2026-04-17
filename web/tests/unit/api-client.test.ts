/**
 * Covers the auth-header injection and 401 handling paths — the pieces
 * most likely to break during refactors.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { apiFetch, onAuthEvent, setToken } from '../../src/lib/api/client';
import { ApiFetchError } from '../../src/lib/api/types';

const jsonResponse = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

describe('apiFetch', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('attaches the Bearer token when one is stored', async () => {
    setToken('tok-abc');
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse(200, { ok: true }));

    await apiFetch('/api/stats');

    const headers = fetchSpy.mock.calls[0]![1]!.headers as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer tok-abc');
  });

  it('omits Authorization when no token', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse(200, { ok: true }));

    await apiFetch('/api/auth/status');

    const headers = fetchSpy.mock.calls[0]![1]!.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
  });

  it('serialises json option and sets content-type', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse(200, { ok: true }));

    await apiFetch('/api/text', { method: 'POST', json: { text: 'hi' } });

    const init = fetchSpy.mock.calls[0]![1]!;
    expect(init.body).toBe('{"text":"hi"}');
    expect((init.headers as Record<string, string>)['Content-Type']).toBe('application/json');
  });

  it('clears token + fires unauthorized event on 401', async () => {
    setToken('tok-dead');
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse(401, { error: 'Unauthorized' }));
    const events: string[] = [];
    const off = onAuthEvent((e) => events.push(e));

    await expect(apiFetch('/api/stats')).rejects.toBeInstanceOf(ApiFetchError);
    expect(localStorage.getItem('hud_auth_token')).toBeNull();
    expect(events).toContain('unauthorized');
    off();
  });

  it('does not clear token when allowUnauthorized is set', async () => {
    setToken('tok-keep');
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse(200, { authenticated: false }));

    const res = await apiFetch('/api/auth/status', { allowUnauthorized: true });

    expect(res).toEqual({ authenticated: false });
    expect(localStorage.getItem('hud_auth_token')).toBe('tok-keep');
  });
});
