import { beforeEach, describe, expect, it } from 'vitest';
import { get } from 'svelte/store';

import {
  currentVoiceState,
  resetVoiceStatus,
  setVoiceError,
  setVoiceRms,
  setVoiceState,
  voiceStatus,
} from '../../src/lib/voice/state-machine';

describe('voice state machine', () => {
  beforeEach(() => {
    resetVoiceStatus();
  });

  it('starts idle with no RMS or error', () => {
    const s = get(voiceStatus);
    expect(s.state).toBe('idle');
    expect(s.rms).toBe(0);
    expect(s.error).toBeNull();
  });

  it('transitions through listening → processing → playing → idle', () => {
    setVoiceState('listening');
    expect(currentVoiceState()).toBe('listening');

    setVoiceRms(0.5);
    expect(get(voiceStatus).rms).toBe(0.5);

    setVoiceState('processing');
    // RMS clears when leaving listening
    expect(get(voiceStatus).rms).toBe(0);

    setVoiceState('playing');
    expect(currentVoiceState()).toBe('playing');

    setVoiceState('idle');
    expect(currentVoiceState()).toBe('idle');
  });

  it('ignores RMS updates outside of listening', () => {
    setVoiceState('processing');
    setVoiceRms(0.9);
    expect(get(voiceStatus).rms).toBe(0);
  });

  it('setVoiceError forces idle + surfaces message', () => {
    setVoiceState('listening');
    setVoiceError('mic denied');
    const s = get(voiceStatus);
    expect(s.state).toBe('idle');
    expect(s.error).toBe('mic denied');
    expect(s.message).toBe('mic denied');
    expect(s.rms).toBe(0);
  });

  it('uses the optional override message', () => {
    setVoiceState('listening', 'Go ahead');
    expect(get(voiceStatus).message).toBe('Go ahead');
  });
});
