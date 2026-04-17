/**
 * Centralised fetch client.
 *
 *  - Attaches the stored Bearer token automatically
 *  - Throws typed ApiFetchError on non-2xx
 *  - On 401, clears the token and triggers the auth store so route
 *    guards can redirect to /login
 *
 *  The client deliberately does NOT hard-code a redirect itself — that
 *  couples the HTTP layer to routing. Consumers subscribe to the auth
 *  store.
 */

import { ApiFetchError } from './types';

const TOKEN_KEY = 'hud_auth_token';

/** True in a real DOM (browser or jsdom). We deliberately avoid
 *  ``$app/environment.browser`` here: it reports false under vitest,
 *  which would make all library modules no-op in tests. */
const hasDom = typeof window !== 'undefined' && typeof localStorage !== 'undefined';

type AuthListener = (event: 'unauthorized' | 'forbidden') => void;
const listeners = new Set<AuthListener>();

export function onAuthEvent(fn: AuthListener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function getToken(): string | null {
  if (!hasDom) return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (!hasDom) return;
  if (token === null) localStorage.removeItem(TOKEN_KEY);
  else localStorage.setItem(TOKEN_KEY, token);
}

export interface ApiFetchOptions extends Omit<RequestInit, 'body' | 'headers'> {
  /** JSON-serialised and sent as ``application/json``. */
  json?: unknown;
  /** Raw body. Mutually exclusive with ``json``. */
  body?: BodyInit;
  /** Extra headers (merged with auth + content-type). */
  headers?: Record<string, string>;
  /** Skip throwing on 401 — useful for /api/auth/status polling. */
  allowUnauthorized?: boolean;
}

export async function apiFetch<T = unknown>(
  path: string,
  opts: ApiFetchOptions = {},
): Promise<T> {
  const { json, body, headers = {}, allowUnauthorized, ...rest } = opts;
  const token = getToken();
  const finalHeaders: Record<string, string> = { ...headers };
  if (token) finalHeaders['Authorization'] = `Bearer ${token}`;
  let finalBody: BodyInit | undefined = body;
  if (json !== undefined) {
    finalHeaders['Content-Type'] ??= 'application/json';
    finalBody = JSON.stringify(json);
  }
  const res = await fetch(path, { ...rest, body: finalBody, headers: finalHeaders });
  if (res.status === 401 && !allowUnauthorized) {
    setToken(null);
    listeners.forEach((fn) => fn('unauthorized'));
    throw new ApiFetchError(401, await safeJson(res));
  }
  if (res.status === 403) {
    listeners.forEach((fn) => fn('forbidden'));
    throw new ApiFetchError(403, await safeJson(res));
  }
  if (!res.ok) {
    throw new ApiFetchError(res.status, await safeJson(res));
  }
  const contentType = res.headers.get('Content-Type') ?? '';
  if (contentType.includes('application/json')) {
    return (await res.json()) as T;
  }
  return (await res.text()) as unknown as T;
}

async function safeJson(res: Response): Promise<unknown> {
  try {
    return await res.json();
  } catch {
    return null;
  }
}

/**
 * Like ``apiFetch`` but returns the raw ``Response`` so callers can
 * read response headers + body manually. Used for the binary
 * /api/voice endpoint where the response is WAV audio with metadata
 * in X-* headers.
 */
export async function rawFetch(
  path: string,
  opts: Omit<ApiFetchOptions, 'json'> = {},
): Promise<Response> {
  const { body, headers = {}, allowUnauthorized, ...rest } = opts;
  const token = getToken();
  const finalHeaders: Record<string, string> = { ...headers };
  if (token) finalHeaders['Authorization'] = `Bearer ${token}`;
  const res = await fetch(path, { ...rest, body, headers: finalHeaders });
  if (res.status === 401 && !allowUnauthorized) {
    setToken(null);
    listeners.forEach((fn) => fn('unauthorized'));
    throw new ApiFetchError(401, await safeJson(res));
  }
  if (res.status === 403) {
    listeners.forEach((fn) => fn('forbidden'));
    throw new ApiFetchError(403, await safeJson(res));
  }
  if (!res.ok) {
    throw new ApiFetchError(res.status, await safeJson(res));
  }
  return res;
}
