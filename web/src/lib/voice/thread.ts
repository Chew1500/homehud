/**
 * Conversation thread state.
 *
 * The server tracks a rolling LLM context that times out after
 * ``llm_history_ttl`` seconds (default 300). When the server tells us
 * the thread is no longer active — via the ``X-Thread-Active`` header or
 * a ``thread_active`` JSON field — or our local idle timer expires, the
 * NEXT user turn is preceded by a "new conversation" marker in the UI.
 *
 * Kept in a store so both the status pill and the transcript component
 * can react without prop-drilling.
 */

import { writable, get } from 'svelte/store';
import { apiFetch } from '$lib/api/client';
import { config } from '$lib/config';

export interface ThreadState {
  active: boolean;
  /** True once any bubble has been drawn in the current session. */
  hasHistory: boolean;
  /** Next user turn should be prefaced with a divider. */
  pendingDivider: boolean;
}

const initial: ThreadState = {
  active: false,
  hasHistory: false,
  pendingDivider: false,
};

const store = writable<ThreadState>(initial);
let timer: ReturnType<typeof setTimeout> | null = null;

export const threadStore = { subscribe: store.subscribe };

export function markHistory(): void {
  store.update((s) => (s.hasHistory ? s : { ...s, hasHistory: true }));
}

/** Mark the pending divider as consumed (called after it's rendered). */
export function clearPendingDivider(): void {
  store.update((s) => ({ ...s, pendingDivider: false }));
}

export function setThreadActive(active: boolean): void {
  store.update((s) => ({ ...s, active }));

  if (timer) {
    clearTimeout(timer);
    timer = null;
  }

  if (active) {
    timer = setTimeout(expireThread, config.voiceThreadTtlMs);
  }
}

/** Called by the idle timer OR after a manual reset. */
function expireThread(): void {
  store.update((s) => ({
    ...s,
    active: false,
    pendingDivider: s.hasHistory ? true : s.pendingDivider,
  }));
  timer = null;
}

/** Tell the server to drop LLM history; update local state to match. */
export async function resetConversation(): Promise<void> {
  try {
    await apiFetch('/api/conversation/reset', { method: 'POST' });
  } catch {
    /* best-effort — still reset the UI */
  }
  expireThread();
}

export function currentThread(): ThreadState {
  return get(store);
}

/** Test hook — resets timer + state without touching the server. */
export function __resetForTest(): void {
  if (timer) {
    clearTimeout(timer);
    timer = null;
  }
  store.set(initial);
}
