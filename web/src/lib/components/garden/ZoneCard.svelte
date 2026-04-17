<!--
  ZoneCard — a single watering zone's state.

  The card's tint and status pill come from `urgency`. The progress bar
  visualises current soil water as a fraction of the deficit threshold.
-->
<script lang="ts">
  import { CloudRain, Droplets } from 'lucide-svelte';
  import type { Zone, ZoneUrgency } from '$lib/api/garden';
  import { formatInches } from '$lib/garden/units';

  interface Props {
    zone: Zone;
  }

  let { zone }: Props = $props();

  const urgencyMeta: Record<
    ZoneUrgency,
    { label: string; tone: string; bg: string; text: string; fill: string }
  > = {
    ok: {
      label: 'On track',
      tone: 'border-border',
      bg: 'bg-surface',
      text: 'text-fg-muted',
      fill: 'bg-success',
    },
    monitor: {
      label: 'Monitor',
      tone: 'border-warn/40',
      bg: 'bg-warn/5',
      text: 'text-warn',
      fill: 'bg-warn',
    },
    water_today: {
      label: 'Water today',
      tone: 'border-accent/50',
      bg: 'bg-accent/10',
      text: 'text-accent',
      fill: 'bg-accent',
    },
    urgent: {
      label: 'Urgent',
      tone: 'border-danger/50',
      bg: 'bg-danger/10',
      text: 'text-danger',
      fill: 'bg-danger',
    },
  };

  const meta = $derived(urgencyMeta[zone.urgency]);
  const barPct = $derived(Math.max(0, Math.min(100, zone.pct_of_threshold)));
</script>

<article class="flex flex-col gap-2 rounded-xl border p-4 {meta.tone} {meta.bg}">
  <header class="flex items-center justify-between gap-2">
    <h3 class="text-base font-semibold text-fg">{zone.label}</h3>
    <span
      class="rounded-full px-2 py-0.5 text-[0.65rem] font-semibold uppercase tracking-wide {meta.text} bg-surface"
    >
      {meta.label}
    </span>
  </header>

  <div class="h-1.5 overflow-hidden rounded-full bg-border/60">
    <div class="h-full {meta.fill}" style="width: {barPct}%"></div>
  </div>

  <dl class="grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-fg-muted">
    <dt class="uppercase tracking-wide">Deficit</dt>
    <dd class="text-right font-mono text-fg">
      {formatInches(zone.deficit_inches)} / {formatInches(zone.threshold_inches)}
    </dd>
    {#if zone.days_since_rain != null}
      <dt class="flex items-center gap-1 uppercase tracking-wide">
        <CloudRain class="size-3" /> Last rain
      </dt>
      <dd class="text-right font-mono text-fg">{zone.days_since_rain}d ago</dd>
    {/if}
    {#if zone.days_since_watered != null}
      <dt class="flex items-center gap-1 uppercase tracking-wide">
        <Droplets class="size-3" /> Watered
      </dt>
      <dd class="text-right font-mono text-fg">{zone.days_since_watered}d ago</dd>
    {/if}
  </dl>
</article>
