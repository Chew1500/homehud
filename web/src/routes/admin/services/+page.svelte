<!--
  Services — monitoring list with per-row test/enable/edit/delete and a
  30-day uptime drawer. An "Add service" bottom section creates new
  monitors (with a Test button for pre-validation).
-->
<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { AlertCircle, Plus, RefreshCw } from 'lucide-svelte';
  import ServiceCard from '$lib/components/admin/ServiceCard.svelte';
  import {
    addService,
    deleteService,
    fetchServiceHistory,
    fetchServices,
    testService,
    updateService,
    type CheckType,
    type HistoryCheck,
    type MonitorListResponse,
  } from '$lib/api/services';

  let data = $state<MonitorListResponse | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let histories = $state<Record<number, HistoryCheck[]>>({});
  let historyLoading = $state<Record<number, boolean>>({});

  let newName = $state('');
  let newUrl = $state('');
  let newType = $state<CheckType>('http');
  let adding = $state(false);
  let addError = $state<string | null>(null);
  let addTestMsg = $state<string | null>(null);
  let addTestTone = $state<'success' | 'danger' | 'muted'>('muted');

  let refreshTimer: ReturnType<typeof setInterval> | null = null;

  async function load() {
    loading = true;
    error = null;
    try {
      data = await fetchServices();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load services';
    } finally {
      loading = false;
    }
  }

  async function reloadHistory(id: number) {
    historyLoading = { ...historyLoading, [id]: true };
    try {
      const res = await fetchServiceHistory(id, 30);
      histories = { ...histories, [id]: res.checks };
    } catch {
      /* leave history untouched */
    } finally {
      historyLoading = { ...historyLoading, [id]: false };
    }
  }

  async function patchService(id: number, patch: Parameters<typeof updateService>[1]) {
    try {
      await updateService(id, patch);
      await load();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Update failed';
    }
  }

  async function removeService(id: number) {
    if (!confirm('Remove this service and its history? This cannot be undone.')) return;
    try {
      await deleteService(id);
      await load();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Delete failed';
    }
  }

  async function runTest(url: string, checkType: CheckType) {
    try {
      return await testService(url, checkType);
    } catch {
      return null;
    }
  }

  async function handleAdd() {
    addError = null;
    const name = newName.trim();
    const url = newUrl.trim();
    if (!name || !url) {
      addError = 'Name and URL are required.';
      return;
    }
    adding = true;
    try {
      await addService(name, url, newType);
      newName = '';
      newUrl = '';
      newType = 'http';
      addTestMsg = null;
      await load();
    } catch (err) {
      addError = err instanceof Error ? err.message : 'Failed to add';
    } finally {
      adding = false;
    }
  }

  async function handleTestNew() {
    if (!newUrl.trim()) {
      addTestMsg = 'Enter a URL first.';
      addTestTone = 'danger';
      return;
    }
    addTestMsg = 'Testing…';
    addTestTone = 'muted';
    const result = await runTest(newUrl.trim(), newType);
    if (!result) {
      addTestMsg = 'Test failed.';
      addTestTone = 'danger';
      return;
    }
    if (result.is_up) {
      const rt = result.response_time_ms != null ? ` · ${Math.round(result.response_time_ms)}ms` : '';
      const code = result.status_code ? ` · HTTP ${result.status_code}` : '';
      addTestMsg = `Reachable${rt}${code}`;
      addTestTone = 'success';
    } else {
      addTestMsg = `Unreachable: ${result.error ?? 'unknown error'}`;
      addTestTone = 'danger';
    }
  }

  onMount(() => {
    load();
    refreshTimer = setInterval(load, 60_000);
  });

  onDestroy(() => {
    if (refreshTimer) clearInterval(refreshTimer);
  });

  const addTestToneClass = $derived(
    addTestTone === 'success'
      ? 'text-success'
      : addTestTone === 'danger'
        ? 'text-danger'
        : 'text-fg-muted',
  );
