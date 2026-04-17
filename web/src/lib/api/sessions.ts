/**
 * Sessions API.
 *
 * List endpoint returns paginated summary rows; detail endpoint
 * returns the full session with per-exchange timing and LLM calls.
 * Admin-only on the server — the store's `apiFetch` inherits the
 * Bearer-token auth flow.
 */

import { apiFetch } from './client';

export interface SessionSummary {
  id: string;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  exchange_count: number;
  wake_model: string | null;
  first_transcription: string | null;
  features_used: string[];
  had_error: boolean;
}

export interface SessionListResponse {
  sessions: SessionSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface LlmCall {
  call_type: string;
  model: string | null;
  system_prompt: string | null;
  user_message: string | null;
  response_text: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  stop_reason: string | null;
  duration_ms: number | null;
  error: string | null;
}

export interface Exchange {
  id: number;
  sequence: number;
  transcription: string | null;
  response_text: string | null;
  routing_path: string | null;
  matched_feature: string | null;
  feature_action: string | null;
  error: string | null;
  used_vad: boolean;
  had_bargein: boolean;
  is_follow_up: boolean;

  recording_started_at: string | null;
  recording_ended_at: string | null;
  stt_started_at: string | null;
  stt_ended_at: string | null;
  routing_started_at: string | null;
  routing_ended_at: string | null;
  tts_started_at: string | null;
  tts_ended_at: string | null;
  playback_started_at: string | null;
  playback_ended_at: string | null;

  recording_duration_ms: number | null;
  stt_duration_ms: number | null;
  routing_duration_ms: number | null;
  tts_duration_ms: number | null;
  playback_duration_ms: number | null;

  stt_no_speech_prob: number | null;
  stt_avg_logprob: number | null;

  llm_calls: LlmCall[];
}

export interface SessionDetail {
  session: {
    id: string;
    started_at: string;
    ended_at: string | null;
    exchange_count: number;
    wake_model: string | null;
  };
  exchanges: Exchange[];
}

export function fetchSessions(limit: number, offset: number): Promise<SessionListResponse> {
  const qs = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return apiFetch<SessionListResponse>(`/api/sessions?${qs.toString()}`);
}

export function fetchSessionDetail(id: string): Promise<SessionDetail> {
  return apiFetch<SessionDetail>(`/api/sessions/${encodeURIComponent(id)}`);
}
