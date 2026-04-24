<!--
  Grocery — mobile-first shopping list.

  Composer at top, scroll-able category sections in the middle, and a
  footer with the "Clear purchased" action. The "Aisle order" editor is
  inline (toggles in place) rather than a modal.
-->
<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { ArrowUpDown, Trash2, RefreshCw, AlertCircle } from 'lucide-svelte';
  import AddItemComposer from '$lib/components/grocery/AddItemComposer.svelte';
  import CategoryOrderEditor from '$lib/components/grocery/CategoryOrderEditor.svelte';
  import CategorySection from '$lib/components/grocery/CategorySection.svelte';
  import RecipeLayerRow from '$lib/components/grocery/RecipeLayerRow.svelte';
  import type { GroceryItem } from '$lib/api/grocery';
  import {
    clearChecked,
    clearGroceryError,
    commitItemReorder,
    grocery,
    loadGrocery,
    setItemsLocally,
  } from '$lib/grocery/store';

  const UNCATEGORIZED = 'Uncategorized';

  let editingOrder = $state(false);
  let clearing = $state(false);

  // Snapshot of items as they were BEFORE the current drag. Used by
  // commitItemReorder to detect which items' categories changed and
  // to roll back on server failure.
  let preDragSnapshot: GroceryItem[] | null = null;
  // Debounce commit — svelte-dnd-action fires `finalize` on BOTH zones
  // when an item crosses zones. We consolidate the final committed
  // state before talking to the server.
  let commitTimer: ReturnType<typeof setTimeout> | null = null;

  const state = $derived($grocery);

  const sections = $derived(groupByCategory(state.items, state.category_order));
  const checkedCount = $derived(state.items.filter((i) => i.checked).length);

  onMount(() => {
    loadGrocery();
  });

  function groupByCategory(
    items: GroceryItem[],
    order: string[],
  ): Array<{ category: string; items: GroceryItem[] }> {
    const byCat = new Map<string, GroceryItem[]>();
    for (const it of items) {
      const c = it.category ?? 'Uncategorized';
      const bucket = byCat.get(c) ?? [];
      bucket.push(it);
      byCat.set(c, bucket);
    }
    const seen = new Set<string>();
    const result: Array<{ category: string; items: GroceryItem[] }> = [];
    for (const c of order) {
      const bucket = byCat.get(c);
      if (bucket && bucket.length) {
        result.push({ category: c, items: bucket });
        seen.add(c);
      }
    }
    // Any category present in items but missing from category_order
    // (e.g. first appearance) — append in insertion order.
    for (const [c, bucket] of byCat.entries()) {
      if (!seen.has(c)) result.push({ category: c, items: bucket });
    }
    return result;
  }

  async function onClearChecked() {
    if (clearing) return;
    clearing = true;
    await clearChecked();
    clearing = false;
  }

  /**
   * Build a new global items list by replacing the slice in
   * ``targetCategory`` with ``newSlice``. Items in ``newSlice`` get
   * their category normalised to the target so cross-zone drops
   * update the category server-side.
   *
   * Items that left this category but haven't been picked up by the
   * destination zone's event yet won't appear until that zone fires
   * — svelte-dnd-action always fires both zones on a cross-zone drop,
   * so the brief intermediate state is fine.
   */
  function applyDragUpdate(targetCategory: string, newSlice: GroceryItem[]) {
    const newIds = new Set(newSlice.map((i) => i.id));
    const normalised = newSlice.map((i) => ({
      ...i,
      category: targetCategory === UNCATEGORIZED ? null : targetCategory,
    }));

    // Preserve the order of OTHER categories' items. Reconstruct the
    // full list by walking the current sections and swapping in
    // normalised for the target section.
    const result: GroceryItem[] = [];
    for (const section of sections) {
      if (section.category === targetCategory) {
        result.push(...normalised);
      } else {
        for (const item of section.items) {
          // Skip any item that's now in newSlice (it moved to target)
          if (!newIds.has(item.id)) result.push(item);
        }
      }
    }
    setItemsLocally(result);
  }

  function handleConsider(targetCategory: string, newSlice: GroceryItem[]) {
    if (!preDragSnapshot) preDragSnapshot = [...state.items];
    applyDragUpdate(targetCategory, newSlice);
  }

  function handleFinalize(targetCategory: string, newSlice: GroceryItem[]) {
    applyDragUpdate(targetCategory, newSlice);
    // Both source and destination zones fire finalize on cross-zone
    // drop. Debounce so we commit once with the final state.
    if (commitTimer) clearTimeout(commitTimer);
    commitTimer = setTimeout(() => {
      commitTimer = null;
      const snapshot = preDragSnapshot;
      preDragSnapshot = null;
      if (!snapshot) return;
      void commitItemReorder(state.items, snapshot);
    }, 50);
  }

  onDestroy(() => {
    if (commitTimer) clearTimeout(commitTimer);
  });
