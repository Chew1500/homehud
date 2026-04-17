import { describe, expect, it } from 'vitest';
import type { Exchange } from '../../src/lib/api/sessions';
import {
  computeSegments,
  exchangeWallClock,
  phaseSum,
  prettyRejectionReason,
  unaccountedMs,
} from '../../src/lib/admin/phase';

function mkExchange(overrides: Partial<Exchange> = {}): Exchange {
  return {
    id: 1,
    sequence: 1,
    transcription: null,
    response_text: null,
    routing_path: null,
    matched_feature: null,
    feature_action: null,
    error: null,
    used_vad: false,
    had_bargein: false,
    is_follow_up: false,
    recording_started_at: null,
    recording_ended_at: null,
    stt_started_at: null,
    stt_ended_at: null,
    routing_started_at: null,
    routing_ended_at: null,
    tts_started_at: null,
    tts_ended_at: null,
    playback_started_at: null,
    playback_ended_at: null,
    recording_duration_ms: null,
    stt_duration_ms: null,
    routing_duration_ms: null,
    tts_duration_ms: null,
    playback_duration_ms: null,
    stt_no_speech_prob: null,
    stt_avg_logprob: null,
    llm_calls: [],
    ...overrides,
  };
}

const t = (isoSuffix: string) => `2026-04-16T12:00:${isoSuffix}Z`;

describe('exchangeWallClock', () => {
  it('returns null when no timing data', () => {
    expect(exchangeWallClock(mkExchange())).toBeNull();
  });

  it('is (last end - first start) across all phases', () => {
    const ex = mkExchange({
      recording_started_at: t('00.000'),
      recording_ended_at: t('00.500'),
      stt_started_at: t('00.600'),
      stt_ended_at: t('01.000'),
      playback_started_at: t('01.100'),
      playback_ended_at: t('02.000'),
    });
    expect(exchangeWallClock(ex)).toBe(2_000);
  });
});

describe('computeSegments', () => {
  it('emits ordered phases with gaps between', () => {
    const ex = mkExchange({
      recording_started_at: t('00.000'),
      recording_ended_at: t('00.500'),
      stt_started_at: t('00.600'), // 100ms gap
      stt_ended_at: t('00.800'),
      routing_started_at: t('00.800'), // no gap
      routing_ended_at: t('00.900'),
    });
    const segs = computeSegments(ex);
    expect(segs.map((s) => `${s.kind}:${s.phase}:${s.durationMs}`)).toEqual([
      'phase:recording:500',
      'gap:stt:100',
      'phase:stt:200',
      'phase:routing:100',
    ]);
  });

  it('skips phases missing either timestamp', () => {
    const ex = mkExchange({
      recording_started_at: t('00.000'),
      recording_ended_at: t('00.500'),
      stt_started_at: t('00.600'),
      // stt_ended_at missing → phase skipped
      routing_started_at: t('00.800'),
      routing_ended_at: t('00.900'),
    });
    const segs = computeSegments(ex);
    // Two phases, no gap computed between them (prevEnd skipped to recording end).
    expect(segs.map((s) => s.phase)).toEqual(['recording', 'routing']);
  });
});

describe('phaseSum + unaccountedMs', () => {
  it('sums only phase segments', () => {
    const segs = computeSegments(
      mkExchange({
        recording_started_at: t('00.000'),
        recording_ended_at: t('00.500'),
        stt_started_at: t('00.600'),
        stt_ended_at: t('00.800'),
      }),
    );
    expect(phaseSum(segs)).toBe(700); // 500 + 200 (gap excluded)
  });

  it('unaccounted = wall - (phases + gaps)', () => {
    const ex = mkExchange({
      recording_started_at: t('00.000'),
      recording_ended_at: t('00.500'),
      stt_started_at: t('00.600'),
      stt_ended_at: t('00.800'),
      playback_started_at: t('01.500'),
      playback_ended_at: t('02.000'),
    });
    const wall = exchangeWallClock(ex)!;
    const segs = computeSegments(ex);
    // wall = 2000, segs cover 500+100+200+700+500 = 2000 → unaccounted 0
    expect(unaccountedMs(wall, segs)).toBe(0);
  });
});

describe('prettyRejectionReason', () => {
  it('returns null for non-rejection routes', () => {
    expect(prettyRejectionReason(null)).toBeNull();
    expect(prettyRejectionReason('llm_parse')).toBeNull();
  });
  it('strips prefix and underscores', () => {
    expect(prettyRejectionReason('rejected_stt_low_confidence')).toBe(
      'stt low confidence',
    );
  });
});
