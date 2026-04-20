import { describe, expect, it } from 'vitest';
import type { Recipe } from '../../src/lib/api/recipes';
import { formatRecipeForShare } from '../../src/lib/recipes/share';

const full: Recipe = {
  id: 'r1',
  name: 'Miso-Glazed Salmon',
  tags: ['dinner', 'seafood'],
  prep_time_min: 10,
  cook_time_min: 15,
  servings: 2,
  ingredients: [
    { quantity: '2', unit: '', name: 'salmon fillets' },
    { quantity: '2', unit: 'tbsp', name: 'white miso' },
  ],
  directions: ['Heat oven to 400°F.', 'Brush glaze onto salmon, bake 12–15 min.'],
  source: 'https://example.com/miso-salmon',
};

describe('formatRecipeForShare', () => {
  it('renders a fully-populated recipe', () => {
    expect(formatRecipeForShare(full)).toBe(
      [
        'Miso-Glazed Salmon',
        '',
        'Prep: 10 min \u00b7 Cook: 15 min \u00b7 Serves: 2',
        'Tags: dinner, seafood',
        '',
        'INGREDIENTS',
        '- 2 salmon fillets',
        '- 2 tbsp white miso',
        '',
        'DIRECTIONS',
        '1. Heat oven to 400°F.',
        '2. Brush glaze onto salmon, bake 12–15 min.',
        '',
        'Source: https://example.com/miso-salmon',
      ].join('\n'),
    );
  });

  it('skips metadata, tags, and source when absent', () => {
    const sparse: Recipe = {
      id: 'r2',
      name: 'Pasta',
      tags: [],
      ingredients: [{ quantity: '1', unit: 'lb', name: 'spaghetti' }],
      directions: ['Boil salted water.', 'Cook pasta per package.'],
    };
    expect(formatRecipeForShare(sparse)).toBe(
      [
        'Pasta',
        '',
        'INGREDIENTS',
        '- 1 lb spaghetti',
        '',
        'DIRECTIONS',
        '1. Boil salted water.',
        '2. Cook pasta per package.',
      ].join('\n'),
    );
  });

  it('emits partial metadata when only some fields are set', () => {
    const partial: Recipe = {
      ...full,
      prep_time_min: null,
      cook_time_min: 20,
      servings: null,
      tags: [],
      source: undefined,
    };
    const out = formatRecipeForShare(partial);
    expect(out).toContain('Cook: 20 min');
    expect(out).not.toContain('Prep:');
    expect(out).not.toContain('Serves:');
    expect(out).not.toContain('Tags:');
    expect(out).not.toContain('Source:');
  });

  it('emits free-text source verbatim', () => {
    const r: Recipe = { ...full, source: "Grandma's cookbook" };
    expect(formatRecipeForShare(r)).toContain("Source: Grandma's cookbook");
  });

  it('falls back gracefully for empty name and empty lists', () => {
    const empty: Recipe = {
      id: 'r3',
      name: '',
      tags: [],
      ingredients: [],
      directions: [],
    };
    const out = formatRecipeForShare(empty);
    expect(out.startsWith('Recipe')).toBe(true);
    expect(out).toContain('INGREDIENTS\n- (none)');
    expect(out).toContain('DIRECTIONS\n1. (none)');
  });

  it('has no trailing newline', () => {
    expect(formatRecipeForShare(full).endsWith('\n')).toBe(false);
  });
});
