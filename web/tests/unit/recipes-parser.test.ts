import { describe, expect, it } from 'vitest';
import {
  displayIngredient,
  formatIngredientLine,
  parseIngredientLine,
} from '../../src/lib/recipes/parser';

describe('parseIngredientLine', () => {
  it('returns null for blank lines', () => {
    expect(parseIngredientLine('')).toBeNull();
    expect(parseIngredientLine('   ')).toBeNull();
  });

  it('parses "qty unit name"', () => {
    expect(parseIngredientLine('2 cups flour')).toEqual({
      quantity: '2',
      unit: 'cups',
      name: 'flour',
    });
  });

  it('parses fractions', () => {
    expect(parseIngredientLine('1/2 tsp salt')).toEqual({
      quantity: '1/2',
      unit: 'tsp',
      name: 'salt',
    });
  });

  it('parses ranges', () => {
    expect(parseIngredientLine('1-2 cloves garlic')).toEqual({
      quantity: '1-2',
      unit: 'cloves',
      name: 'garlic',
    });
  });

  it('parses "qty name" with no unit', () => {
    expect(parseIngredientLine('3 eggs')).toEqual({
      quantity: '3',
      unit: '',
      name: 'eggs',
    });
  });

  it('falls back to name-only for plain text', () => {
    expect(parseIngredientLine('salt to taste')).toEqual({
      quantity: '',
      unit: '',
      name: 'salt to taste',
    });
  });
});

describe('formatIngredientLine / displayIngredient', () => {
  it('omits empty fields', () => {
    expect(formatIngredientLine({ quantity: '', unit: '', name: 'salt' })).toBe('salt');
    expect(formatIngredientLine({ quantity: '3', unit: '', name: 'eggs' })).toBe('3 eggs');
    expect(formatIngredientLine({ quantity: '2', unit: 'cups', name: 'flour' })).toBe(
      '2 cups flour',
    );
  });

  it('round-trips parse → format', () => {
    const cases = ['2 cups flour', '1/2 tsp salt', '3 eggs', 'salt to taste'];
    for (const line of cases) {
      const parsed = parseIngredientLine(line);
      if (parsed) {
        expect(displayIngredient(parsed)).toBe(line);
      }
    }
  });
});
