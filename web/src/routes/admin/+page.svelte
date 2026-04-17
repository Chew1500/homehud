<!--
  Admin overview — KPI cards, phase performance, breakdown lists, and
  the current display snapshot.
-->
<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { AlertCircle, RefreshCw } from 'lucide-svelte';
  import StatCard from '$lib/components/admin/StatCard.svelte';
  import BreakdownList from '$lib/components/admin/BreakdownList.svelte';
  import PhaseTable from '$lib/components/admin/PhaseTable.svelte';
  import { fetchDisplayImageUrl, fetchStats, type StatsResponse } from '$lib/api/stats';
  import { fmtInt, fmtTime } from '$lib/admin/format';

  let stats = $state<StatsResponse | null>(null);
  let statsError = $state<string | null>(null);
  let loading = $state(true);

  let displayUrl = $state<string | null>(null);
  let displayLoadedAt = $state<Date | null>(null);

  async function refresh() {
    loading = true;
    statsError = null;
    try {
      stats = await fetchStats();
    } catch (err) {
      statsError = err instanceof Error ? err.message : 'Failed to load stats';
    } finally {
      loading = false;
    }

    // Release the previous object URL before overwriting it.
    if (displayUrl) URL.revokeObjectURL(displayUrl);
    displayUrl = await fetchDisplayImageUrl();
    displayLoadedAt = displayUrl ? new Date() : null;
  }

  onMount(() => {
    refresh();
  });

  onDestroy(() => {
    if (displayUrl) URL.revokeObjectURL(displayUrl);
  });

  const totalTokens = $derived(
    stats ? (stats.total_input_tokens ?? 0) + (stats.total_output_tokens ?? 0) : 0,
  );
</script>

<div class="flex flex-col gap-5">
  <header class="flex items-start justify-between gap-3">
    <div>
      <h1 class="text-2xl font-semibold">Overview</h1>
      <p class="mt-1 text-sm text-fg-muted">
        Aggregate telemetry across all sessions.
      </p>
    </div>
    <button
      type="button"
      onclick={refresh}
      disabled={loading}
      aria-label="Refresh stats"
      class="flex size-9 items-center justify-center rounded-full border border-border text-fg-muted transition-colors hover:bg-surface-muted hover:text-fg disabled:opacity-40"
    >
      <RefreshCw class="size-4 {loading ? 'animate-spin' : ''}" />
    </button>
  </header>

  {#if statsError}
    <div
      class="flex items-start gap-2 rounded-xl border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger"
    >
      <AlertCircle class="mt-0.5 size-4 shrink-0" />
      <span>{statsError}</span>
    </div>
  {/if}

  {#if stats}
    <!-- KPI grid -->
    <section class="grid grid-cols-2 gap-2 md:grid-cols-4">
      <StatCard label="Sessions" value={fmtInt(stats.total_sessions)} />
      <StatCard label="Exchanges" value={fmtInt(stats.total_exchanges)} />
      <StatCard label="LLM calls" value={fmtInt(stats.total_llm_calls)} />
      <StatCard
        label="Tokens"
        value={fmtInt(totalTokens)}
        subtitle="{fmtInt(stats.total_input_tokens)} in · {fmtInt(stats.total_output_tokens)} out"
      />
      <StatCard
        label="Errors"
        value={fmtInt(stats.error_count)}
        tone={stats.error_count > 0 ? 'danger' : 'neutral'}
      />
      <StatCard
        label="Rejected"
        value={fmtInt(stats.rejected_count)}
        tone={stats.rejected_count > 0 ? 'danger' : 'neutral'}
      />
      <StatCard
        label="Today"
        value={fmtInt(stats.sessions_today)}
        subtitle="{fmtInt(stats.exchanges_today)} exchanges"
      />
    </section>

    <!-- Phase performance -->
    <PhaseTable {stats} />

    <!-- Breakdowns -->
    <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
      <BreakdownList title="Features" data={stats.feature_counts} />
      <BreakdownList title="Routing paths" data={stats.routing_counts} />
    </div>
  {/if}

  <!-- Display preview -->
  <section class="flex flex-col gap-2 rounded-xl border border-border bg-surface p-4">
    <h3 class="text-xs font-semibold uppercase tracking-[0.08em] text-fg-muted">
      Display preview
    </h3>
    {#if displayUrl}
      <img
        src={displayUrl}
        alt="Current e-ink display"
        class="w-full rounded-lg border border-border bg-bg"
      />
      {#if displayLoadedAt}
        <p class="text-xs text-fg-muted">Last refreshed: {fmtTime(displayLoadedAt.toISOString())}</p>
      {/if}
    {:else if !loading}
      <p class="py-6 text-center text-sm text-fg-muted">
        No display snapshot available.
      </p>
    {/if}
  </section>
</div>
