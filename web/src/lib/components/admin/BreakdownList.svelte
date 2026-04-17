<!--
  BreakdownList — sorted name / count / percent rows with a thin bar
  to give the longest counts visual weight.
-->
<script lang="ts">
  import { fmtPct } from '$lib/admin/format';

  interface Props {
    title: string;
    data: Record<string, number>;
  }

  let { title, data }: Props = $props();

  const entries = $derived(
    Object.entries(data).sort((a, b) => b[1] - a[1]),
  );
  const total = $derived(entries.reduce((acc, [, n]) => acc + n, 0));
  const max = $derived(entries[0]?.[1] ?? 0);
</script>

{#if entries.length > 0}
  <section class="flex flex-col gap-2 rounded-xl border border-border bg-surface p-4">
    <h3 class="text-xs font-semibold uppercase tracking-[0.08em] text-fg-muted">
      {title}
    </h3>
    <ul class="flex flex-col gap-2">
      {#each entries as [name, count] (name)}
        <li class="flex items-center gap-3">
          <div class="flex-1 min-w-0">
            <div class="flex items-baseline justify-between gap-2 text-sm">
              <span class="truncate text-fg">{name || '(none)'}</span>
              <span class="font-mono text-xs text-fg-muted">
                {count} · {fmtPct(count, total)}
              </span>
            </div>
            <div class="mt-1 h-1 overflow-hidden rounded-full bg-border/60">
              <div
                class="h-full bg-accent/70"
                style="width: {max ? (count / max) * 100 : 0}%"
              ></div>
            </div>
          </div>
        </li>
      {/each}
    </ul>
  </section>
{/if}
