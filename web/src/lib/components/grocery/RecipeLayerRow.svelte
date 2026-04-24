<!--
  Horizontal strip of pills above the grocery list showing which recipes
  have contributed items. Tapping × asks for confirmation and removes
  every item that came from that recipe (while leaving other recipes'
  contributions and any manually-added items alone).
-->
<script lang="ts">
  import { X } from 'lucide-svelte';
  import type { GroceryRecipeLayer } from '$lib/api/grocery';
  import { removeRecipeLayerFromList } from '$lib/grocery/store';

  interface Props {
    layers: GroceryRecipeLayer[];
  }

  let { layers }: Props = $props();
  let busyId = $state<string | null>(null);

  async function onRemove(layer: GroceryRecipeLayer) {
    if (busyId) return;
    const ok = confirm(
      `Remove "${layer.recipe_name || 'this recipe'}"? Items it added will be pulled back from the list.`,
    );
    if (!ok) return;
    busyId = layer.recipe_id;
    try {
      await removeRecipeLayerFromList(layer.recipe_id);
    } finally {
      busyId = null;
    }
  }
</script>

{#if layers.length}
  <div class="flex flex-col gap-1">
    <span class="text-[0.65rem] font-semibold uppercase tracking-[0.08em] text-fg-muted">
      Recipes on this list
    </span>
    <div class="flex flex-wrap gap-1.5">
      {#each layers as layer (layer.recipe_id)}
        <span
          class="inline-flex items-center gap-1 rounded-full border border-accent/30 bg-accent/10 py-1 pl-3 pr-1 text-xs font-medium text-accent"
        >
          {layer.recipe_name || 'Untitled recipe'}
          <button
            type="button"
            onclick={() => onRemove(layer)}
            disabled={busyId === layer.recipe_id}
            aria-label={`Remove ${layer.recipe_name} from the list`}
            class="flex size-6 items-center justify-center rounded-full text-accent/70 transition-colors hover:bg-accent/20 hover:text-accent disabled:opacity-50"
          >
            <X class="size-3.5" />
          </button>
        </span>
      {/each}
    </div>
  </div>
{/if}
