<!--
  Edit an existing recipe. Delegates to <RecipeForm> with the current
  values pre-filled.
-->
<script lang="ts">
  import { ArrowLeft } from 'lucide-svelte';
  import { goto } from '$app/navigation';
  import type { PageData } from './$types';
  import RecipeForm from '$lib/components/recipes/RecipeForm.svelte';
  import { saveRecipePatch } from '$lib/recipes/store';

  let { data }: { data: PageData } = $props();
  const recipe = $derived(data.recipe);

  async function onSubmit(payload: Parameters<typeof saveRecipePatch>[1]) {
    await saveRecipePatch(recipe.id, payload);
    await goto(`/recipes/${recipe.id}`, { replaceState: true });
  }
</script>

<div class="h-full overflow-y-auto">
  <div
    class="mx-auto flex w-full max-w-2xl flex-col gap-4 px-4 pb-8 pt-[max(1rem,env(safe-area-inset-top))]"
  >
    <a
      href="/recipes/{recipe.id}"
      class="flex w-fit items-center gap-1 text-sm text-fg-muted hover:text-fg"
    >
      <ArrowLeft class="size-4" />
      Back
    </a>
    <h1 class="text-2xl font-semibold">Edit recipe</h1>
    <RecipeForm initial={recipe} submitLabel="Save changes" {onSubmit} />
  </div>
</div>
