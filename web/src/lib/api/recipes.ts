/**
 * Recipes API. Matches the Python handlers 1:1.
 *
 * All ingredient/direction fields are serialised as raw strings on the
 * wire; parsing happens on the server side in src/features/recipes.py.
 */

import { apiFetch } from './client';

export interface RecipeIngredient {
  /** Free-form quantity string — the server stores "1 1/2" as-is. */
  quantity: string;
  unit: string;
  name: string;
}

export interface Recipe {
  id: string;
  name: string;
  tags: string[];
  prep_time_min?: number | null;
  cook_time_min?: number | null;
  servings?: number | null;
  ingredients: RecipeIngredient[];
  directions: string[];
  source?: string;
  raw_text?: string;
  created_at?: string;
  updated_at?: string;
}

export type RecipeCreateRequest = Omit<Recipe, 'id' | 'created_at' | 'updated_at'>;
export type RecipePatch = Partial<RecipeCreateRequest>;

export function fetchRecipes(): Promise<Recipe[]> {
  return apiFetch<Recipe[]>('/api/recipes');
}

export function fetchRecipe(id: string): Promise<Recipe> {
  return apiFetch<Recipe>(`/api/recipes/${encodeURIComponent(id)}`);
}

export function createRecipe(recipe: RecipeCreateRequest): Promise<{ id: string; recipe: Recipe }> {
  return apiFetch('/api/recipes', { method: 'POST', json: recipe });
}

export function updateRecipe(id: string, patch: RecipePatch): Promise<{ ok: true; recipe: Recipe }> {
  return apiFetch(`/api/recipes/${encodeURIComponent(id)}`, { method: 'PATCH', json: patch });
}

export function deleteRecipe(id: string): Promise<{ ok: true }> {
  return apiFetch(`/api/recipes/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

export interface UploadImageResponse {
  recipe: RecipeCreateRequest;
  saved: boolean;
}

/** Upload a base64-encoded image; server asks the LLM to parse it into
 *  a recipe shape. Returns the parsed fields — nothing is persisted
 *  until the user saves the form. */
export function uploadRecipeImage(
  imageBase64: string,
  mediaType: string,
): Promise<UploadImageResponse> {
  return apiFetch('/api/recipes/upload-image', {
    method: 'POST',
    json: { image: imageBase64, media_type: mediaType },
  });
}
