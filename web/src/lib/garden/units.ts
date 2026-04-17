/** Utility conversions used by the Garden UI. */

export const MM_PER_INCH = 25.4;

export function mmToInches(mm: number): number {
  return mm / MM_PER_INCH;
}

export function formatInches(value: number, digits = 2): string {
  return `${value.toFixed(digits)}"`;
}

/** Short, relative date label — "Today", "Yesterday", or "Mar 5". */
export function friendlyDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const now = new Date();
  const midnight = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate());
  const days = Math.round(
    (midnight(d).getTime() - midnight(now).getTime()) / 86_400_000,
  );
  if (days === 0) return 'Today';
  if (days === -1) return 'Yesterday';
  if (days === 1) return 'Tomorrow';
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}
