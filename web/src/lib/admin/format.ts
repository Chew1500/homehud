/**
 * Small formatters shared across admin pages. Keeping them in one
 * place lets later admin tabs (Sessions, Logs) use the same output
 * style without duplication.
 */

/** Compact integer — "1,234" or "12.3k" when > 10_000. */
export function fmtInt(n: number | null | undefined): string {
  if (n == null) return '—';
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 10_000) return `${(n / 1_000).toFixed(1)}k`;
  return n.toLocaleString();
}

/** Milliseconds → "123 ms" / "1.23 s" / "—" when null. */
export function fmtMs(ms: number | null | undefined): string {
  if (ms == null) return '—';
  const rounded = Math.round(ms);
  if (rounded < 1_000) return `${rounded} ms`;
  return `${(rounded / 1_000).toFixed(2)} s`;
}

/** Percentage of a total, 0 decimal places. */
export function fmtPct(part: number, total: number): string {
  if (!total) return '0%';
  return `${Math.round((part / total) * 100)}%`;
}

/** ISO timestamp → short local time (e.g., "14:32:06"). */
export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString();
}

/** ISO timestamp → compact relative ("2m ago", "3h ago", "Mar 5"). */
export function fmtRelative(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const diffSec = (Date.now() - d.getTime()) / 1000;
  if (diffSec < 60) return 'just now';
  if (diffSec < 3_600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86_400) return `${Math.floor(diffSec / 3_600)}h ago`;
  if (diffSec < 7 * 86_400) return `${Math.floor(diffSec / 86_400)}d ago`;
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}
