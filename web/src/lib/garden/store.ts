/**
 * Minimal garden store — load on mount, expose current data + loading
 * state. No mutations (read-only dashboard).
 */

import { writable } from 'svelte/store';
import { fetchGarden, type GardenState } from '$lib/api/garden';

interface State {
  data: GardenState | null;
  loading: boolean;
  error: string | null;
}

const initial: State = { data: null, loading: false, error: null };
const store = writable<State>(initial);

export const garden = { subscribe: store.subscribe };

export async function loadGarden(): Promise<void> {
  store.update((s) => ({ ...s, loading: true, error: null }));
  try {
    const data = await fetchGarden();
    store.set({ data, loading: false, error: null });
  } catch (err) {
    store.update((s) => ({
      ...s,
      loading: false,
      error: err instanceof Error ? err.message : 'Failed to load garden',
    }));
  }
}

export function __resetGardenStore(): void {
  store.set(initial);
}
