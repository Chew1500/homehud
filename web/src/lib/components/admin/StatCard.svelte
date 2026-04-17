<!--
  StatCard — a single KPI tile for admin dashboards.

  Uses subtle tinting (not full saturated fills) so a wall of cards
  doesn't feel visually loud. Danger tone kicks in when error counts
  are non-zero.
-->
<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    label: string;
    value: string | number;
    subtitle?: string;
    tone?: 'neutral' | 'danger' | 'accent';
    icon?: Snippet;
  }

  let { label, value, subtitle, tone = 'neutral', icon }: Props = $props();

  const toneClass = $derived(
    tone === 'danger'
      ? 'border-danger/40 bg-danger/10'
      : tone === 'accent'
        ? 'border-accent/40 bg-accent/10'
        : 'border-border bg-surface',
  );
  const valueClass = $derived(
    tone === 'danger' ? 'text-danger' : tone === 'accent' ? 'text-accent' : 'text-fg',
  );
</script>

<div class="flex flex-col gap-1 rounded-xl border p-4 {toneClass}">
  <div class="flex items-center justify-between">
    <span class="text-[0.65rem] font-semibold uppercase tracking-[0.08em] text-fg-muted">
      {label}
    </span>
    {#if icon}{@render icon()}{/if}
  </div>
  <span class="font-mono text-2xl font-semibold tabular-nums {valueClass}">
    {value}
  </span>
  {#if subtitle}
    <span class="text-xs text-fg-muted">{subtitle}</span>
  {/if}
</div>
