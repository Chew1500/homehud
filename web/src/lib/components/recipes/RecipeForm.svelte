<!--
  Shared recipe editor — used for both "new" and "edit" flows. Emits
  the parsed recipe payload via ``onSubmit``; the parent handles the
  actual create/update call plus navigation.
-->
<script lang="ts">
  import { Save, Loader2 } from 'lucide-svelte';
  import type { Recipe, RecipeCreateRequest, RecipeIngredient } from '$lib/api/recipes';
  import { formatIngredientLine, parseIngredientLine } from '$lib/recipes/parser';

  interface Props {
    /** Initial values. Can be a full Recipe or a partial parse result. */
    initial?: Partial<Recipe>;
    submitLabel?: string;
    onSubmit: (payload: RecipeCreateRequest) => Promise<void> | void;
  }

  let { initial = {}, submitLabel = 'Save recipe', onSubmit }: Props = $props();

  let name = $state(initial.name ?? '');
  let tagsText = $state((initial.tags ?? []).join(', '));
  let prep = $state(initial.prep_time_min ?? null);
  let cook = $state(initial.cook_time_min ?? null);
  let servings = $state(initial.servings ?? null);
  let ingredientsText = $state(
    (initial.ingredients ?? []).map(formatIngredientLine).join('\n'),
  );
  let directionsText = $state((initial.directions ?? []).join('\n'));

  let saving = $state(false);
  let errorMsg = $state<string | null>(null);

  async function handleSubmit(ev: SubmitEvent) {
    ev.preventDefault();
    if (saving) return;
    if (!name.trim()) {
      errorMsg = 'Name is required.';
      return;
    }
    errorMsg = null;
    saving = true;

    const tags = tagsText
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean);

    const ingredients: RecipeIngredient[] = ingredientsText
      .split('\n')
      .map(parseIngredientLine)
      .filter((x): x is RecipeIngredient => x !== null);

    const directions = directionsText
      .split('\n')
      .map((l) => l.trim())
      .filter(Boolean);

    const payload: RecipeCreateRequest = {
      name: name.trim(),
      tags,
      prep_time_min: prep ?? null,
      cook_time_min: cook ?? null,
      servings: servings ?? null,
      ingredients,
      directions,
      source: initial.source ?? 'manual',
      raw_text: initial.raw_text ?? '',
    };

    try {
      await onSubmit(payload);
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : 'Failed to save';
    } finally {
      saving = false;
    }
  }
</script>

<form onsubmit={handleSubmit} class="flex flex-col gap-4">
  <label class="flex flex-col gap-1">
    <span class="text-xs font-medium uppercase tracking-wide text-fg-muted">Name</span>
    <input
      type="text"
      bind:value={name}
      required
      autocomplete="off"
      class="rounded-lg border border-border bg-surface px-3 py-2.5 text-[1rem] text-fg focus:border-accent focus:outline-none"
    />
  </label>

  <label class="flex flex-col gap-1">
    <span class="text-xs font-medium uppercase tracking-wide text-fg-muted">
      Tags <span class="normal-case tracking-normal text-fg-muted/70">(comma separated)</span>
    </span>
    <input
      type="text"
      bind:value={tagsText}
      autocomplete="off"
      class="rounded-lg border border-border bg-surface px-3 py-2.5 text-[1rem] text-fg focus:border-accent focus:outline-none"
    />
  </label>

  <div class="grid grid-cols-3 gap-2">
    <label class="flex flex-col gap-1">
      <span class="text-xs font-medium uppercase tracking-wide text-fg-muted">Prep</span>
      <input
        type="number"
        min="0"
        inputmode="numeric"
        bind:value={prep}
        class="rounded-lg border border-border bg-surface px-3 py-2.5 text-[1rem] text-fg focus:border-accent focus:outline-none"
      />
    </label>
    <label class="flex flex-col gap-1">
      <span class="text-xs font-medium uppercase tracking-wide text-fg-muted">Cook</span>
      <input
        type="number"
        min="0"
        inputmode="numeric"
        bind:value={cook}
        class="rounded-lg border border-border bg-surface px-3 py-2.5 text-[1rem] text-fg focus:border-accent focus:outline-none"
      />
    </label>
    <label class="flex flex-col gap-1">
      <span class="text-xs font-medium uppercase tracking-wide text-fg-muted">Serves</span>
      <input
        type="number"
        min="1"
        inputmode="numeric"
        bind:value={servings}
        class="rounded-lg border border-border bg-surface px-3 py-2.5 text-[1rem] text-fg focus:border-accent focus:outline-none"
      />
    </label>
  </div>

  <label class="flex flex-col gap-1">
    <span class="text-xs font-medium uppercase tracking-wide text-fg-muted">
      Ingredients <span class="normal-case tracking-normal text-fg-muted/70">(one per line)</span>
    </span>
    <textarea
      bind:value={ingredientsText}
      rows="8"
      placeholder={'2 cups flour\n1 tsp salt\n3 eggs'}
      class="rounded-lg border border-border bg-surface px-3 py-2.5 font-mono text-sm text-fg focus:border-accent focus:outline-none"
    ></textarea>
  </label>

  <label class="flex flex-col gap-1">
    <span class="text-xs font-medium uppercase tracking-wide text-fg-muted">
      Directions <span class="normal-case tracking-normal text-fg-muted/70">(one step per line)</span>
    </span>
    <textarea
      bind:value={directionsText}
      rows="10"
      class="rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-fg focus:border-accent focus:outline-none"
    ></textarea>
  </label>

  {#if errorMsg}
    <p class="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
      {errorMsg}
    </p>
  {/if}

  <button
    type="submit"
    disabled={saving || !name.trim()}
    class="flex items-center justify-center gap-2 rounded-full bg-accent px-4 py-3 font-medium text-accent-fg transition-opacity disabled:opacity-40"
  >
    {#if saving}
      <Loader2 class="size-4 animate-spin" />
      Saving…
    {:else}
      <Save class="size-4" />
      {submitLabel}
    {/if}
  </button>
</form>
