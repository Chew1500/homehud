<!--
  Sessions list — paginated summary of voice sessions. Tap a row to
  open the detail view.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { AlertCircle, RefreshCw, AlertTriangle } from 'lucide-svelte';
  import Pagination from '$lib/components/admin/Pagination.svelte';
  import { fetchSessions, type SessionListResponse } from '$lib/api/sessions';
  import { fmtMs, fmtRelative } from '$lib/admin/format';

  const PAGE_SIZE = 25;

  let data = $state<SessionListResponse | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  const offset = $derived.by(() => {
    const raw = $page.url.searchParams.get('offset');
    const parsed = raw != null ? Number(raw) : 0;
    return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
  });

  async function load() {
    loading = true;
    error = null;
    try {
      data = await fetchSessions(PAGE_SIZE, offset);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load sessions';
    } finally {
      loading = false;
    }
  }

  // Re-fetch whenever the offset changes in the URL.
  $effect(() => {
    void offset;
    load();
  });

  onMount(() => {
    load();
  });

  async function onPage(newOffset: number) {
    const qs = new URLSearchParams();
    if (newOffset > 0) qs.set('offset', String(newOffset));
    await goto(`/admin/sessions${qs.size ? `?${qs.toString()}` : ''}`);
  }
</script>

<div class="flex flex-col gap-4">
  <header class="flex items-start justify-between gap-3">
    <div>
      <h1 class="text-2xl font-semibold">Sessions</h1>
      <p class="mt-1 text-sm text-fg-muted">
        Each wake-word activation, with per-exchange telemetry.
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

  {#if data}
    {#if data.sessions.length === 0}
      <p class="rounded-xl border border-border bg-surface p-6 text-center text-sm text-fg-muted">
        No sessions yet.
      </p>
    {:else}
      <ul class="flex flex-col gap-1.5">
        {#each data.sessions as s (s.id)}
          <li>
            <a
              href="/admin/sessions/{s.id}"
              class="flex items-center gap-3 rounded-xl border border-border bg-surface px-3 py-2.5 transition-colors hover:border-accent/60 hover:bg-surface-muted"
            >
              <div class="flex flex-1 min-w-0 flex-col gap-0.5">
                <div class="flex items-center gap-2">
                  <span class="truncate text-sm text-fg">
                    {s.first_transcription || '(no transcription)'}
                  </span>
                  {#if s.had_error}
                    <AlertTriangle class="size-3.5 shrink-0 text-danger" />
                  {/if}
                </div>
                <div class="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-fg-muted">
                  <span>{fmtRelative(s.started_at)}</span>
                  <span class="font-mono">{s.exchange_count}× exchange</span>
                  <span class="font-mono">{fmtMs(s.duration_ms)}</span>
                  {#if s.features_used.length}
                    <span class="flex flex-wrap gap-1">
                      {#each s.features_used as f (f)}
                        <span
                          class="rounded-full bg-accent/10 px-1.5 py-0.5 text-[0.6rem] font-semibold uppercase tracking-wide text-accent"
                        >
                          {f}
                        </span>
                      {/each}
                    </span>
                  {/if}
                </div>
              </div>
            </a>
          </li>
        {/each}
      </ul>

      <Pagination
        total={data.total}
        limit={data.limit}
        offset={data.offset}
        {onPage}
        label="sessions"
      />
    {/if}
  {:else if loading}
    <p class="py-8 text-center text-sm text-fg-muted">Loading…</p>
  {/if}
</div>
