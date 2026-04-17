<!--
  ServiceCard — single monitored-service row.

  Status pill, editable name/URL (inline), test button, enable toggle,
  history drawer, and delete. All mutations bubble through the parent
  so the list can refetch canonically.
-->
<script lang="ts">
  import {
    ChevronDown,
    ChevronUp,
    Pencil,
    Power,
    Trash2,
    Zap,
  } from 'lucide-svelte';
  import type {
    HistoryCheck,
    MonitoredService,
    ServicePatch,
  } from '$lib/api/services';
  import UptimeBar from './UptimeBar.svelte';
  import { fmtRelative } from '$lib/admin/format';

  interface Props {
    service: MonitoredService;
    history?: HistoryCheck[];
    historyLoading?: boolean;
    onPatch: (patch: ServicePatch) => Promise<void> | void;
    onTest: () => Promise<{ is_up: boolean; response_time_ms: number | null; status_code: number | null; error: string | null } | null> | void;
    onDelete: () => Promise<void> | void;
    onLoadHistory: () => Promise<void> | void;
  }

  let {
    service,
    history = [],
    historyLoading = false,
    onPatch,
    onTest,
    onDelete,
    onLoadHistory,
  }: Props = $props();

  let showHistory = $state(false);
  let editing = $state<null | 'name' | 'url'>(null);
  let editValue = $state('');
  let testing = $state(false);
  let testMessage = $state<string | null>(null);
  let testTone = $state<'success' | 'danger' | 'muted'>('muted');

  function startEdit(field: 'name' | 'url') {
    editing = field;
    editValue = field === 'name' ? service.name : service.url;
  }

  async function commitEdit() {
    if (!editing) return;
    const next = editValue.trim();
    if (!next || next === (editing === 'name' ? service.name : service.url)) {
      editing = null;
      return;
    }
    const patch: ServicePatch = editing === 'name' ? { name: next } : { url: next };
    editing = null;
    await onPatch(patch);
  }

  function cancelEdit() {
    editing = null;
  }

  async function handleTest() {
    if (testing) return;
    testing = true;
    testMessage = 'Testing…';
    testTone = 'muted';
    const result = await onTest();
    testing = false;
    if (!result) {
      testMessage = 'Test failed';
      testTone = 'danger';
      return;
    }
    if (result.is_up) {
      const rt = result.response_time_ms != null ? ` · ${Math.round(result.response_time_ms)}ms` : '';
      const code = result.status_code ? ` · HTTP ${result.status_code}` : '';
      testMessage = `Reachable${rt}${code}`;
      testTone = 'success';
    } else {
      testMessage = `Unreachable: ${result.error ?? 'unknown error'}`;
      testTone = 'danger';
    }
    setTimeout(() => {
      testMessage = null;
    }, 5_000);
  }

  async function toggleHistory() {
    const next = !showHistory;
    showHistory = next;
    if (next && history.length === 0 && !historyLoading) {
      await onLoadHistory();
    }
  }

  const statusLabel = $derived.by(() => {
    if (!service.checked_at) return 'pending';
    return service.is_up === 1 ? 'up' : 'down';
  });

  const statusClass = $derived.by(() => {
    if (statusLabel === 'up') return 'bg-success/15 text-success';
    if (statusLabel === 'down') return 'bg-danger/15 text-danger';
    return 'bg-surface-muted text-fg-muted';
  });

  const testToneClass = $derived(
    testTone === 'success'
      ? 'text-success'
      : testTone === 'danger'
        ? 'text-danger'
        : 'text-fg-muted',
  );
</script>

<article
  class="flex flex-col gap-2 rounded-xl border border-border bg-surface p-3"
  class:opacity-60={!service.enabled}
