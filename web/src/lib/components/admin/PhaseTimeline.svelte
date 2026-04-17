<!--
  PhaseTimeline — horizontal proportional bar showing exchange phases
  and the gaps between them. Hover/long-press shows each segment's
  duration via the title attribute (no fancy tooltip needed on mobile).
-->
<script lang="ts">
  import type { Exchange } from '$lib/api/sessions';
  import {
    computeSegments,
    exchangeWallClock,
    PHASE_LABELS,
    type Segment,
  } from '$lib/admin/phase';
  import { fmtMs } from '$lib/admin/format';

  interface Props {
    exchange: Exchange;
    showLegend?: boolean;
  }

  let { exchange, showLegend = false }: Props = $props();

  const wall = $derived(exchangeWallClock(exchange));
  const segments = $derived(computeSegments(exchange));

  function segmentClass(seg: Segment): string {
    if (seg.kind === 'gap') return 'bg-border/70';
    switch (seg.phase) {
      case 'recording':
        return 'bg-accent';
      case 'stt':
        return 'bg-success';
      case 'routing':
        return 'bg-warn';
      case 'tts':
        return 'bg-[#a37fd1]'; // soft lavender
      case 'playback':
        return 'bg-[#5b9e9a]'; // muted teal
    }
  }

  function segmentTitle(seg: Segment): string {
    const ms = fmtMs(seg.durationMs);
    if (seg.kind === 'gap') return `gap before ${PHASE_LABELS[seg.phase]}: ${ms}`;
    return `${PHASE_LABELS[seg.phase]}: ${ms}`;
  }

  const legend = [
    { label: 'Recording', cls: 'bg-accent' },
    { label: 'STT', cls: 'bg-success' },
    { label: 'Routing', cls: 'bg-warn' },
    { label: 'TTS', cls: 'bg-[#a37fd1]' },
    { label: 'Playback', cls: 'bg-[#5b9e9a]' },
    { label: 'Gap', cls: 'bg-border/70' },
  ];
</script>

{#if !wall || wall <= 0}
  <span class="text-xs text-fg-muted">—</span>
{:else}
  <div class="flex h-2 w-full overflow-hidden rounded-full bg-border/30">
    {#each segments as seg, i (i)}
      <div
        class="h-full {segmentClass(seg)}"
        style="width: {Math.max(0.5, (seg.durationMs / wall) * 100).toFixed(2)}%"
        title={segmentTitle(seg)}
      ></div>
    {/each}
  </div>
{/if}

{#if showLegend}
  <div class="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[0.7rem] text-fg-muted">
    {#each legend as item (item.label)}
      <span class="flex items-center gap-1">
        <span class="size-2 rounded-full {item.cls}"></span>
        {item.label}
      </span>
    {/each}
  </div>
{/if}
