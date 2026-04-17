/**
 * Runtime config hydrated from the `<script id="hud-config">` tag that the
 * Python server rewrites on every index.html response. Single source of
 * truth for values the SPA needs before its first network call.
 */

export interface RuntimeConfig {
  /** Idle window before a new voice conversation divider appears. */
  voiceThreadTtlMs: number;
  pwaName: string;
  pwaThemeColor: string;
  /** When false, everyone is treated as admin (no login screen). */
  authEnabled: boolean;
  serverTime: number;
}

const DEFAULTS: RuntimeConfig = {
  voiceThreadTtlMs: 300_000,
  pwaName: 'Home HUD',
  pwaThemeColor: '#F39060',
  authEnabled: false,
  serverTime: 0,
};

function readConfig(): RuntimeConfig {
  // Use a typeof-document check rather than $app/environment.browser
  // so this module works identically in vitest (jsdom) and browser.
  if (typeof document === 'undefined') return DEFAULTS;
  const el = document.getElementById('hud-config');
  if (!el?.textContent) return DEFAULTS;
  try {
    return { ...DEFAULTS, ...(JSON.parse(el.textContent) as Partial<RuntimeConfig>) };
  } catch {
    return DEFAULTS;
  }
}

export const config: RuntimeConfig = readConfig();
