<!--
  RecipeCard — grid tile used on the list view.

  Clicking navigates to ``/recipes/[id]``. Meta line is rendered
  compactly on mobile.
-->
<script lang="ts">
  import { Clock, Users } from 'lucide-svelte';
  import type { Recipe } from '$lib/api/recipes';

  interface Props {
    recipe: Recipe;
  }

  let { recipe }: Props = $props();

  const totalMin = $derived(
    (recipe.prep_time_min ?? 0) + (recipe.cook_time_min ?? 0) || null,
  );
</script>

<a
  href="/recipes/{recipe.id}"
  class="flex flex-col gap-2 rounded-xl border border-border bg-surface p-4 transition-colors hover:border-accent/60 hover:bg-surface-muted"
>
  <h3 class="text-base font-semibold leading-tight text-fg">{recipe.name}</h3>

  {#if recipe.tags?.length}
    <div class="flex flex-wrap gap-1">
      {#each recipe.tags as tag (tag)}
        <span
          class="rounded-full bg-accent/10 px-2 py-0.5 text-[0.65rem] font-medium uppercase tracking-wide text-accent"
        >
          {tag}
        </span>
      {/each}
    </div>
  {/if}

  {#if totalMin || recipe.servings}
    <div class="flex items-center gap-3 text-xs text-fg-muted">
      {#if totalMin}
        <span class="flex items-center gap-1">
          <Clock class="size-3" />
          {totalMin} min
        </span>
      {/if}
      {#if recipe.servings}
        <span class="flex items-center gap-1">
          <Users class="size-3" />
          Serves {recipe.servings}
        </span>
      {/if}
    </div>
  {/if}
</a>
