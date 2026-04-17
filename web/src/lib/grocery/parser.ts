/**
 * Parses free-form grocery input like "2 cups flour" or "1/2 lb butter"
 * into a structured {name, quantity, unit} triple.
 *
 * Unit aliases mirror ``src/features/grocery.py:_UNIT_ALIASES`` so the
 * server and client agree on canonical forms.
 */

const UNIT_ALIASES: Record<string, string> = {
  cup: 'cup', cups: 'cup',
  tsp: 'tsp', teaspoon: 'tsp', teaspoons: 'tsp',
  tbsp: 'tbsp', tablespoon: 'tbsp', tablespoons: 'tbsp',
  lb: 'lb', lbs: 'lb', pound: 'lb', pounds: 'lb',
  oz: 'oz', ounce: 'oz', ounces: 'oz',
  g: 'g', gram: 'g', grams: 'g',
  kg: 'kg', kilogram: 'kg', kilograms: 'kg',
  ml: 'ml', milliliter: 'ml', milliliters: 'ml',
  l: 'l', liter: 'l', liters: 'l', litre: 'l', litres: 'l',
  clove: 'clove', cloves: 'clove',
  piece: 'piece', pieces: 'piece',
  slice: 'slice', slices: 'slice',
  can: 'can', cans: 'can',
  pack: 'pack', packs: 'pack',
  bottle: 'bottle', bottles: 'bottle',
  dozen: 'dozen', dozens: 'dozen',
  bunch: 'bunch', bunches: 'bunch',
  stick: 'stick', sticks: 'stick',
  head: 'head', heads: 'head',
};

export interface ParsedItem {
  name: string;
  quantity: number | null;
  unit: string | null;
}

export function parseGroceryInput(input: string): ParsedItem {
  const s = input.trim();
  if (!s) return { name: '', quantity: null, unit: null };

  // Match "2", "2.5", "1/2", or "1 1/2" followed optionally by a unit word and the name.
  const m = s.match(
    /^(\d+\s+\d+\/\d+|\d+\/\d+|\d+(?:\.\d+)?)\s+(?:([a-zA-Z]+)\s+)?(.+)$/,
  );
  if (!m) return { name: s, quantity: null, unit: null };

  let qty: number;
  if (m[1].includes('/')) {
    const parts = m[1].split(/\s+/);
    if (parts.length === 2) {
      const [n, d] = parts[1].split('/').map(Number);
      qty = parseFloat(parts[0]) + n / d;
    } else {
      const [n, d] = m[1].split('/').map(Number);
      qty = n / d;
    }
  } else {
    qty = parseFloat(m[1]);
  }

  const rawUnit = (m[2] ?? '').toLowerCase();
  const unit = rawUnit && UNIT_ALIASES[rawUnit] ? UNIT_ALIASES[rawUnit] : null;
  // If the "unit" token wasn't actually a known unit, restore it to the name.
  const name = unit ? m[3] : m[2] ? `${m[2]} ${m[3]}` : m[3];

  return { name: name.trim(), quantity: qty, unit };
}

/** Render an item back into a user-facing label. */
export function formatGroceryItem(item: {
  name: string;
  quantity: number | null;
  unit: string | null;
}): string {
  const { name, quantity, unit } = item;
  const parts: string[] = [];
  if (quantity != null) parts.push(formatQuantity(quantity));
  // Pluralise only for qty > 1 — fractions like ½ use the singular
  // form in natural English ("½ lb butter", not "½ lbs butter").
  const plural = quantity != null && quantity > 1;
  if (unit) {
    parts.push(plural && !unit.endsWith('s') ? `${unit}s` : unit);
    if (name) parts.push(name);
  } else if (name) {
    parts.push(plural && !name.endsWith('s') ? `${name}s` : name);
  }
  return parts.join(' ');
}

function formatQuantity(q: number): string {
  if (Number.isInteger(q)) return String(q);
  // Prefer simple fractions for common cooking values.
  const fractions: [number, string][] = [
    [1 / 4, '¼'],
    [1 / 3, '⅓'],
    [1 / 2, '½'],
    [2 / 3, '⅔'],
    [3 / 4, '¾'],
  ];
  const whole = Math.floor(q);
  const frac = q - whole;
  const match = fractions.find(([v]) => Math.abs(v - frac) < 0.02);
  if (match) return whole > 0 ? `${whole} ${match[1]}` : match[1];
  return q.toFixed(2).replace(/\.?0+$/, '');
}
