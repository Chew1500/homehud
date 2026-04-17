/**
 * Voice UI state machine.
 *
 * Mirrors the four-state model from the classic voice tab:
 *
 *   idle       → nothing happening, mic closed
 *   listening  → mic open, worklet capturing PCM + RMS
 *   processing → buffer posted to /api/voice (or /api/text), awaiting reply
 *   playing    → WAV response decoded, audio playing
 *
 * Kept as a Svelte writable rather than xstate: the transitions are
 * shallow and linear, and using a plain store keeps the component side
 * trivial.
 */

import { writable, get, derived } from 'svelte/store';

export type VoiceState = 'idle' | 'listening' | 'processing' | 'playing';

export interface VoiceStatus {
  state: VoiceState;
  /** Optional human-facing override; otherwise components pick a default. */
  message: string | null;
  /** Latest mic RMS (0..1), only meaningful while listening. */
  rms: number;
  /** Last error message shown to the user (cleared on next transition). */
  error: string | null;
}

const initial: VoiceStatus = {
  state: 'idle',
  message: null,
  rms: 0,
  error: null,
};

const status = writable<VoiceStatus>(initial);

export const voiceStatus = { subscribe: status.subscribe };
export const voiceState = derived(status, (s) => s.state);

/** Transition to a new state; clears RMS unless staying in listening. */
export function setVoiceState(state: VoiceState, message: string | null = null): void {
  status.update((s) => ({
    state,
    message,
    rms: state === 'listening' ? s.rms : 0,
    error: null,
  }));
}

export function setVoiceRms(rms: number): void {
  status.update((s) => (s.state === 'listening' ? { ...s, rms } : s));
}

export function setVoiceError(error: string): void {
  status.update((s) => ({ ...s, state: 'idle', rms: 0, error, message: error }));
}

export function currentVoiceState(): VoiceState {
  return get(status).state;
}

export function resetVoiceStatus(): void {
  status.set(initial);
}
