/**
 * Phase-timeline math for session exchanges.
 *
 * Each exchange has five sequential phases (recording → STT → routing
 * → TTS → playback). Between them, inter-phase gaps — time the exchange
 * was in-flight but not actively executing a named phase — are worth
 * visualising because that's where scheduling / IO latency lives.
 *
 * The segment model mirrors the classic shell.js implementation.
 */

import type { Exchange } from '$lib/api/sessions';

export const PHASE_ORDER = ['recording', 'stt', 'routing', 'tts', 'playback'] as const;
export type PhaseName = (typeof PHASE_ORDER)[number];

export const PHASE_LABELS: Record<PhaseName, string> = {
  recording: 'Recording',
  stt: 'STT',
  routing: 'Routing',
  tts: 'TTS',
  playback: 'Playback',
};

export type SegmentKind = 'phase' | 'gap';

export interface Segment {
  kind: SegmentKind;
  /** Phase identifier when kind === 'phase', otherwise the phase that FOLLOWS the gap. */
  phase: PhaseName;
  /** Duration in ms (always >= 0). */
  durationMs: number;
}

function tsMs(iso: string | null | undefined): number | null {
  if (!iso) return null;
  // Python may write "+00:00" which Safari used to hate; normalise to Z.
  const normalised = iso.replace('+00:00', 'Z').replace('+0000', 'Z');
  const ms = new Date(normalised).getTime();
  return Number.isFinite(ms) ? ms : null;
}

/** Total wall-clock duration from first phase start to last phase end. */
export function exchangeWallClock(ex: Exchange): number | null {
  let first: number | null = null;
  let last: number | null = null;
  for (const p of PHASE_ORDER) {
    const s = tsMs(ex[`${p}_started_at` as const]);
    const e = tsMs(ex[`${p}_ended_at` as const]);
    if (s != null && (first == null || s < first)) first = s;
    if (e != null && (last == null || e > last)) last = e;
  }
  return first != null && last != null ? last - first : null;
}

/** Phase + gap segments, in execution order. Skips phases with no timing. */
export function computeSegments(ex: Exchange): Segment[] {
  const segs: Segment[] = [];
  let prevEnd: number | null = null;
  for (const p of PHASE_ORDER) {
    const s = tsMs(ex[`${p}_started_at` as const]);
    const e = tsMs(ex[`${p}_ended_at` as const]);
    if (s == null || e == null) continue;
    if (prevEnd != null) {
      const gap = Math.max(0, s - prevEnd);
      if (gap > 0) segs.push({ kind: 'gap', phase: p, durationMs: gap });
    }
    segs.push({ kind: 'phase', phase: p, durationMs: Math.max(0, e - s) });
    prevEnd = e;
  }
  return segs;
}

/** Sum of phase durations (excludes gaps). */
export function phaseSum(segments: Segment[]): number {
  return segments.reduce((a, s) => (s.kind === 'phase' ? a + s.durationMs : a), 0);
}

/** Wall - (phases + gaps) — time nothing was accounted for. */
export function unaccountedMs(
  wallMs: number | null,
  segments: Segment[],
): number | null {
  if (wallMs == null) return null;
  const total = segments.reduce((a, s) => a + s.durationMs, 0);
  return Math.max(0, wallMs - total);
}

/** "rejected_stt_low_confidence" → "stt low confidence". */
export function prettyRejectionReason(routingPath: string | null): string | null {
  if (!routingPath || !routingPath.startsWith('rejected_')) return null;
  return routingPath.replace('rejected_', '').replace(/_/g, ' ');
}
