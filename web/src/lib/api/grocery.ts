/**
 * Grocery API wrappers. Mirror the classic UI's endpoints 1:1 so the
 * backend contract is untouched.
 */

import { apiFetch } from './client';
import { ApiFetchError } from './types';

export interface GroceryItemSource {
  quantity: number;
  recipe_name: string;
}

export interface GroceryItem {
  id: string;
  name: string;
  category: string | null;
  quantity: number | null;
  unit: string | null;
  checked: boolean;
  sources: Record<string, GroceryItemSource>;
  manual_quantity: number;
}

export interface GroceryRecipeLayer {
  recipe_id: string;
  recipe_name: string;
  added_at: string;
}

export interface GroceryState {
  items: GroceryItem[];
  category_order: string[];
  categories: string[];
  recipe_layers: GroceryRecipeLayer[];
}

export interface AddRecipeResult {
  ok: true;
  recipe: { id: string; name: string };
  detail: {
    added: GroceryItem[];
    merged: GroceryItem[];
    mixed_units: { new: GroceryItem; existing: GroceryItem[] }[];
    skipped_dup: GroceryItem[];
  };
  skipped_pantry: string[];
  layer: GroceryRecipeLayer;
  state: GroceryState;
}

export interface RemoveRecipeLayerResult {
  ok: true;
  layer: GroceryRecipeLayer | null;
  items_removed: GroceryItem[];
  items_updated: GroceryItem[];
  state: GroceryState;
}

export function fetchGrocery(): Promise<GroceryState> {
  return apiFetch<GroceryState>('/api/grocery');
}

export interface AddItemRequest {
  name: string;
  quantity?: number | null;
  unit?: string | null;
}

export async function addGroceryItem(item: AddItemRequest): Promise<GroceryItem | 'duplicate'> {
  try {
    const res = await apiFetch<{ ok: true; item: GroceryItem }>('/api/grocery', {
      method: 'POST',
      json: item,
    });
    return res.item;
  } catch (err) {
    // 409 is non-fatal — the server reports existing items. Bubble a
    // string the caller can branch on rather than a generic Error.
    if (err instanceof ApiFetchError && err.status === 409) return 'duplicate';
    throw err;
  }
}

export type GroceryPatch = Partial<Pick<GroceryItem, 'name' | 'category' | 'quantity' | 'unit' | 'checked'>>;

export function updateGroceryItem(id: string, patch: GroceryPatch): Promise<{ ok: true; item: GroceryItem }> {
  return apiFetch(`/api/grocery/${id}`, { method: 'PATCH', json: patch });
}

export function deleteGroceryItem(id: string): Promise<{ ok: true }> {
  return apiFetch(`/api/grocery/${id}`, { method: 'DELETE' });
}

export function reorderGroceryItems(ids: string[]): Promise<{ ok: true }> {
  return apiFetch('/api/grocery/reorder', { method: 'POST', json: { ids } });
}

export function setCategoryOrder(order: string[]): Promise<{ ok: true; category_order: string[] }> {
  return apiFetch('/api/grocery/category-order', { method: 'POST', json: { order } });
}

export function clearCheckedGroceryItems(): Promise<{ ok: true; removed: number }> {
  return apiFetch('/api/grocery/clear-checked', { method: 'POST' });
}

export function addRecipeToGrocery(
  recipeId: string,
  scale = 1.0,
): Promise<AddRecipeResult> {
  return apiFetch(`/api/grocery/recipe/${recipeId}`, {
    method: 'POST',
    json: { scale },
  });
}

export function removeRecipeLayer(recipeId: string): Promise<RemoveRecipeLayerResult> {
  return apiFetch(`/api/grocery/recipe/${recipeId}`, { method: 'DELETE' });
}
