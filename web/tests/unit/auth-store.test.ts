import { beforeEach, describe, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';

import { authStore, logout, pairWithCode, refreshAuth } from '../../src/lib/auth/store';
import { setToken } from '../../src/lib/api/client';

const jsonResponse = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

describe('authStore', () => {
  beforeEach(() => {
    localStorage.clear();
    authStore.set({
      initialised: false,
      authenticated: false,
      userId: 'anonymous',
      isAdmin: false,
    });
    vi.restoreAllMocks();
  });

  it('hydrates from /api/auth/status', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      jsonResponse(200, { authenticated: true, user_id: 'tailscale:alice', admin: true }),
    );

    const state = await refreshAuth();

    expect(state.authenticated).toBe(true);
    expect(state.isAdmin).toBe(true);
    expect(state.userId).toBe('tailscale:alice');
    expect(get(authStore).initialised).toBe(true);
  });

  it('stores token on successful pairing', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      jsonResponse(200, { token: 'new-token', user_id: 'u1', admin: false }),
    );

    await pairWithCode('123456');

    expect(localStorage.getItem('hud_auth_token')).toBe('new-token');
    expect(get(authStore).authenticated).toBe(true);
  });

  it('clears token on logout', () => {
    setToken('abc');
    logout();
    expect(localStorage.getItem('hud_auth_token')).toBeNull();
    expect(get(authStore).authenticated).toBe(false);
  });
});
