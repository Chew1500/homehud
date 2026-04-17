/** Logs API — tails the homehud.log file with optional level filter. */

import { apiFetch } from './client';

export type LogLevel = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';

export interface LogEntry {
  timestamp: string;
  level: LogLevel;
  logger: string;
  message: string;
}

export interface LogsResponse {
  lines: LogEntry[];
  total_lines: number;
  log_file: string;
  filters: { level: string | null; limit: number };
}

export function fetchLogs(params: { lines?: number; level?: string | null }): Promise<LogsResponse> {
  const qs = new URLSearchParams();
  qs.set('lines', String(params.lines ?? 200));
  if (params.level) qs.set('level', params.level);
  return apiFetch<LogsResponse>(`/api/logs?${qs.toString()}`);
}
