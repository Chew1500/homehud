/**
 * Recipes list store. List CRUD flows through here; detail fetches are
 * cached for short reads so the detail page feels instant after a list
 * tap.
 *
 * The store keeps the last-loaded list in memory and exposes simple
 * async helpers that keep it in sync with the server after each write.
 */

import { writable, get, derived } from 'svelte/store';
import {
  createRecipe,
  deleteRecipe as apiDelete,
  fetchRecipe,
  fetchRecipes,
  updateRecipe,
  type Recipe,
  type RecipeCreateRequest,
  type RecipePatch,
} from '$lib/api/recipes';

interface State {
  items: Recipe[];
  loading: boolean;
  error: string | null;
  initialised: boolean;
}

const initial: State = {
  items: [],
  loading: false,
  error: null,
  initialised: false,
};

const store = writable<State>(initial);

export const recipes = { subscribe: store.subscribe };
export const recipeItems = derived(store, (s) => s.items);

export async function loadRecipes(): Promise<void> {
  store.update((s) => ({ ...s, loading: true, error: null }));
  try {
    const items = await fetchRecipes();
    store.set({ items, loading: false, error: null, initialised: true });
  } catch (err) {
    store.update((s) => ({
      ...s,
      loading: false,
      error: err instanceof Error ? err.message : 'Failed to load recipes',
      initialised: true,
    }));
  }
}

export function getCachedRecipe(id: string): Recipe | undefined {
  return get(store).items.find((r) => r.id === id);
}

/** Fetch a recipe, preferring the cached list entry if present. */
export async function getRecipe(id: string): Promise<Recipe> {
  const cached = getCachedRecipe(id);
  if (cached) return cached;
  return fetchRecipe(id);
}

export async function saveNewRecipe(recipe: RecipeCreateRequest): Promise<string> {
  const { id, recipe: saved } = await createRecipe(recipe);
  store.update((s) => ({ ...s, items: [saved, ...s.items] }));
  return id;
}

export async function saveRecipePatch(id: string, patch: RecipePatch): Promise<Recipe> {
  const { recipe: saved } = await updateRecipe(id, patch);
  store.update((s) => ({
    ...s,
    items: s.items.map((r) => (r.id === id ? saved : r)),
  }));
  return saved;
}

export async function removeRecipe(id: string): Promise<void> {
  const snapshot = get(store).items;
  store.update((s) => ({ ...s, items: s.items.filter((r) => r.id !== id) }));
  try {
    await apiDelete(id);
  } catch (err) {
    store.update((s) => ({
      ...s,
      items: snapshot,
      error: err instanceof Error ? err.message : 'Delete failed',
    }));
    throw err;
  }
}

export function clearRecipeError(): void {
  store.update((s) => ({ ...s, error: null }));
}

export function __resetRecipesForTest(): void {
  store.set(initial);
}
