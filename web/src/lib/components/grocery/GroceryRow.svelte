<!--
  Single grocery item row.

  Checkbox + formatted label + delete button. On check/delete the parent
  store handles optimistic mutation + server sync.
-->
<script lang="ts">
  import { Trash2, Check } from 'lucide-svelte';
  import type { GroceryItem } from '$lib/api/grocery';
  import { formatGroceryItem } from '$lib/grocery/parser';
  import { deleteItem, toggleChecked } from '$lib/grocery/store';

  interface Props {
    item: GroceryItem;
  }

  let { item }: Props = $props();

  async function onToggle() {
    await toggleChecked(item.id, !item.checked);
  }

  async function onDelete() {
    await deleteItem(item.id);
  }
</script>

<li
  class="group flex items-center gap-3 border-b border-border px-1 py-3 last:border-b-0"
>
  <button
    type="button"
    onclick={onToggle}
    aria-label={item.checked ? 'Mark as not purchased' : 'Mark as purchased'}
    aria-pressed={item.checked}
    class="flex size-7 shrink-0 items-center justify-center rounded-full border transition-colors"
    class:border-border={!item.checked}
    class:border-accent={item.checked}
    class:bg-accent={item.checked}
    class:text-accent-fg={item.checked}
  >
    {#if item.checked}
      <Check class="size-4" strokeWidth={3} />
    {/if}
  </button>

  <span
    class="flex-1 text-[1rem] leading-snug transition-colors"
    class:text-fg-muted={item.checked}
    class:line-through={item.checked}
  >
    {formatGroceryItem(item)}
  </span>

  <button
    type="button"
    onclick={onDelete}
    aria-label="Remove {item.name}"
    class="flex size-9 shrink-0 items-center justify-center rounded-full text-fg-muted transition-opacity hover:bg-surface-muted hover:text-danger"
  >
    <Trash2 class="size-4" />
  </button>
</li>
