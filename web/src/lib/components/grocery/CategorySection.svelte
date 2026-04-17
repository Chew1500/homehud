<!--
  Category section — a header with item count and a list of rows.
  Collapsed/expanded state is purely client-side; all items stay in memory.
-->
<script lang="ts">
  import { ChevronRight } from 'lucide-svelte';
  import type { GroceryItem } from '$lib/api/grocery';
  import GroceryRow from './GroceryRow.svelte';

  interface Props {
    category: string;
    items: GroceryItem[];
  }

  let { category, items }: Props = $props();
  let collapsed = $state(false);

  const uncheckedCount = $derived(items.filter((i) => !i.checked).length);
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
    <ul class="px-2 pb-1">
      {#each items as item (item.id)}
        <GroceryRow {item} />
      {/each}
    </ul>
  {/if}
</section>
