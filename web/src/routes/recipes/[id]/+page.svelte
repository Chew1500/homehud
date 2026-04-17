<!--
  Recipe detail. Ingredients + directions, Cook Mode toggle (Wake Lock
  API to keep the screen on), and Edit/Delete actions.
-->
<script lang="ts">
  import { onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    ArrowLeft, Clock, Users, Utensils, Pencil, Trash2,
    FlameKindling, AlertCircle,
  } from 'lucide-svelte';
  import type { PageData } from './$types';
  import { displayIngredient } from '$lib/recipes/parser';
  import { removeRecipe } from '$lib/recipes/store';
  import { disableWakeLock, enableWakeLock, wakeLockState } from '$lib/recipes/wake-lock';

  let { data }: { data: PageData } = $props();
  const recipe = $derived(data.recipe);

  let deleting = $state(false);
  let errorMsg = $state<string | null>(null);

  const cookMode = $derived($wakeLockState.locked);
  const cookModeSupported = $derived($wakeLockState.supported);

  async function toggleCookMode() {
    if (cookMode) await disableWakeLock();
    else await enableWakeLock();
  }

  async function onDelete() {
    if (deleting) return;
    if (!confirm(`Delete "${recipe.name}"? This cannot be undone.`)) return;
    deleting = true;
    try {
      await removeRecipe(recipe.id);
      await goto('/recipes', { replaceState: true });
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : 'Delete failed';
      deleting = false;
    }
  }

  onDestroy(() => {
    // Always release the wake lock when leaving the detail page.
    void disableWakeLock();
  });

  const totalMin = $derived(
    (recipe.prep_time_min ?? 0) + (recipe.cook_time_min ?? 0) || null,
  );
</script>

<div class="h-full overflow-y-auto" class:bg-bg={!cookMode} class:bg-surface={cookMode}>
  <div
    class="mx-auto flex w-full max-w-2xl flex-col gap-5 px-4 pb-8 pt-[max(1rem,env(safe-area-inset-top))]"
  >
    <!-- Back -->
    <a
      href="/recipes"
      class="flex w-fit items-center gap-1 text-sm text-fg-muted hover:text-fg"
    >
      <ArrowLeft class="size-4" />
      Recipes
    </a>

    <!-- Hero -->
    <header class="flex flex-col gap-2">
      <h1 class="text-3xl font-semibold leading-tight text-fg">{recipe.name}</h1>
      {#if recipe.tags?.length}
        <div class="flex flex-wrap gap-1">
          {#each recipe.tags as tag (tag)}
            <span
              class="rounded-full bg-accent/10 px-2 py-0.5 text-xs font-medium uppercase tracking-wide text-accent"
            >
              {tag}
            </span>
          {/each}
        </div>
      {/if}
      {#if totalMin || recipe.servings || recipe.prep_time_min || recipe.cook_time_min}
        <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-fg-muted">
          {#if recipe.prep_time_min}
            <span class="flex items-center gap-1">
              <Clock class="size-4" />
              {recipe.prep_time_min} min prep
            </span>
          {/if}
          {#if recipe.cook_time_min}
            <span class="flex items-center gap-1">
              <Utensils class="size-4" />
              {recipe.cook_time_min} min cook
            </span>
          {/if}
          {#if recipe.servings}
            <span class="flex items-center gap-1">
              <Users class="size-4" />
              Serves {recipe.servings}
            </span>
          {/if}
        </div>
      {/if}
    </header>

    <!-- Cook mode toggle -->
    {#if cookModeSupported}
      <button
        type="button"
        onclick={toggleCookMode}
        class="flex items-center justify-between gap-3 rounded-xl border px-4 py-3 text-left transition-colors"
        class:border-accent={cookMode}
        class:bg-accent={cookMode}
        class:text-accent-fg={cookMode}
        class:border-border={!cookMode}
        class:bg-surface={!cookMode}
      >
        <div class="flex items-center gap-3">
          <FlameKindling class="size-5 shrink-0" />
          <div>
            <p class="text-sm font-semibold">Cook mode</p>
            <p class="text-xs opacity-80">
              {cookMode
                ? 'Screen will stay on while you cook.'
                : 'Keep the screen awake while following this recipe.'}
            </p>
          </div>
        </div>
        <span
          class="flex h-6 w-11 items-center rounded-full border p-0.5 transition-colors"
          class:border-accent-fg={cookMode}
          class:border-border={!cookMode}
        >
          <span
            class="size-4 rounded-full transition-transform"
            class:translate-x-5={cookMode}
            class:bg-accent-fg={cookMode}
            class:bg-fg-muted={!cookMode}
          ></span>
        </span>
      </button>
    {/if}

    {#if errorMsg}
      <div
        class="flex items-start gap-2 rounded-xl border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger"
      >
        <AlertCircle class="mt-0.5 size-4 shrink-0" />
        <span>{errorMsg}</span>
      </div>
    {/if}

    <!-- Ingredients -->
    <section class="flex flex-col gap-2">
      <h2 class="text-xs font-semibold uppercase tracking-[0.08em] text-fg-muted">
        Ingredients
      </h2>
      {#if recipe.ingredients?.length}
        <ul class="flex flex-col gap-1">
          {#each recipe.ingredients as ing, i (i)}
            <li class="flex items-baseline gap-2 text-[0.95rem] leading-relaxed">
              <span class="select-none text-accent">•</span>
              <span>{displayIngredient(ing)}</span>
            </li>
          {/each}
        </ul>
      {:else}
        <p class="text-sm text-fg-muted">No ingredients listed.</p>
      {/if}
    </section>

    <!-- Directions -->
    <section class="flex flex-col gap-2">
      <h2 class="text-xs font-semibold uppercase tracking-[0.08em] text-fg-muted">
        Directions
      </h2>
      {#if recipe.directions?.length}
        <ol class="flex flex-col gap-3">
          {#each recipe.directions as step, i (i)}
            <li class="flex gap-3 text-[0.95rem] leading-relaxed">
              <span
                class="flex size-7 shrink-0 items-center justify-center rounded-full bg-accent/10 font-mono text-xs font-semibold text-accent"
              >
                {i + 1}
              </span>
              <span>{step}</span>
            </li>
          {/each}
        </ol>
      {:else}
        <p class="text-sm text-fg-muted">No directions listed.</p>
      {/if}
    </section>

    <!-- Actions -->
    <div class="flex gap-2 pt-4">
      <a
        href="/recipes/{recipe.id}/edit"
        class="flex flex-1 items-center justify-center gap-2 rounded-full border border-border bg-surface px-4 py-2.5 text-sm font-medium text-fg hover:bg-surface-muted"
      >
        <Pencil class="size-4" />
        Edit
      </a>
      <button
        type="button"
        onclick={onDelete}
        disabled={deleting}
        class="flex flex-1 items-center justify-center gap-2 rounded-full border border-danger/40 bg-danger/5 px-4 py-2.5 text-sm font-medium text-danger hover:bg-danger/10 disabled:opacity-50"
      >
        <Trash2 class="size-4" />
        {deleting ? 'Deleting…' : 'Delete'}
      </button>
    </div>
  </div>
</div>
