/**
 * Format a recipe as paste-friendly plaintext and share it via the
 * native share sheet (falling back to the clipboard).
 */

import type { Recipe } from '$lib/api/recipes';
import { formatIngredientLine } from './parser';

export function formatRecipeForShare(recipe: Recipe): string {
  const blocks: string[] = [];

  const title = recipe.name?.trim() || 'Recipe';
  blocks.push(title);

  const infoLines: string[] = [];
  const metaPieces: string[] = [];
  if (recipe.prep_time_min) metaPieces.push(`Prep: ${recipe.prep_time_min} min`);
  if (recipe.cook_time_min) metaPieces.push(`Cook: ${recipe.cook_time_min} min`);
  if (recipe.servings) metaPieces.push(`Serves: ${recipe.servings}`);
  if (metaPieces.length) infoLines.push(metaPieces.join(' \u00b7 '));
  if (recipe.tags?.length) infoLines.push(`Tags: ${recipe.tags.join(', ')}`);
  if (infoLines.length) blocks.push(infoLines.join('\n'));

  const ingredientLines = recipe.ingredients?.length
    ? recipe.ingredients.map((ing) => `- ${formatIngredientLine(ing)}`)
    : ['- (none)'];
  blocks.push(['INGREDIENTS', ...ingredientLines].join('\n'));

  const directionLines = recipe.directions?.length
    ? recipe.directions.map((step, i) => `${i + 1}. ${step}`)
    : ['1. (none)'];
  blocks.push(['DIRECTIONS', ...directionLines].join('\n'));

  const source = recipe.source?.trim();
  if (source) blocks.push(`Source: ${source}`);

  return blocks.join('\n\n');
}

export type ShareResult = 'shared' | 'copied' | 'cancelled' | 'unavailable';

export async function shareRecipe(recipe: Recipe): Promise<ShareResult> {
  const text = formatRecipeForShare(recipe);
  const title = recipe.name?.trim() || 'Recipe';

  if (typeof navigator !== 'undefined' && typeof navigator.share === 'function') {
    try {
      await navigator.share({ title, text });
      return 'shared';
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        return 'cancelled';
      }
      // Other failures (e.g. NotAllowedError outside a gesture) fall
      // through to the clipboard path.
    }
  }

  if (
    typeof navigator !== 'undefined' &&
    navigator.clipboard &&
    typeof navigator.clipboard.writeText === 'function'
  ) {
    await navigator.clipboard.writeText(text);
    return 'copied';
  }

  return 'unavailable';
}