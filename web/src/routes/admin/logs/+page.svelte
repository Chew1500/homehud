<!--
  Logs — terminal-feel viewer. Tails homehud.log with an optional level
  filter and a 10-second auto-refresh.
-->
<script lang="ts">
  import { onDestroy, onMount, tick } from 'svelte';
  import { AlertCircle, RefreshCw, Circle } from 'lucide-svelte';
  import { fetchLogs } from '$lib/api/logs';
  import type { LogEntry, LogLevel, LogsResponse } from '$lib/api/logs';

  const REFRESH_MS = 10_000;

  let level = $state<string>('INFO');
  let autoRefresh = $state(true);
  let loading = $state(false);
  let errorMsg = $state<string | null>(null);
  let data = $state<LogsResponse | null>(null);
  let lastLoadedAt = $state<Date | null>(null);
  let timer: ReturnType<typeof setInterval> | null = null;
  let scroller: HTMLDivElement | undefined = $state();

  function levelClass(lv: LogEntry['level']): string {
    switch (lv) {
      case 'CRITICAL':
      case 'ERROR':
        return 'text-danger';
      case 'WARNING':
        return 'text-warn';
      case 'DEBUG':
        return 'text-fg-muted';
      default:
        return 'text-fg';
    }
  }

  async function load() {
    loading = true;
    errorMsg = null;
    const wasAtBottom =
      scroller != null &&
      scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 30;
    try {
      const levelArg: LogLevel | null = level ? (level as LogLevel) : null;
      data = await fetchLogs({ lines: 200, level: levelArg });
      lastLoadedAt = new Date();
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : 'Failed to load logs';
    } finally {
      loading = false;
    }
    if (wasAtBottom) {
      await tick();
      if (scroller) scroller.scrollTop = scroller.scrollHeight;
    }
  }

  function stopTimer() {
    if (timer) clearInterval(timer);
    timer = null;
  }

  function startTimer() {
    stopTimer();
    if (autoRefresh) timer = setInterval(load, REFRESH_MS);
  }

  function toggleAutoRefresh() {
    autoRefresh = !autoRefresh;
    startTimer();
  }

  onMount(() => {
    startTimer();
    load();
  });

  onDestroy(stopTimer);
</script>

<div class="flex h-full flex-col gap-3">
  <header class="flex flex-wrap items-center justify-between gap-3">
    <div>
      <h1 class="text-2xl font-semibold">Logs</h1>
      <p class="mt-1 text-sm text-fg-muted">Tailing homehud.log (last 200 entries).</p>
    </div>
    <div class="flex items-center gap-2">
      <select
        bind:value={level}
        onchange={load}
        class="rounded-full border border-border bg-surface px-3 py-1.5 text-xs text-fg focus:border-accent focus:outline-none"
      >
        <option value="">All levels</option>
        <option value="DEBUG">DEBUG</option>
        <option value="INFO">INFO</option>
        <option value="WARNING">WARNING</option>
        <option value="ERROR">ERROR</option>
        <option value="CRITICAL">CRITICAL</option>
      </select>
      <button
        type="button"
        onclick={toggleAutoRefresh}
        aria-pressed={autoRefresh}
        class="flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs transition-colors {autoRefresh
          ? 'border-accent text-accent'
          : 'border-border text-fg-muted'}"
      >
        <Circle class="size-3 {autoRefresh ? 'fill-accent text-accent animate-pulse' : ''}" />
        <span>Tail {autoRefresh ? 'on' : 'off'}</span>
      </button>
      <button
        type="button"
        onclick={load}
        disabled={loading}
        aria-label="Refresh now"
        class="flex size-9 items-center justify-center rounded-full border border-border text-fg-muted hover:bg-surface-muted hover:text-fg disabled:opacity-40"
      >
        <RefreshCw class="size-4 {loading ? 'animate-spin' : ''}" />
      </button>
    </div>
  </header>

  {#if errorMsg}
    <div
      class="flex items-start gap-2 rounded-xl border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger"
    >
      <AlertCircle class="mt-0.5 size-4 shrink-0" />
      <span>{errorMsg}</span>
    </div>
  {/if}

  <div
    bind:this={scroller}
    class="min-h-0 flex-1 overflow-y-auto rounded-xl border border-border bg-bg p-2 font-mono text-[0.75rem] leading-snug"
  >
    {#if !data}
      <p class="p-4 text-center text-fg-muted">Loading…</p>
    {:else if data.message}
      <p class="p-4 text-center text-fg-muted">{data.message}</p>
    {:else if data.lines.length === 0}
      <p class="p-4 text-center text-fg-muted">No log entries match the current filter.</p>
    {:else}
      {#each data.lines as entry, i (i)}
        <div class="border-b border-border/30 py-1 last:border-b-0 whitespace-pre-wrap break-words">
          <span class="text-fg-muted">{entry.timestamp}</span>
          <span class="mx-2 font-semibold {levelClass(entry.level)}">{entry.level}</span>
          <span class="text-fg-muted">{entry.logger}:</span>
          <span class={levelClass(entry.level)}>{entry.message}</span>
        </div>
      {/each}
    {/if}
  </div>

  {#if data}
    <p class="text-xs text-fg-muted">
      <span class="font-mono">{data.total_lines}</span> entries
      {#if lastLoadedAt}
        · refreshed {lastLoadedAt.toLocaleTimeString()}
      {/if}
    </p>
  {/if}
</div>
