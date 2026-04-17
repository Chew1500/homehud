<!--
  Config — dynamic registry-driven form.

  Groups render as collapsible sections. Each field tracks its own
  dirty state via ``dirtyValues`` (key → value); the sticky save bar
  POSTs the dirty map to /api/config and updates the originals on
  success so fields become "clean" again.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { AlertCircle, ChevronRight, RefreshCw, Save } from 'lucide-svelte';
  import {
    fetchConfig,
    saveConfig,
    type ConfigParam,
    type ConfigResponse,
  } from '$lib/api/config';
  import ConfigField from '$lib/components/admin/ConfigField.svelte';

  let data = $state<ConfigResponse | null>(null);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let saving = $state(false);
  let saveError = $state<string | null>(null);
  let savedBanner = $state(false);

  let originals = $state<Record<string, string | number | boolean | null>>({});
  let dirtyValues = $state<Record<string, string | number | boolean>>({});
  let collapsed = $state<Record<string, boolean>>({});

  async function load() {
    loading = true;
    loadError = null;
    try {
      const res = await fetchConfig();
      data = res;
      const orig: typeof originals = {};
      for (const p of res.params) orig[p.key] = p.value;
      originals = orig;
      dirtyValues = {};
      savedBanner = false;
    } catch (err) {
      loadError = err instanceof Error ? err.message : 'Failed to load config';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    load();
  });

  function handleChange(key: string, next: string | number | boolean) {
    const orig = originals[key];
    if (next === orig || String(next) === String(orig)) {
      // Return to clean state.
      const { [key]: _omit, ...rest } = dirtyValues;
      dirtyValues = rest;
    } else {
      dirtyValues = { ...dirtyValues, [key]: next };
    }
    savedBanner = false;
    saveError = null;
  }

  async function handleSave() {
    if (saving || Object.keys(dirtyValues).length === 0) return;
    saving = true;
    saveError = null;
    const payload: Record<string, string> = {};
    for (const [k, v] of Object.entries(dirtyValues)) {
      payload[k] =
        typeof v === 'boolean' ? (v ? 'true' : 'false') : String(v);
    }
    try {
      await saveConfig(payload);
      // Promote dirty values into originals so they're no longer "dirty".
      const nextOriginals = { ...originals };
      for (const [k, v] of Object.entries(dirtyValues)) nextOriginals[k] = v;
      originals = nextOriginals;
      dirtyValues = {};
      savedBanner = true;
    } catch (err) {
      saveError = err instanceof Error ? err.message : 'Save failed';
    } finally {
      saving = false;
    }
  }

  function handleDiscard() {
    dirtyValues = {};
    saveError = null;
  }

  function paramsInGroup(group: string): ConfigParam[] {
    return data?.params.filter((p) => p.group === group) ?? [];
  }

  function valueFor(p: ConfigParam): string | number | boolean | null {
    if (Object.prototype.hasOwnProperty.call(dirtyValues, p.key)) {
      return dirtyValues[p.key];
    }
    return originals[p.key] ?? null;
  }

  const dirtyCount = $derived(Object.keys(dirtyValues).length);
</script>

<div class="flex h-full flex-col gap-4">
  <header class="flex items-start justify-between gap-3">
    <div>
      <h1 class="text-2xl font-semibold">Config</h1>
      <p class="mt-1 text-sm text-fg-muted">
        Edit live parameters. Saving writes to <code class="font-mono">data/config.json</code>;
        most changes require a service restart.
      </p>
    </div>
    <button
      type="button"
      onclick={load}
      disabled={loading}
      aria-label="Reload config"
      class="flex size-9 items-center justify-center rounded-full border border-border text-fg-muted hover:bg-surface-muted hover:text-fg disabled:opacity-40"
    >
      <RefreshCw class="size-4 {loading ? 'animate-spin' : ''}" />
    </button>
  </header>

  {#if loadError}
    <div
      class="flex items-start gap-2 rounded-xl border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger"
    >
      <AlertCircle class="mt-0.5 size-4 shrink-0" />
      <span>{loadError}</span>
    </div>
  {/if}

  {#if savedBanner}
    <div class="rounded-xl border border-success/40 bg-success/10 px-3 py-2 text-sm text-success">
      Saved. Restart the service to apply most settings.
    </div>
  {/if}

  {#if data}
    <div class="flex flex-1 flex-col gap-3 overflow-y-auto pb-28">
      {#each data.groups as group (group)}
        {@const items = paramsInGroup(group)}
        {#if items.length > 0}
          {@const isCollapsed = collapsed[group] ?? false}
          <section class="overflow-hidden rounded-xl border border-border bg-surface">
            <button
              type="button"
              onclick={() => (collapsed = { ...collapsed, [group]: !isCollapsed })}
              aria-expanded={!isCollapsed}
              class="flex w-full items-center gap-2 px-4 py-3 text-left"
            >
              <ChevronRight
                class="size-4 shrink-0 text-fg-muted transition-transform {isCollapsed ? '' : 'rotate-90'}"
              />
              <span class="flex-1 text-sm font-semibold">{group}</span>
              <span class="text-xs text-fg-muted">{items.length}</span>
            </button>
            {#if !isCollapsed}
              <div class="border-t border-border px-4 pb-1">
                {#each items as p (p.key)}
                  <ConfigField
                    param={p}
                    value={valueFor(p)}
                    dirty={Object.prototype.hasOwnProperty.call(dirtyValues, p.key)}
                    onChange={(next) => handleChange(p.key, next)}
                  />
                {/each}
              </div>
            {/if}
          </section>
        {/if}
      {/each}
    </div>
  {/if}

  <!-- Sticky save bar -->
  {#if dirtyCount > 0}
    <div
      class="sticky bottom-0 -mx-4 flex items-center gap-3 border-t border-border bg-surface/95 px-4 py-3 backdrop-blur"
    >
      <span class="flex-1 text-sm text-fg-muted">
        {dirtyCount} unsaved change{dirtyCount === 1 ? '' : 's'}
      </span>
      {#if saveError}
        <span class="text-xs text-danger">{saveError}</span>
      {/if}
      <button
        type="button"
        onclick={handleDiscard}
        disabled={saving}
        class="rounded-full border border-border px-3 py-1.5 text-sm text-fg-muted hover:text-fg disabled:opacity-50"
      >
        Discard
      </button>
      <button
        type="button"
        onclick={handleSave}
        disabled={saving}
        class="flex items-center gap-1.5 rounded-full bg-accent px-4 py-1.5 text-sm font-medium text-accent-fg disabled:opacity-50"
      >
        {#if saving}
          <RefreshCw class="size-4 animate-spin" />
          Saving…
        {:else}
          <Save class="size-4" />
          Save {dirtyCount}
        {/if}
      </button>
    </div>
  {/if}
</div>
