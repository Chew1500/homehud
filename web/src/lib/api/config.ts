/** Config registry API — reads ``ConfigParam`` metadata + current values. */

import { apiFetch } from './client';

export type ConfigFieldType = 'str' | 'int' | 'float' | 'bool';
export type ConfigSource = 'file' | 'env' | 'default';

export interface ConfigParam {
  key: string;
  value: string | number | boolean | null;
  type: ConfigFieldType;
  group: string;
  description: string;
  default: string | null;
  env_var: string;
  source: ConfigSource;
  sensitive: boolean;
}

export interface ConfigResponse {
  params: ConfigParam[];
  groups: string[];
}

export function fetchConfig(): Promise<ConfigResponse> {
  return apiFetch<ConfigResponse>('/api/config');
}

export interface SaveConfigResponse {
  saved: boolean;
  restart_required: boolean;
  keys: string[];
}

/** The server stores everything as strings; we stringify client-side. */
export function saveConfig(changes: Record<string, string>): Promise<SaveConfigResponse> {
  return apiFetch('/api/config', { method: 'POST', json: changes });
}
