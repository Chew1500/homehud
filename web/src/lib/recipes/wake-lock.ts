/**
 * Thin wrapper around the Screen Wake Lock API for Cook Mode.
 *
 * Browsers drop wake locks when the tab becomes hidden; we re-acquire
 * on ``visibilitychange`` so returning from another tab restores the
 * locked-on state. The API isn't supported everywhere (older iOS
 * Safari in particular), so all calls fail silently.
 */

type WakeLock = { release: () => Promise<void> };

interface WakeLockState {
  locked: boolean;
  supported: boolean;
}

import { writable } from 'svelte/store';

const state = writable<WakeLockState>({
  locked: false,
  supported: typeof navigator !== 'undefined' && 'wakeLock' in navigator,
});

export const wakeLockState = { subscribe: state.subscribe };

let current: WakeLock | null = null;
let visibilityHandler: (() => void) | null = null;

async function acquire(): Promise<void> {
  if (current) return;
  if (typeof navigator === 'undefined' || !('wakeLock' in navigator)) return;
  try {
    const wl = await (
      navigator as Navigator & {
        wakeLock: { request: (type: 'screen') => Promise<WakeLock> };
      }
    ).wakeLock.request('screen');
    current = wl;
    state.update((s) => ({ ...s, locked: true }));
  } catch {
    /* lost or unavailable — fail silently */
  }
}

export async function enableWakeLock(): Promise<void> {
  await acquire();
  if (!visibilityHandler) {
    visibilityHandler = () => {
      if (document.visibilityState === 'visible' && !current) {
        void acquire();
      }
    };
    document.addEventListener('visibilitychange', visibilityHandler);
  }
}

export async function disableWakeLock(): Promise<void> {
  if (visibilityHandler) {
    document.removeEventListener('visibilitychange', visibilityHandler);
    visibilityHandler = null;
  }
  if (current) {
    try {
      await current.release();
    } catch {
      /* no-op */
    }
    current = null;
  }
  state.update((s) => ({ ...s, locked: false }));
}
