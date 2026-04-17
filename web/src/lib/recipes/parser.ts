/**
 * Parse a free-form ingredient line from the editor into the structured
 * {quantity, unit, name} shape the API expects. Mirrors the
 * ``parseIngredientLine`` helper in the classic UI.
 */

import type { RecipeIngredient } from '$lib/api/recipes';

export function parseIngredientLine(line: string): RecipeIngredient | null {
  const trimmed = line.trim();
  if (!trimmed) return null;

  // "1 1/2 cups sugar", "2 tbsp olive oil", "3 large eggs"
  const tri = trimmed.match(/^([\d./]+(?:\s*-\s*[\d./]+)?)\s+(\w+)\s+(.+)$/);
  if (tri) return { quantity: tri[1], unit: tri[2], name: tri[3] };

  // "2 eggs" — no explicit unit
  const bi = trimmed.match(/^([\d./]+)\s+(.+)$/);
  if (bi) return { quantity: bi[1], unit: '', name: bi[2] };

  // Plain name
  return { quantity: '', unit: '', name: trimmed };
}

/** Render an ingredient as a single line for the editor textarea. */
export function formatIngredientLine(ing: RecipeIngredient): string {
  return [ing.quantity, ing.unit, ing.name].filter(Boolean).join(' ');
}

/** Render an ingredient as a display label (used on the detail view). */
export function displayIngredient(ing: RecipeIngredient): string {
  return formatIngredientLine(ing);
}