</script>

<div class="flex flex-col gap-4">
  <header class="flex items-start justify-between gap-3">
    <div>
      <h1 class="text-2xl font-semibold">Services</h1>
      <p class="mt-1 text-sm text-fg-muted">
        HTTP / ping uptime monitors. Refreshes every minute.
      </p>
    </div>
    <button
      type="button"
      onclick={load}
      disabled={loading}
      aria-label="Refresh"
      class="flex size-9 items-center justify-center rounded-full border border-border text-fg-muted hover:bg-surface-muted hover:text-fg disabled:opacity-40"
    >
      <RefreshCw class="size-4 {loading ? 'animate-spin' : ''}" />
    </button>
  </header>

  {#if error}
    <div
      class="flex items-start gap-2 rounded-xl border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger"
    >
      <AlertCircle class="mt-0.5 size-4 shrink-0" />
      <span>{error}</span>
    </div>
  {/if}

  {#if data && !data.monitoring_enabled}
    <div class="rounded-xl border border-border bg-surface p-4 text-sm text-fg-muted">
      Service monitoring is disabled. Turn on
      <code class="font-mono text-fg">monitor_enabled</code>
      in the Config tab.
    </div>
  {:else if data}
    {#if data.services.length === 0}
      <p class="rounded-xl border border-border bg-surface p-6 text-center text-sm text-fg-muted">
        No services configured yet.
      </p>
    {:else}
      <div class="flex flex-col gap-2">
        {#each data.services as svc (svc.id)}
          <ServiceCard
            service={svc}
            history={histories[svc.id] ?? []}
            historyLoading={historyLoading[svc.id] ?? false}
            onPatch={(patch) => patchService(svc.id, patch)}
            onTest={() => runTest(svc.url, svc.check_type)}
            onDelete={() => removeService(svc.id)}
            onLoadHistory={() => reloadHistory(svc.id)}
          />
        {/each}
      </div>
    {/if}

    <!-- Add new -->
    <section class="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4">
      <h2 class="text-xs font-semibold uppercase tracking-[0.08em] text-fg-muted">
        Add service
      </h2>
      <div class="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_2fr_auto]">
        <input
          type="text"
          bind:value={newName}
          placeholder="Name"
          disabled={adding}
          class="rounded-lg border border-border bg-bg px-3 py-2 text-sm text-fg focus:border-accent focus:outline-none"
        />
        <input
          type="text"
          bind:value={newUrl}
          placeholder="http://192.168.1.1 or 192.168.1.1"
          autocomplete="off"
          spellcheck="false"
          disabled={adding}
          class="rounded-lg border border-border bg-bg px-3 py-2 font-mono text-sm text-fg focus:border-accent focus:outline-none"
        />
        <select
          bind:value={newType}
          disabled={adding}
          class="rounded-lg border border-border bg-bg px-3 py-2 text-sm text-fg focus:border-accent focus:outline-none"
        >
          <option value="http">HTTP</option>
          <option value="ping">Ping</option>
        </select>
      </div>
      <div class="flex items-center gap-2">
        <button
          type="button"
          onclick={handleAdd}
          disabled={adding || !newName.trim() || !newUrl.trim()}
          class="flex items-center gap-1.5 rounded-full bg-accent px-3 py-1.5 text-sm font-medium text-accent-fg disabled:opacity-50"
        >
          <Plus class="size-4" />
          Add
        </button>
        <button
          type="button"
          onclick={handleTestNew}
          class="rounded-full border border-border px-3 py-1.5 text-sm text-fg-muted hover:text-fg"
        >
          Test
        </button>
        {#if addTestMsg}
          <span class="text-xs {addTestToneClass}">{addTestMsg}</span>
        {/if}
      </div>
      {#if addError}
        <p class="text-xs text-danger">{addError}</p>
      {/if}
    </section>
  {/if}
</div>
