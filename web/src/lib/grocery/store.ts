/**
 * Grocery list store.
 *
 * Holds the list state + async loading/error flags, and exposes
 * optimistic CRUD helpers that update the store first and reconcile
 * with the server in the background. Mirrors the classic UI's UX —
 * fast local feedback with best-effort sync.
 */

import { writable, derived, get } from 'svelte/store';
import {
  addGroceryItem,
  addRecipeToGrocery,
  clearCheckedGroceryItems,
  deleteGroceryItem,
  fetchGrocery,
  removeRecipeLayer,
  reorderGroceryItems,
  setCategoryOrder,
  updateGroceryItem,
  type AddItemRequest,
  type AddRecipeResult,
  type GroceryItem,
  type GroceryPatch,
  type GroceryRecipeLayer,
  type GroceryState,
} from '$lib/api/grocery';

interface StoreState extends GroceryState {
  loading: boolean;
  error: string | null;
  initialised: boolean;
}

const initial: StoreState = {
  items: [],
  category_order: [],
  categories: [],
  recipe_layers: [],
  loading: false,
  error: null,
  initialised: false,
};

const store = writable<StoreState>(initial);

export const grocery = { subscribe: store.subscribe };
export const groceryItems = derived(store, (s) => s.items);
export const groceryCategoryOrder = derived(store, (s) => s.category_order);
export const groceryRecipeLayers = derived(store, (s) => s.recipe_layers ?? []);

export async function loadGrocery(): Promise<void> {
  store.update((s) => ({ ...s, loading: true, error: null }));
  try {
    const data = await fetchGrocery();
    store.set({
      ...data,
      recipe_layers: data.recipe_layers ?? [],
      loading: false,
      error: null,
      initialised: true,
    });
  } catch (err) {
    store.update((s) => ({
      ...s,
      loading: false,
      error: err instanceof Error ? err.message : 'Failed to load grocery list',
      initialised: true,
    }));
  }
}

export async function addRecipeLayer(recipeId: string, scale = 1.0): Promise<AddRecipeResult | 'error'> {
  try {
    const res = await addRecipeToGrocery(recipeId, scale);
    // Refetch so category assignments (cache + LLM) land before render.
    await loadGrocery();
    return res;
  } catch (err) {
    store.update((s) => ({
      ...s,
      error: err instanceof Error ? err.message : 'Failed to add recipe',
    }));
    return 'error';
  }
}

export async function removeRecipeLayerFromList(recipeId: string): Promise<'ok' | 'error'> {
  const snapshot = get(store);
  // Optimistic: drop the pill. Items get reconciled on refetch.
  store.update((s) => ({
    ...s,
    recipe_layers: s.recipe_layers.filter((l) => l.recipe_id !== recipeId),
  }));
  try {
    await removeRecipeLayer(recipeId);
    await loadGrocery();
    return 'ok';
  } catch (err) {
    store.update((s) => ({
      ...s,
      recipe_layers: snapshot.recipe_layers,
      error: err instanceof Error ? err.message : 'Failed to remove recipe',
    }));
    return 'error';
  }
}

export type { AddRecipeResult, GroceryRecipeLayer };

/** Add an item and refetch to pick up server-side categorization. */
export async function addItem(req: AddItemRequest): Promise<'ok' | 'duplicate' | 'error'> {
  try {
    const result = await addGroceryItem(req);
    if (result === 'duplicate') return 'duplicate';
    // Reload — the server may assign a category via cache/LLM and we
    // want that reflected immediately.
    await loadGrocery();
    return 'ok';
  } catch (err) {
    store.update((s) => ({
      ...s,
      error: err instanceof Error ? err.message : 'Failed to add item',
    }));
    return 'error';
  }
}

export async function toggleChecked(id: string, checked: boolean): Promise<void> {
  mutateItem(id, (item) => ({ ...item, checked }));
  try {
    await updateGroceryItem(id, { checked });
  } catch (err) {
    mutateItem(id, (item) => ({ ...item, checked: !checked }));
    store.update((s) => ({
      ...s,
      error: err instanceof Error ? err.message : 'Toggle failed',
    }));
  }
}

