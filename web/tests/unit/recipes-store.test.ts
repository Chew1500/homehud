import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';

const jsonResponse = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

const fakeRecipe = (id: string, name: string) => ({
  id,
  name,
  tags: [],
  prep_time_min: null,
  cook_time_min: null,
  servings: null,
  ingredients: [],
  directions: [],
  source: 'manual',
  raw_text: '',
});

beforeEach(() => {
  vi.resetModules();
  localStorage.clear();
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('recipes store', () => {
  it('loadRecipes populates items', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      jsonResponse(200, [fakeRecipe('a', 'pancakes'), fakeRecipe('b', 'soup')]),
    );
    const mod = await import('../../src/lib/recipes/store');
    mod.__resetRecipesForTest();
    await mod.loadRecipes();

    const items = get(mod.recipes).items;
    expect(items.map((r) => r.id)).toEqual(['a', 'b']);
  });

  it('saveNewRecipe prepends the new recipe', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse(200, [fakeRecipe('a', 'pancakes')]))
      .mockResolvedValueOnce(
        jsonResponse(200, { id: 'b', recipe: fakeRecipe('b', 'soup') }),
      );

    const mod = await import('../../src/lib/recipes/store');
    mod.__resetRecipesForTest();
    await mod.loadRecipes();
    const id = await mod.saveNewRecipe({
      name: 'soup',
      tags: [],
      prep_time_min: null,
      cook_time_min: null,
      servings: null,
      ingredients: [],
      directions: [],
    });
    expect(id).toBe('b');
    expect(get(mod.recipes).items.map((r) => r.id)).toEqual(['b', 'a']);
  });

  it('removeRecipe rolls back on failure', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse(200, [fakeRecipe('a', 'pancakes')]))
      .mockResolvedValueOnce(jsonResponse(500, { error: 'db down' }));

    const mod = await import('../../src/lib/recipes/store');
    mod.__resetRecipesForTest();
    await mod.loadRecipes();

    await expect(mod.removeRecipe('a')).rejects.toBeTruthy();
    const ids = get(mod.recipes).items.map((r) => r.id);
    expect(ids).toEqual(['a']);
    expect(get(mod.recipes).error).toBeTruthy();
  });

  it('getCachedRecipe returns undefined for unknown ids', async () => {
    const mod = await import('../../src/lib/recipes/store');
    mod.__resetRecipesForTest();
    expect(mod.getCachedRecipe('missing')).toBeUndefined();
  });
});
