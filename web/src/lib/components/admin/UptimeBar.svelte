<!--
  UptimeBar — thin horizontal strip of up/down segments for the last
  N checks. Uses CSS gradients instead of canvas so it scales cleanly
  across DPI and pairs naturally with our colour tokens.
-->
<script lang="ts">
  import type { HistoryCheck } from '$lib/api/services';

  interface Props {
    checks: HistoryCheck[];
    height?: string;
  }

  let { checks, height = '36px' }: Props = $props();

  const segments = $derived(
    checks.map((c) => ({
      up: c.is_up === 1,
      checkedAt: c.checked_at,
      responseMs: c.response_time_ms,
    })),
  );

  const upCount = $derived(segments.filter((s) => s.up).length);
  const uptimePct = $derived(
    segments.length > 0 ? (upCount / segments.length) * 100 : 0,
  );
</script>

<div class="flex flex-col gap-1.5">
  <div
    class="flex w-full overflow-hidden rounded-md border border-border bg-bg"
    style="height: {height};"
  >
    {#if segments.length === 0}
      <div class="flex w-full items-center justify-center text-xs text-fg-muted">
        No checks yet.
      </div>
    {:else}
      {#each segments as seg, i (i)}
        <div
          class="h-full flex-1 {seg.up ? 'bg-success' : 'bg-danger'}"
          title={`${seg.up ? 'UP' : 'DOWN'} · ${seg.checkedAt}`}
        ></div>
      {/each}
    {/if}
  </div>
  {#if segments.length > 0}
    <p class="text-xs text-fg-muted">
      <span class="font-mono text-fg">{uptimePct.toFixed(2)}%</span> uptime
      over
      <span class="font-mono text-fg">{segments.length}</span> checks
    </p>
  {/if}
</div>