export async function deleteItem(id: string): Promise<void> {
  const snapshot = get(store).items;
  store.update((s) => ({ ...s, items: s.items.filter((i) => i.id !== id) }));
  try {
    await deleteGroceryItem(id);
  } catch (err) {
    store.update((s) => ({
      ...s,
      items: snapshot,
      error: err instanceof Error ? err.message : 'Delete failed',
    }));
  }
}

export async function patchItem(id: string, patch: GroceryPatch): Promise<void> {
  const snapshot = get(store).items;
  mutateItem(id, (item) => ({ ...item, ...patch }));
  try {
    await updateGroceryItem(id, patch);
  } catch (err) {
    store.update((s) => ({
      ...s,
      items: snapshot,
      error: err instanceof Error ? err.message : 'Update failed',
    }));
  }
}

export async function clearChecked(): Promise<number> {
  const snapshot = get(store).items;
  store.update((s) => ({ ...s, items: s.items.filter((i) => !i.checked) }));
  try {
    const res = await clearCheckedGroceryItems();
    return res.removed;
  } catch (err) {
    store.update((s) => ({
      ...s,
      items: snapshot,
      error: err instanceof Error ? err.message : 'Clear failed',
    }));
    return 0;
  }
}

export async function moveCategory(from: number, to: number): Promise<void> {
  const current = get(store).category_order.slice();
  if (from < 0 || from >= current.length) return;
  const clamped = Math.max(0, Math.min(to, current.length - 1));
  if (from === clamped) return;
  const [moved] = current.splice(from, 1);
  current.splice(clamped, 0, moved);
  store.update((s) => ({ ...s, category_order: current }));
  try {
    const res = await setCategoryOrder(current);
    store.update((s) => ({ ...s, category_order: res.category_order }));
  } catch (err) {
    store.update((s) => ({
      ...s,
      error: err instanceof Error ? err.message : 'Reorder failed',
    }));
  }
}

export function clearGroceryError(): void {
  store.update((s) => ({ ...s, error: null }));
}

/**
 * Commit a drag-reorder to the server.
 *
 *  - ``newOrder`` is the full items list in its new order (categories
 *    already reflect any cross-category moves).
 *  - ``snapshot`` is the items list as it was BEFORE the drag began —
 *    used to detect which items had their category changed so we can
 *    PATCH each one, and to roll back the optimistic update if
 *    anything fails.
 *
 *  The optimistic update to ``store.items`` has already been applied
 *  by the drag handlers; this function only talks to the server and
 *  rolls back on failure.
 */
export async function commitItemReorder(
  newOrder: GroceryItem[],
  snapshot: GroceryItem[],
): Promise<void> {
  const priorById = new Map(snapshot.map((i) => [i.id, i]));
  const categoryChanges = newOrder.filter((item) => {
    const prev = priorById.get(item.id);
    return prev != null && (prev.category ?? null) !== (item.category ?? null);
  });

  try {
    // Apply category changes first so the server-side state matches
    // the ID order we're about to POST.
    for (const item of categoryChanges) {
      await updateGroceryItem(item.id, { category: item.category });
    }
    await reorderGroceryItems(newOrder.map((i) => i.id));
  } catch (err) {
    store.update((s) => ({
      ...s,
      items: snapshot,
      error: err instanceof Error ? err.message : 'Reorder failed',
    }));
  }
}

/** Apply a drag preview to store.items without hitting the server.
 *  Called during svelte-dnd-action's ``consider`` and ``finalize``
 *  events so the UI keeps up with the pointer. */
export function setItemsLocally(newItems: GroceryItem[]): void {
  store.update((s) => ({ ...s, items: newItems }));
}

function mutateItem(id: string, fn: (item: GroceryItem) => GroceryItem): void {
  store.update((s) => ({
    ...s,
    items: s.items.map((i) => (i.id === id ? fn(i) : i)),
  }));
}

/** Test hook. */
export function __resetGroceryStore(): void {
  store.set(initial);
}