</script>

<div class="flex h-full flex-col">
  <!-- Scroll region: header + composer + sections -->
  <div class="flex-1 overflow-y-auto">
    <div class="mx-auto flex w-full max-w-xl flex-col gap-4 px-4 pb-4 pt-[max(1rem,env(safe-area-inset-top))]">
      <header class="flex items-center justify-between">
        <h1 class="text-2xl font-semibold">Grocery</h1>
        <button
          type="button"
          onclick={() => (editingOrder = !editingOrder)}
          class="flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-xs text-fg-muted transition-colors hover:text-fg"
          class:text-accent={editingOrder}
          class:border-accent={editingOrder}
        >
          <ArrowUpDown class="size-3.5" />
          <span>{editingOrder ? 'Done' : 'Aisle order'}</span>
        </button>
      </header>

      {#if state.error}
        <div
          class="flex items-start gap-2 rounded-xl border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger"
        >
          <AlertCircle class="mt-0.5 size-4 shrink-0" />
          <div class="flex-1">{state.error}</div>
          <button
            type="button"
            onclick={clearGroceryError}
            class="text-xs opacity-70 hover:opacity-100"
          >
            dismiss
          </button>
        </div>
      {/if}

      {#if editingOrder}
        <CategoryOrderEditor onClose={() => (editingOrder = false)} />
      {:else}
        <AddItemComposer />

        <RecipeLayerRow layers={state.recipe_layers ?? []} />

        {#if !state.initialised}
          <p class="py-8 text-center text-sm text-fg-muted">Loading…</p>
        {:else if sections.length === 0}
          <div class="flex flex-col items-center gap-2 py-12 text-center">
            <p class="text-base text-fg">Your grocery list is empty.</p>
            <p class="text-sm text-fg-muted">
              Add items above, or say <span class="font-medium text-fg">"add milk to the grocery list"</span>.
            </p>
          </div>
        {:else}
          <div class="flex flex-col gap-3">
            {#each sections as section (section.category)}
              <CategorySection
                category={section.category}
                items={section.items}
                onConsider={handleConsider}
                onFinalize={handleFinalize}
              />
            {/each}
          </div>
        {/if}
      {/if}
    </div>
  </div>

  <!-- Footer: clear purchased -->
  {#if !editingOrder && checkedCount > 0}
    <div
      class="border-t border-border bg-surface/80 px-4 py-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] backdrop-blur"
    >
      <div class="mx-auto flex w-full max-w-xl items-center justify-between gap-3">
        <span class="text-sm text-fg-muted">
          {checkedCount} purchased
        </span>
        <button
          type="button"
          onclick={onClearChecked}
          disabled={clearing}
          class="flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-sm text-fg-muted transition-colors hover:text-danger disabled:opacity-50"
        >
          {#if clearing}
            <RefreshCw class="size-3.5 animate-spin" />
          {:else}
            <Trash2 class="size-3.5" />
          {/if}
          <span>Clear purchased</span>
        </button>
      </div>
    </div>
  {/if}
</div>
