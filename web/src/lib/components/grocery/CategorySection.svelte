<!--
  Category section — a header with item count, a drag-reorderable list
  of items, and an optional collapsed state.

  Drag behaviour (via svelte-dnd-action):
    - Long-press or click-and-hold any row to start dragging
    - Move within the list to reorder
    - Move into a different category section to change category
    - Release to commit; the store debounces the server round-trip
-->
<script lang="ts">
  import { ChevronRight } from 'lucide-svelte';
  import { dndzone, type DndEvent } from 'svelte-dnd-action';
  import { flip } from 'svelte/animate';
  import type { GroceryItem } from '$lib/api/grocery';
  import GroceryRow from './GroceryRow.svelte';

  interface Props {
    category: string;
    items: GroceryItem[];
    onConsider: (category: string, newItems: GroceryItem[]) => void;
    onFinalize: (category: string, newItems: GroceryItem[]) => void;
  }

  let { category, items, onConsider, onFinalize }: Props = $props();
  let collapsed = $state(false);

  const uncheckedCount = $derived(items.filter((i) => !i.checked).length);
  const FLIP_MS = 180;

  function handleConsider(ev: CustomEvent<DndEvent<GroceryItem>>) {
    onConsider(category, ev.detail.items);
  }

  function handleFinalize(ev: CustomEvent<DndEvent<GroceryItem>>) {
    onFinalize(category, ev.detail.items);
  }
</script>

<section class="rounded-xl border border-border bg-surface">
  <button
    type="button"
    onclick={() => (collapsed = !collapsed)}
    class="flex w-full items-center gap-2 px-3 py-2.5 text-left"
    aria-expanded={!collapsed}
  >
    <ChevronRight
      class="size-4 shrink-0 text-fg-muted transition-transform {collapsed ? '' : 'rotate-90'}"
    />
    <span class="flex-1 text-xs font-semibold uppercase tracking-[0.08em] text-fg-muted">
      {category}
    </span>
    <span class="text-xs text-fg-muted">
      {uncheckedCount} / {items.length}
    </span>
  </button>

  {#if !collapsed}
    <ul
      class="min-h-[2rem] px-2 pb-1"
      use:dndzone={{
        items,
        flipDurationMs: FLIP_MS,
        dropTargetStyle: {},
        dropTargetClasses: ['dnd-drop-target'],
        type: 'grocery',
      }}
      onconsider={handleConsider}
      onfinalize={handleFinalize}
    >
      {#each items as item (item.id)}
        <li animate:flip={{ duration: FLIP_MS }}>
          <GroceryRow {item} />
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  /* Visual affordance when the zone is a valid drop target. The
     library toggles ``dnd-drop-target`` as the pointer enters. */
  :global(.dnd-drop-target) {
    outline: 2px dashed var(--color-accent, #f39060);
    outline-offset: -4px;
    border-radius: 12px;
  }
</style>
