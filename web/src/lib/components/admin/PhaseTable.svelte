<!--
  PhaseTable — phase-by-phase average latency with inter-phase gaps
  and a wall-clock reconciliation at the bottom. Mirrors the classic
  "Phase Performance" table but with monospace numbers and subtle gap
  rows so the eye lands on the phases first.
-->
<script lang="ts">
  import { fmtMs } from '$lib/admin/format';
  import type { StatsResponse } from '$lib/api/stats';

  interface Props {
    stats: StatsResponse;
  }

  let { stats }: Props = $props();

  const rows = $derived([
    { phase: 'Recording', ms: stats.avg_recording_ms, gap: stats.avg_rec_to_stt_gap_ms },
    { phase: 'STT', ms: stats.avg_stt_ms, gap: stats.avg_stt_to_routing_gap_ms },
    { phase: 'Routing', ms: stats.avg_routing_ms, gap: stats.avg_routing_to_tts_gap_ms },
    { phase: 'TTS', ms: stats.avg_tts_ms, gap: stats.avg_tts_to_playback_gap_ms },
    { phase: 'Playback', ms: stats.avg_playback_ms, gap: null },
  ]);

  const phaseSum = $derived(
    rows.reduce((acc, r) => acc + (r.ms ?? 0), 0),
  );
  const wall = $derived(stats.avg_wall_clock_ms ?? null);
  const unaccounted = $derived(
    wall != null && phaseSum > 0 ? Math.max(0, Math.round(wall - phaseSum)) : null,
  );
  const maxPhase = $derived(
    Math.max(0, ...rows.map((r) => r.ms ?? 0)),
  );
</script>

<section class="flex flex-col gap-2 rounded-xl border border-border bg-surface p-4">
  <h3 class="text-xs font-semibold uppercase tracking-[0.08em] text-fg-muted">
    Phase performance
  </h3>
  <table class="w-full text-sm">
    <tbody>
      {#each rows as row, i (row.phase)}
        <tr class="border-t border-border first:border-t-0">
          <td class="py-2 pr-3 text-fg">{row.phase}</td>
          <td class="py-2 pr-2 w-1/2">
            <div class="h-1.5 overflow-hidden rounded-full bg-border/60">
              <div
                class="h-full bg-accent"
                style="width: {maxPhase ? ((row.ms ?? 0) / maxPhase) * 100 : 0}%"
              ></div>
            </div>
          </td>
          <td class="py-2 text-right font-mono tabular-nums">{fmtMs(row.ms)}</td>
        </tr>
        {#if row.gap != null && i < rows.length - 1}
          <tr class="text-fg-muted/80">
            <td class="py-1 pr-3 pl-4 text-xs italic">→ gap</td>
            <td></td>
            <td class="py-1 text-right font-mono text-xs italic tabular-nums">
              {fmtMs(row.gap)}
            </td>
          </tr>
        {/if}
      {/each}
    </tbody>
    <tfoot>
      <tr class="border-t-2 border-border font-semibold">
        <td class="py-2 pr-3">Wall clock</td>
        <td></td>
        <td class="py-2 text-right font-mono tabular-nums">{fmtMs(wall)}</td>
      </tr>
      <tr class="text-fg-muted">
        <td class="py-1 pr-3 text-xs">Sum of phases</td>
        <td></td>
        <td class="py-1 text-right font-mono text-xs tabular-nums">
          {fmtMs(phaseSum || null)}
        </td>
      </tr>
      {#if unaccounted}
        <tr class="text-fg-muted/80">
          <td class="py-1 pr-3 pl-4 text-xs italic">Unaccounted</td>
          <td></td>
          <td class="py-1 text-right font-mono text-xs italic tabular-nums">
            {fmtMs(unaccounted)}
          </td>
        </tr>
      {/if}
    </tfoot>
  </table>
</section>
