/**
 * Telemetry stats + display preview. Admin-only endpoints.
 */

import { apiFetch, rawFetch } from './client';

export interface StatsResponse {
  total_sessions: number;
  total_exchanges: number;
  total_llm_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  error_count: number;
  rejected_count: number;
  sessions_today: number;
  exchanges_today: number;

  avg_recording_ms?: number | null;
  avg_stt_ms?: number | null;
  avg_routing_ms?: number | null;
  avg_tts_ms?: number | null;
  avg_playback_ms?: number | null;
  avg_wall_clock_ms?: number | null;

  avg_rec_to_stt_gap_ms?: number | null;
  avg_stt_to_routing_gap_ms?: number | null;
  avg_routing_to_tts_gap_ms?: number | null;
  avg_tts_to_playback_gap_ms?: number | null;

  feature_counts: Record<string, number>;
  routing_counts: Record<string, number>;
}

export function fetchStats(): Promise<StatsResponse> {
  return apiFetch<StatsResponse>('/api/stats');
}

/** Fetches the current e-ink display snapshot as an object URL.
 *  Returns null when no snapshot is available (404). */
export async function fetchDisplayImageUrl(): Promise<string | null> {
  try {
    const res = await rawFetch('/api/display');
    const blob = await res.blob();
    return URL.createObjectURL(blob);
  } catch {
    return null;
  }
}
