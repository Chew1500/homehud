<!--
  Inline "edit category order" panel.

  Up/down buttons instead of HTML5 drag-drop — drag-drop is flaky on
  touch without a dedicated library, and up/down is unambiguous on
  every device. Covered by the store's moveCategory() which syncs to
  the server after each move.
-->
<script lang="ts">
  import { ChevronUp, ChevronDown, X } from 'lucide-svelte';
  import { groceryCategoryOrder, moveCategory } from '$lib/grocery/store';

  interface Props {
    onClose: () => void;
  }

  let { onClose }: Props = $props();
  const order = $derived($groceryCategoryOrder);
</script>

<div class="flex flex-col gap-3">
  <header class="flex items-center justify-between">
    <div>
      <h2 class="text-base font-semibold">Aisle order</h2>
      <p class="text-xs text-fg-muted">Move categories to match the order you walk the store.</p>
    </div>
    <button
      type="button"
      onclick={onClose}
      aria-label="Close editor"
      class="flex size-9 items-center justify-center rounded-full text-fg-muted hover:bg-surface-muted hover:text-fg"
    >
      <X class="size-4" />
    </button>
  </header>

  <ul class="flex flex-col gap-2">
    {#each order as category, i (category)}
      <li
        class="flex items-center gap-2 rounded-xl border border-border bg-surface px-3 py-2"
      >
        <span class="flex-1 text-sm font-medium">{category}</span>
        <button
          type="button"
          onclick={() => moveCategory(i, i - 1)}
          disabled={i === 0}
          aria-label="Move {category} up"
          class="flex size-8 items-center justify-center rounded-full text-fg-muted hover:bg-surface-muted hover:text-fg disabled:opacity-30"
        >
          <ChevronUp class="size-4" />
        </button>
        <button
          type="button"
          onclick={() => moveCategory(i, i + 1)}
          disabled={i === order.length - 1}
          aria-label="Move {category} down"
          class="flex size-8 items-center justify-center rounded-full text-fg-muted hover:bg-surface-muted hover:text-fg disabled:opacity-30"
        >
          <ChevronDown class="size-4" />
        </button>
      </li>
    {/each}
  </ul>
</div>
