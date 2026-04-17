<!--
  Recipes list. Card grid with search + "+ Upload" entry point.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { Plus, Search, AlertCircle } from 'lucide-svelte';
  import RecipeCard from '$lib/components/recipes/RecipeCard.svelte';
  import { loadRecipes, recipes, clearRecipeError } from '$lib/recipes/store';

  let query = $state('');
  const state = $derived($recipes);

  const filtered = $derived.by(() => {
    const q = query.trim().toLowerCase();
    if (!q) return state.items;
    return state.items.filter(
      (r) =>
        r.name.toLowerCase().includes(q) ||
        (r.tags ?? []).some((t) => t.toLowerCase().includes(q)),
    );
  });

  onMount(() => {
    loadRecipes();
  });
</script>

<div class="h-full overflow-y-auto">
  <div
    class="mx-auto flex w-full max-w-xl flex-col gap-4 px-4 pb-6 pt-[max(1rem,env(safe-area-inset-top))]"
  >
    <header class="flex items-center justify-between gap-2">
      <h1 class="text-2xl font-semibold">Recipes</h1>
      <a
        href="/recipes/new"
        class="flex items-center gap-1.5 rounded-full bg-accent px-3 py-1.5 text-sm font-medium text-accent-fg"
      >
        <Plus class="size-4" />
        <span>New</span>
      </a>
    </header>

    <label class="flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-2">
      <Search class="size-4 shrink-0 text-fg-muted" />
      <input
        type="search"
        bind:value={query}
        placeholder="Search by name or tag…"
        class="flex-1 bg-transparent text-[1rem] text-fg placeholder:text-fg-muted focus:outline-none"
      />
    </label>

    {#if state.error}
      <div
        class="flex items-start gap-2 rounded-xl border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger"
      >
        <AlertCircle class="mt-0.5 size-4 shrink-0" />
        <div class="flex-1">{state.error}</div>
        <button
          type="button"
          onclick={clearRecipeError}
          class="text-xs opacity-70 hover:opacity-100">dismiss</button
        >
      </div>
    {/if}

    {#if !state.initialised}
      <p class="py-8 text-center text-sm text-fg-muted">Loading…</p>
    {:else if state.items.length === 0}
      <div class="flex flex-col items-center gap-2 py-12 text-center">
        <p class="text-base text-fg">No recipes yet.</p>
        <p class="text-sm text-fg-muted">
          Tap <span class="font-medium text-fg">New</span> to add one — or upload a photo of a recipe and
          we'll transcribe it.
        </p>
      </div>
    {:else if filtered.length === 0}
      <p class="py-8 text-center text-sm text-fg-muted">
        No recipes match "{query}".
      </p>
    {:else}
      <div class="flex flex-col gap-2">
        {#each filtered as recipe (recipe.id)}
          <RecipeCard {recipe} />
        {/each}
      </div>
    {/if}
  </div>
</div>
