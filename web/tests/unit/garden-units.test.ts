import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { formatInches, friendlyDate, mmToInches } from '../../src/lib/garden/units';

describe('mmToInches / formatInches', () => {
  it('converts and formats', () => {
    expect(mmToInches(25.4)).toBeCloseTo(1);
    expect(formatInches(1)).toBe('1.00"');
    expect(formatInches(0.125, 3)).toBe('0.125"');
  });
});

describe('friendlyDate', () => {
  beforeEach(() => {
    // Pin wall clock to 2026-04-16 at local noon so relative labels
    // are deterministic across CI and laptop time zones.
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-16T12:00:00'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('labels today / yesterday / tomorrow', () => {
    expect(friendlyDate('2026-04-16')).toBe('Today');
    expect(friendlyDate('2026-04-15')).toBe('Yesterday');
    expect(friendlyDate('2026-04-17')).toBe('Tomorrow');
  });

  it('returns a short month-day for other dates', () => {
    const out = friendlyDate('2026-04-10');
    expect(out).toMatch(/Apr\s*10/);
  });

  it('returns the input as-is if unparsable', () => {
    expect(friendlyDate('not a date')).toBe('not a date');
  });
});
