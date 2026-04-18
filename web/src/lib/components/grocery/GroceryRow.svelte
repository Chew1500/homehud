<!--
  Single grocery item row.

  Checkbox + formatted label + drag affordance + delete button. Parent
  wraps this in the <li> that svelte-dnd-action tracks; we render a
  plain <div> here so the row isn't double-nested.
-->
<script lang="ts">
  import { Trash2, Check, GripVertical } from 'lucide-svelte';
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

<div
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

  <!-- Drag grip — the whole row is draggable, but the grip makes the
       affordance explicit so users don't have to guess. -->
  <span
    aria-hidden="true"
    class="flex size-6 shrink-0 cursor-grab items-center justify-center text-fg-muted/70 active:cursor-grabbing"
  >
    <GripVertical class="size-4" />
  </span>

  <button
    type="button"
    onclick={onDelete}
    aria-label="Remove {item.name}"
    class="flex size-9 shrink-0 items-center justify-center rounded-full text-fg-muted transition-opacity hover:bg-surface-muted hover:text-danger"
  >
    <Trash2 class="size-4" />
  </button>
</div>
