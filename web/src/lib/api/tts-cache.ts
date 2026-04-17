/** TTS cache inspection + audio streaming URLs. */

import { apiFetch } from './client';

export interface TtsCacheEntry {
  hash: string;
  text: string;
  voice: string;
  model: string;
  created_at: string;
  hit_count: number;
  size_bytes: number;
}

export interface TtsCacheResponse {
  entries: TtsCacheEntry[];
  total_entries: number;
  total_size_bytes: number;
}

export function fetchTtsCache(): Promise<TtsCacheResponse> {
  return apiFetch<TtsCacheResponse>('/api/tts-cache');
}

export function ttsCacheAudioUrl(hash: string): string {
  return `/api/tts-cache/${encodeURIComponent(hash)}/audio`;
}
