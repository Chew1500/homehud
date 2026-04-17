/**
 * Auth state as a Svelte store. Hydrated on boot from GET /api/auth/status
 * (which is auth-exempt on the server). Tailscale users come back
 * authenticated without a token; everyone else pairs on /login.
 */

import { writable, derived, get } from 'svelte/store';
import { apiFetch, onAuthEvent, setToken } from '$lib/api/client';
import type { AuthStatus, PairResponse } from '$lib/api/types';

export interface AuthState {
  /** True once the first /api/auth/status resolves. */
  initialised: boolean;
  authenticated: boolean;
  userId: string;
  isAdmin: boolean;
}

const initial: AuthState = {
  initialised: false,
  authenticated: false,
  userId: 'anonymous',
  isAdmin: false,
};

export const authStore = writable<AuthState>(initial);

export const isAuthenticated = derived(authStore, (s) => s.authenticated);
export const isAdmin = derived(authStore, (s) => s.isAdmin);

export async function refreshAuth(): Promise<AuthState> {
  try {
    const status = await apiFetch<AuthStatus>('/api/auth/status', {
      allowUnauthorized: true,
    });
    const next: AuthState = {
      initialised: true,
      authenticated: status.authenticated,
      userId: status.user_id,
      isAdmin: status.admin,
    };
    authStore.set(next);
    return next;
  } catch {
    const next: AuthState = { ...initial, initialised: true };
    authStore.set(next);
    return next;
  }
}

export async function pairWithCode(code: string): Promise<void> {
  const res = await apiFetch<PairResponse>('/api/auth/pair', {
    method: 'POST',
    json: { code },
  });
  setToken(res.token);
  authStore.set({
    initialised: true,
    authenticated: true,
    userId: res.user_id,
    isAdmin: res.admin,
  });
}

export function logout(): void {
  setToken(null);
  authStore.set({ ...initial, initialised: true });
}

/** Snapshot without subscribing — use inside route guards. */
export function currentAuth(): AuthState {
  return get(authStore);
}

// When the API client sees a 401, clear auth. Route guards pick up the
// change and redirect to /login.
onAuthEvent((event) => {
  if (event === 'unauthorized') {
    authStore.update((s) => ({ ...s, authenticated: false, isAdmin: false }));
  }
});
