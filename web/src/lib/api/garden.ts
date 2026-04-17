/**
 * Garden API. Read-only — the backend computes zone deficits, weather,
 * and watering logs; the UI just renders them.
 */

import { apiFetch } from './client';

export type ZoneUrgency = 'ok' | 'monitor' | 'water_today' | 'urgent';

export interface Zone {
  label: string;
  urgency: ZoneUrgency;
  pct_of_threshold: number;
  deficit_inches: number;
  threshold_inches: number;
  days_since_rain: number | null;
  days_since_watered: number | null;
  forecast_rain_inches: number;
}

export interface HistoryDay {
  date: string;
  precipitation_mm: number;
  et0_mm: number;
  temp_max_f: number;
}

export interface ForecastDay extends HistoryDay {
  precipitation_probability: number;
}

export interface WateringEvent {
  timestamp: string;
  zone: string;
  amount_inches: number;
}

export interface GardenState {
  enabled: boolean;
  zones: Zone[];
  history: HistoryDay[];
  forecast: ForecastDay[];
  watering_events: WateringEvent[];
}

export function fetchGarden(): Promise<GardenState> {
  return apiFetch<GardenState>('/api/garden');
}
