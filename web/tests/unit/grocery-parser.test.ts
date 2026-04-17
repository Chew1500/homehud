import { describe, expect, it } from 'vitest';
import { formatGroceryItem, parseGroceryInput } from '../../src/lib/grocery/parser';

describe('parseGroceryInput', () => {
  it('returns empty name for empty input', () => {
    expect(parseGroceryInput('')).toEqual({ name: '', quantity: null, unit: null });
    expect(parseGroceryInput('   ')).toEqual({ name: '', quantity: null, unit: null });
  });

  it('parses plain names with no quantity', () => {
    expect(parseGroceryInput('milk')).toEqual({ name: 'milk', quantity: null, unit: null });
    expect(parseGroceryInput('Granny Smith apples')).toEqual({
      name: 'Granny Smith apples',
      quantity: null,
      unit: null,
    });
  });

  it('parses integer quantity with unit', () => {
    expect(parseGroceryInput('2 cups flour')).toEqual({
      name: 'flour',
      quantity: 2,
      unit: 'cup',
    });
  });

  it('parses fractional quantity with unit', () => {
    expect(parseGroceryInput('1/2 lb butter')).toEqual({
      name: 'butter',
      quantity: 0.5,
      unit: 'lb',
    });
  });

  it('parses mixed number quantity', () => {
    const parsed = parseGroceryInput('1 1/2 cups sugar');
    expect(parsed.quantity).toBeCloseTo(1.5);
    expect(parsed.unit).toBe('cup');
    expect(parsed.name).toBe('sugar');
  });

  it('canonicalises unit aliases', () => {
    expect(parseGroceryInput('3 tablespoons olive oil').unit).toBe('tbsp');
    expect(parseGroceryInput('500 grams beef').unit).toBe('g');
    expect(parseGroceryInput('2 pounds chicken').unit).toBe('lb');
  });

  it('keeps unrecognised unit words as part of the name', () => {
    // "granny" is not a unit — should stay in the name.
    expect(parseGroceryInput('2 granny smith apples')).toEqual({
      name: 'granny smith apples',
      quantity: 2,
      unit: null,
    });
  });

  it('handles decimal quantities', () => {
    expect(parseGroceryInput('1.5 lb ground beef')).toEqual({
      name: 'ground beef',
      quantity: 1.5,
      unit: 'lb',
    });
  });
});

describe('formatGroceryItem', () => {
  it('renders plain name when no quantity or unit', () => {
    expect(formatGroceryItem({ name: 'milk', quantity: null, unit: null })).toBe('milk');
  });

  it('pluralises name when qty > 1 and no unit', () => {
    expect(formatGroceryItem({ name: 'apple', quantity: 3, unit: null })).toBe('3 apples');
  });

  it('skips pluralisation when name already ends in s', () => {
    expect(formatGroceryItem({ name: 'chips', quantity: 2, unit: null })).toBe('2 chips');
  });

  it('pluralises unit when qty > 1', () => {
    expect(formatGroceryItem({ name: 'flour', quantity: 2, unit: 'cup' })).toBe('2 cups flour');
  });

  it('leaves singular unit at qty = 1', () => {
    expect(formatGroceryItem({ name: 'flour', quantity: 1, unit: 'cup' })).toBe('1 cup flour');
  });

  it('renders common fractions with unicode glyphs', () => {
    expect(formatGroceryItem({ name: 'butter', quantity: 0.5, unit: 'lb' })).toBe('½ lb butter');
    expect(formatGroceryItem({ name: 'sugar', quantity: 1.5, unit: 'cup' })).toBe('1 ½ cups sugar');
  });
});
