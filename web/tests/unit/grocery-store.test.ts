/**
 * Grocery store — mostly about optimistic behaviour. The test ensures
 * that local state flips immediately on user actions and rolls back on
 * server failure.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';

const jsonResponse = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

beforeEach(() => {
  vi.resetModules();
  localStorage.clear();
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('grocery store', () => {
  it('loadGrocery populates items + category order', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      jsonResponse(200, {
        items: [
          { id: 'a', name: 'milk', category: 'Dairy', quantity: 1, unit: null, checked: false },
        ],
        category_order: ['Dairy', 'Produce'],
        categories: ['Dairy', 'Produce'],
      }),
    );

    const mod = await import('../../src/lib/grocery/store');
    mod.__resetGroceryStore();
    await mod.loadGrocery();

    const state = get(mod.grocery);
    expect(state.items).toHaveLength(1);
    expect(state.items[0].name).toBe('milk');
    expect(state.category_order).toEqual(['Dairy', 'Produce']);
    expect(state.initialised).toBe(true);
    expect(state.error).toBeNull();
  });

  it('toggleChecked updates immediately and reconciles with server', async () => {
    const mod = await import('../../src/lib/grocery/store');
    mod.__resetGroceryStore();
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(
        jsonResponse(200, {
          items: [
            { id: 'a', name: 'milk', category: null, quantity: null, unit: null, checked: false },
          ],
          category_order: [],
          categories: [],
        }),
      )
      .mockResolvedValueOnce(jsonResponse(200, { ok: true, item: { id: 'a' } }));

    await mod.loadGrocery();

    const promise = mod.toggleChecked('a', true);
    // Optimistic: check reflected before the PATCH completes.
    expect(get(mod.grocery).items[0].checked).toBe(true);
    await promise;
    expect(get(mod.grocery).items[0].checked).toBe(true);
  });

  it('toggleChecked rolls back on server error', async () => {
    const mod = await import('../../src/lib/grocery/store');
    mod.__resetGroceryStore();
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(
        jsonResponse(200, {
          items: [
            { id: 'a', name: 'milk', category: null, quantity: null, unit: null, checked: false },
          ],
          category_order: [],
          categories: [],
        }),
      )
      .mockResolvedValueOnce(jsonResponse(500, { error: 'db down' }));

    await mod.loadGrocery();
    await mod.toggleChecked('a', true);

    expect(get(mod.grocery).items[0].checked).toBe(false);
    expect(get(mod.grocery).error).toBeTruthy();
  });

  it('deleteItem removes locally then syncs', async () => {
    const mod = await import('../../src/lib/grocery/store');
    mod.__resetGroceryStore();
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(
        jsonResponse(200, {
          items: [
            { id: 'a', name: 'milk', category: null, quantity: null, unit: null, checked: false },
            { id: 'b', name: 'eggs', category: null, quantity: null, unit: null, checked: false },
          ],
          category_order: [],
          categories: [],
        }),
      )
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }));

    await mod.loadGrocery();
    await mod.deleteItem('a');

    const ids = get(mod.grocery).items.map((i) => i.id);
    expect(ids).toEqual(['b']);
  });

  it('moveCategory reorders locally and POSTs new order', async () => {
    const mod = await import('../../src/lib/grocery/store');
    mod.__resetGroceryStore();
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(
        jsonResponse(200, {
          items: [],
          category_order: ['Produce', 'Dairy', 'Pantry'],
          categories: ['Produce', 'Dairy', 'Pantry'],
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse(200, {
          ok: true,
          category_order: ['Dairy', 'Produce', 'Pantry'],
        }),
      );

    await mod.loadGrocery();
    await mod.moveCategory(1, 0);

    const order = get(mod.grocery).category_order;
    expect(order).toEqual(['Dairy', 'Produce', 'Pantry']);
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    const [url, init] = fetchSpy.mock.calls[1]!;
    expect(url).toBe('/api/grocery/category-order');
    expect(JSON.parse(init!.body as string)).toEqual({
      order: ['Dairy', 'Produce', 'Pantry'],
    });
  });
});
