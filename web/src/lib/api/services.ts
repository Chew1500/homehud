/** Service-monitoring API (http/ping uptime checks). Admin-only. */

import { apiFetch } from './client';

export type CheckType = 'http' | 'ping';

export interface MonitoredService {
  id: number;
  name: string;
  url: string;
  check_type: CheckType;
  enabled: boolean;
  /** 0 or 1 in the classic payload; normalised client-side as needed. */
  is_up: number | null;
  response_time_ms: number | null;
  status_code: number | null;
  error: string | null;
  checked_at: string | null;
  uptime_pct: number | null;
}

export interface MonitorListResponse {
  services: MonitoredService[];
  monitoring_enabled: boolean;
}

export function fetchServices(): Promise<MonitorListResponse> {
  return apiFetch<MonitorListResponse>('/api/monitor/services');
}

export interface HistoryCheck {
  checked_at: string;
  is_up: number;
  response_time_ms: number | null;
  status_code: number | null;
  error: string | null;
}

export interface HistoryResponse {
  service_id: number;
  days: number;
  checks: HistoryCheck[];
}

export function fetchServiceHistory(id: number, days = 30): Promise<HistoryResponse> {
  return apiFetch<HistoryResponse>(
    `/api/monitor/services/${id}/history?days=${days}`,
  );
}

export interface TestResult {
  is_up: boolean;
  response_time_ms: number | null;
  status_code: number | null;
  error: string | null;
}

export function testService(url: string, checkType: CheckType): Promise<TestResult> {
  return apiFetch('/api/monitor/test', {
    method: 'POST',
    json: { url, check_type: checkType },
  });
}

export interface AddServiceResponse {
  id: number;
  name: string;
  url: string;
}

export function addService(
  name: string,
  url: string,
  checkType: CheckType,
): Promise<AddServiceResponse> {
  return apiFetch('/api/monitor/services', {
    method: 'POST',
    json: { name, url, check_type: checkType },
  });
}

export type ServicePatch = Partial<{
  name: string;
  url: string;
  check_type: CheckType;
  enabled: boolean;
}>;

export function updateService(id: number, patch: ServicePatch): Promise<{ ok: true }> {
  return apiFetch(`/api/monitor/services/${id}`, { method: 'PATCH', json: patch });
}

export function deleteService(id: number): Promise<{ ok: true }> {
  return apiFetch(`/api/monitor/services/${id}`, { method: 'DELETE' });
}
