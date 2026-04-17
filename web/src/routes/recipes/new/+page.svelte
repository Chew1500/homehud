<!--
  New recipe. Upload a photo (LLM parses it into form values) OR type
  manually. Both paths end at the same RecipeForm; the camera flow just
  seeds the initial values.
-->
<script lang="ts">
  import { ArrowLeft, Camera, Loader2, AlertCircle } from 'lucide-svelte';
  import { goto } from '$app/navigation';
  import RecipeForm from '$lib/components/recipes/RecipeForm.svelte';
  import { uploadRecipeImage, type RecipeCreateRequest } from '$lib/api/recipes';
  import { saveNewRecipe } from '$lib/recipes/store';

  let parsing = $state(false);
  let parseError = $state<string | null>(null);
  let initial = $state<Partial<RecipeCreateRequest>>({});
  let previewUrl = $state<string | null>(null);
  let fileInput: HTMLInputElement | undefined = $state();

  async function onFileSelect(ev: Event) {
    const input = ev.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    parseError = null;
    parsing = true;

    try {
      const dataUrl = await readAsDataUrl(file);
      previewUrl = dataUrl;
      const base64 = dataUrl.split(',')[1] ?? '';
      const mediaType = file.type || 'image/jpeg';
      const { recipe } = await uploadRecipeImage(base64, mediaType);
      initial = recipe;
    } catch (err) {
      parseError = err instanceof Error ? err.message : 'Failed to parse image';
    } finally {
      parsing = false;
    }
  }

  function readAsDataUrl(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result ?? ''));
      reader.onerror = () => reject(reader.error ?? new Error('Read failed'));
      reader.readAsDataURL(file);
    });
  }

  async function onSubmit(payload: RecipeCreateRequest) {
    const id = await saveNewRecipe(payload);
    await goto(`/recipes/${id}`, { replaceState: true });
  }
</script>

<div class="h-full overflow-y-auto">
  <div
    class="mx-auto flex w-full max-w-2xl flex-col gap-5 px-4 pb-8 pt-[max(1rem,env(safe-area-inset-top))]"
  >
    <a href="/recipes" class="flex w-fit items-center gap-1 text-sm text-fg-muted hover:text-fg">
      <ArrowLeft class="size-4" />
      Recipes
    </a>
    <h1 class="text-2xl font-semibold">New recipe</h1>

    <!-- Upload box -->
    <div class="flex flex-col gap-2 rounded-xl border border-dashed border-border bg-surface p-4">
      <div class="flex items-start gap-3">
        <Camera class="mt-1 size-5 shrink-0 text-accent" />
        <div class="flex-1">
          <p class="text-sm font-semibold">Scan from a photo</p>
          <p class="text-xs text-fg-muted">
            We'll extract the ingredients and directions for you to review before saving.
          </p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <button
          type="button"
          onclick={() => fileInput?.click()}
          disabled={parsing}
          class="flex items-center gap-2 rounded-full border border-accent/60 bg-accent/10 px-3 py-1.5 text-sm font-medium text-accent disabled:opacity-50"
        >
          {#if parsing}
            <Loader2 class="size-4 animate-spin" />
            Parsing…
          {:else}
            <Camera class="size-4" />
            Choose photo
          {/if}
        </button>
        <input
          bind:this={fileInput}
          type="file"
          accept="image/*"
          capture="environment"
          onchange={onFileSelect}
          class="hidden"
        />
      </div>
      {#if previewUrl}
        <img
          src={previewUrl}
          alt="Recipe preview"
          class="mt-2 max-h-64 w-full rounded-lg object-contain"
        />
      {/if}
      {#if parseError}
        <div
          class="mt-2 flex items-start gap-2 rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger"
        >
          <AlertCircle class="mt-0.5 size-4 shrink-0" />
          <span>{parseError}</span>
        </div>
      {/if}
    </div>

    <div class="flex items-center gap-2 text-xs uppercase tracking-wide text-fg-muted">
      <span class="h-px flex-1 bg-border"></span>
      <span>or enter manually</span>
      <span class="h-px flex-1 bg-border"></span>
    </div>

    {#key initial}
      <RecipeForm {initial} submitLabel="Save recipe" {onSubmit} />
    {/key}
  </div>
</div>
