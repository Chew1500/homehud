import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { fmtInt, fmtMs, fmtPct, fmtRelative, fmtTime } from '../../src/lib/admin/format';

describe('fmtInt', () => {
  it('returns em-dash for null/undefined', () => {
    expect(fmtInt(null)).toBe('—');
    expect(fmtInt(undefined)).toBe('—');
  });
  it('uses locale string for small numbers', () => {
    expect(fmtInt(0)).toBe('0');
    expect(fmtInt(1234)).toMatch(/1,?234/);
  });
  it('abbreviates at 10k and above', () => {
    expect(fmtInt(9999)).toMatch(/9,?999/);
    expect(fmtInt(10_500)).toBe('10.5k');
    expect(fmtInt(1_200_000)).toBe('1.2M');
  });
});

describe('fmtMs', () => {
  it('formats sub-second as ms', () => {
    expect(fmtMs(123)).toBe('123 ms');
    expect(fmtMs(999)).toBe('999 ms');
  });
  it('formats >= 1s as seconds with 2 decimals', () => {
    expect(fmtMs(1_000)).toBe('1.00 s');
    expect(fmtMs(1_234)).toBe('1.23 s');
  });
  it('returns em-dash for null', () => {
    expect(fmtMs(null)).toBe('—');
  });
});

describe('fmtPct', () => {
  it('returns 0% when total is zero', () => {
    expect(fmtPct(5, 0)).toBe('0%');
  });
  it('rounds to whole percent', () => {
    expect(fmtPct(1, 3)).toBe('33%');
    expect(fmtPct(2, 3)).toBe('67%');
  });
});

describe('fmtRelative', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-16T12:00:00Z'));
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('uses "just now" under a minute', () => {
    expect(fmtRelative('2026-04-16T11:59:30Z')).toBe('just now');
  });
  it('uses minutes under an hour', () => {
    expect(fmtRelative('2026-04-16T11:55:00Z')).toBe('5m ago');
  });
  it('uses hours under a day', () => {
    expect(fmtRelative('2026-04-16T08:00:00Z')).toBe('4h ago');
  });
  it('uses days under a week', () => {
    expect(fmtRelative('2026-04-14T12:00:00Z')).toBe('2d ago');
  });
  it('falls back to short date for older stamps', () => {
    const out = fmtRelative('2026-03-01T12:00:00Z');
    expect(out).toMatch(/Mar/);
  });
});

describe('fmtTime', () => {
  it('returns em-dash for null', () => {
    expect(fmtTime(null)).toBe('—');
  });
  it('returns the input for unparsable strings', () => {
    expect(fmtTime('not a date')).toBe('not a date');
  });
});