>
  <div class="flex items-center gap-3">
    <span
      class="rounded-full px-2 py-0.5 text-[0.6rem] font-semibold uppercase tracking-wide {statusClass}"
    >
      {statusLabel}
    </span>

    <div class="flex flex-1 min-w-0 flex-col gap-0.5">
      {#if editing === 'name'}
        <input
          type="text"
          bind:value={editValue}
          onblur={commitEdit}
          onkeydown={(e) => {
            if (e.key === 'Enter') commitEdit();
            if (e.key === 'Escape') cancelEdit();
          }}
          class="rounded-md border border-accent bg-bg px-2 py-1 text-sm text-fg focus:outline-none"
        />
      {:else}
        <button
          type="button"
          onclick={() => startEdit('name')}
          aria-label="Edit name"
          class="flex items-center gap-1 text-left text-sm font-medium text-fg hover:text-accent"
        >
          <span class="truncate">{service.name}</span>
          <Pencil class="size-3 opacity-0 group-hover:opacity-100" />
        </button>
      {/if}
      {#if editing === 'url'}
        <input
          type="text"
          bind:value={editValue}
          onblur={commitEdit}
          onkeydown={(e) => {
            if (e.key === 'Enter') commitEdit();
            if (e.key === 'Escape') cancelEdit();
          }}
          class="rounded-md border border-accent bg-bg px-2 py-1 text-xs font-mono text-fg focus:outline-none"
        />
      {:else}
        <button
          type="button"
          onclick={() => startEdit('url')}
          aria-label="Edit URL"
          class="truncate text-left font-mono text-xs text-fg-muted hover:text-accent"
        >
          {service.url}
        </button>
      {/if}
    </div>

    <div class="flex shrink-0 items-center gap-1">
      <button
        type="button"
        onclick={handleTest}
        disabled={testing}
        aria-label="Test now"
        class="flex size-8 items-center justify-center rounded-full text-fg-muted hover:bg-surface-muted hover:text-fg disabled:opacity-40"
        title="Test now"
      >
        <Zap class="size-4" />
      </button>
      <button
        type="button"
        onclick={() => onPatch({ enabled: !service.enabled })}
        aria-label={service.enabled ? 'Disable' : 'Enable'}
        class="flex size-8 items-center justify-center rounded-full text-fg-muted hover:bg-surface-muted hover:text-fg"
        title={service.enabled ? 'Disable' : 'Enable'}
      >
        <Power class="size-4" />
      </button>
      <button
        type="button"
        onclick={toggleHistory}
        aria-label="Toggle history"
        class="flex size-8 items-center justify-center rounded-full text-fg-muted hover:bg-surface-muted hover:text-fg"
        title="30-day history"
      >
        {#if showHistory}
          <ChevronUp class="size-4" />
        {:else}
          <ChevronDown class="size-4" />
        {/if}
      </button>
      <button
        type="button"
        onclick={onDelete}
        aria-label="Delete service"
        class="flex size-8 items-center justify-center rounded-full text-fg-muted hover:bg-danger/10 hover:text-danger"
        title="Remove"
      >
        <Trash2 class="size-4" />
      </button>
    </div>
  </div>

  <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-fg-muted">
    <span>
      Type <strong class="font-mono text-fg uppercase">{service.check_type}</strong>
    </span>
    <span>
      Response
      <strong class="font-mono text-fg">
        {service.response_time_ms != null ? `${Math.round(service.response_time_ms)} ms` : '—'}
      </strong>
    </span>
    <span>
      Uptime
      <strong class="font-mono text-fg">
        {service.uptime_pct != null ? `${service.uptime_pct}%` : '—'}
      </strong>
    </span>
    <span>Checked {fmtRelative(service.checked_at)}</span>
    {#if !service.enabled}
      <span class="rounded-full bg-surface-muted px-2 py-0.5 font-semibold uppercase tracking-wide">
        disabled
      </span>
    {/if}
  </div>

  {#if testMessage}
    <p class="text-xs {testToneClass}">{testMessage}</p>
  {/if}

  {#if showHistory}
    <div class="border-t border-border pt-2">
      {#if historyLoading}
        <p class="text-xs text-fg-muted">Loading history…</p>
      {:else}
        <UptimeBar checks={history} />
      {/if}
    </div>
  {/if}
</article>
