<!--
  Session detail — header with session-level facts, then each exchange
  as a collapsible card with timeline, flags, phase breakdown, and LLM
  calls.
-->
<script lang="ts">
  import { ArrowLeft } from 'lucide-svelte';
  import type { PageData } from './$types';
  import ExchangeCard from '$lib/components/admin/ExchangeCard.svelte';
  import PhaseTimeline from '$lib/components/admin/PhaseTimeline.svelte';
  import { fmtMs, fmtTime } from '$lib/admin/format';

  let { data }: { data: PageData } = $props();
  const session = $derived(data.detail.session);
  const exchanges = $derived(data.detail.exchanges);

  const durationMs = $derived.by(() => {
    if (!session.started_at || !session.ended_at) return null;
    const t0 = new Date(session.started_at).getTime();
    const t1 = new Date(session.ended_at).getTime();
    if (!Number.isFinite(t0) || !Number.isFinite(t1)) return null;
    return t1 - t0;
  });
</script>

<div class="flex flex-col gap-4">
  <a
    href="/admin/sessions"
    class="flex w-fit items-center gap-1 text-sm text-fg-muted hover:text-fg"
  >
    <ArrowLeft class="size-4" />
    Sessions
  </a>

  <header class="flex flex-col gap-2">
    <h1 class="text-2xl font-semibold">Session</h1>
    <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-fg-muted">
      <span>
        Wake <strong class="font-mono text-fg">{session.wake_model || '—'}</strong>
      </span>
      <span>
        Started <strong class="font-mono text-fg">{fmtTime(session.started_at)}</strong>
      </span>
      <span>
        Ended <strong class="font-mono text-fg">{fmtTime(session.ended_at)}</strong>
      </span>
      <span>
        Duration <strong class="font-mono text-fg">{fmtMs(durationMs)}</strong>
      </span>
      <span>
        Exchanges <strong class="font-mono text-fg">{session.exchange_count}</strong>
      </span>
    </div>
  </header>

  {#if exchanges.length > 0}
    <div class="rounded-xl border border-border bg-surface p-3">
      <PhaseTimeline exchange={exchanges[0]} showLegend />
    </div>
  {/if}

  {#if exchanges.length === 0}
    <p class="rounded-xl border border-border bg-surface p-6 text-center text-sm text-fg-muted">
      No exchanges recorded.
    </p>
  {:else}
    <div class="flex flex-col gap-2">
      {#each exchanges as ex (ex.id)}
        <ExchangeCard exchange={ex} />
      {/each}
    </div>
  {/if}
</div>
