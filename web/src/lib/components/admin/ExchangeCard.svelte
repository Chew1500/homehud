<!--
  ExchangeCard — one row inside a session detail view. Shows the
  transcription, route + feature, timeline bar, flags, and an
  expandable drawer with response text, phase breakdown, STT
  confidence, and LLM calls.
-->
<script lang="ts">
  import { ChevronRight } from 'lucide-svelte';
  import type { Exchange } from '$lib/api/sessions';
  import { fmtMs } from '$lib/admin/format';
  import {
    computeSegments,
    exchangeWallClock,
    PHASE_LABELS,
    phaseSum,
    prettyRejectionReason,
    unaccountedMs,
  } from '$lib/admin/phase';
  import PhaseTimeline from './PhaseTimeline.svelte';
  import LlmCallCard from './LlmCallCard.svelte';

  interface Props {
    exchange: Exchange;
  }

  let { exchange }: Props = $props();
  let expanded = $state(false);

  const wall = $derived(exchangeWallClock(exchange));
  const segments = $derived(computeSegments(exchange));
  const unaccounted = $derived(unaccountedMs(wall, segments));
  const phasesTotal = $derived(phaseSum(segments));
  const rejectionReason = $derived(prettyRejectionReason(exchange.routing_path));

  const routeLabel = $derived(
    [exchange.routing_path, exchange.matched_feature].filter(Boolean).join(' › '),
  );

  const flags = $derived(
    [
      exchange.used_vad && { label: 'VAD', tone: 'neutral' as const },
      exchange.had_bargein && { label: 'BARGE', tone: 'accent' as const },
      exchange.is_follow_up && { label: 'FOLLOW', tone: 'accent' as const },
      exchange.error && { label: 'ERR', tone: 'danger' as const },
      rejectionReason && { label: 'REJ', tone: 'danger' as const },
    ].filter(
      (x): x is { label: string; tone: 'neutral' | 'accent' | 'danger' } => Boolean(x),
    ),
  );

  function flagClass(tone: 'neutral' | 'accent' | 'danger'): string {
    if (tone === 'danger') return 'border-danger/40 bg-danger/10 text-danger';
    if (tone === 'accent') return 'border-accent/40 bg-accent/10 text-accent';
    return 'border-border bg-surface-muted text-fg-muted';
  }
</script>

<article class="overflow-hidden rounded-xl border border-border bg-surface">
  <button
    type="button"
    onclick={() => (expanded = !expanded)}
    aria-expanded={expanded}
    class="flex w-full flex-col gap-2 px-4 py-3 text-left"
  >
    <div class="flex items-center gap-2">
      <ChevronRight
        class="size-4 shrink-0 text-fg-muted transition-transform {expanded ? 'rotate-90' : ''}"
      />
      <span class="font-mono text-xs text-fg-muted">#{exchange.sequence}</span>
      <span class="flex-1 truncate text-sm text-fg">
        {exchange.transcription || '(no transcription)'}
      </span>
      <span class="shrink-0 font-mono text-xs text-fg-muted">
        {fmtMs(wall)}
      </span>
    </div>
    <div class="flex items-center gap-2 pl-6">
      <span class="truncate text-xs text-fg-muted">
        {routeLabel || '—'}
      </span>
      {#each flags as flag (flag.label)}
        <span
          class="rounded-full border px-1.5 py-0.5 text-[0.6rem] font-semibold uppercase tracking-wide {flagClass(
            flag.tone,
          )}"
        >
          {flag.label}
        </span>
      {/each}
    </div>
    <div class="pl-6">
      <PhaseTimeline {exchange} />
    </div>
  </button>

  {#if expanded}
    <div class="flex flex-col gap-3 border-t border-border px-4 py-3 text-sm">
      {#if exchange.error}
        <div
          class="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger"
        >
          {exchange.error}
        </div>
      {/if}

      {#if exchange.response_text}
        <section class="flex flex-col gap-1">
          <p class="text-[0.65rem] font-semibold uppercase tracking-[0.08em] text-fg-muted">
            Response
          </p>
          <pre
            class="max-h-52 overflow-auto rounded-md bg-surface-muted p-2 font-mono text-[0.75rem] leading-snug text-fg whitespace-pre-wrap break-words"
          >{exchange.response_text}</pre>
        </section>
      {/if}

      {#if segments.length}
        <section class="flex flex-col gap-1">
          <p class="text-[0.65rem] font-semibold uppercase tracking-[0.08em] text-fg-muted">
            Phase breakdown
          </p>
          <table class="w-full text-xs">
            <tbody>
              {#each segments as seg, i (i)}
                {@const isGap = seg.kind === 'gap'}
                <tr class:text-fg-muted={isGap}>
                  <td class="py-0.5 {isGap ? 'pl-5 italic' : ''}">
                    {isGap ? '→ gap' : PHASE_LABELS[seg.phase]}
                  </td>
                  <td class="py-0.5 pr-2 text-right font-mono tabular-nums">
                    {fmtMs(seg.durationMs)}
                  </td>
                  <td class="py-0.5 text-right font-mono tabular-nums text-fg-muted">
                    {wall ? ((seg.durationMs / wall) * 100).toFixed(1) : '—'}%
                  </td>
                </tr>
              {/each}
              {#if wall}
                <tr class="border-t border-border font-semibold">
                  <td class="py-0.5">Total (wall)</td>
                  <td class="py-0.5 pr-2 text-right font-mono tabular-nums">{fmtMs(wall)}</td>
                  <td class="py-0.5 text-right font-mono tabular-nums">100%</td>
                </tr>
                <tr class="text-fg-muted">
                  <td class="py-0.5 text-xs">Sum of phases</td>
                  <td class="py-0.5 pr-2 text-right font-mono text-xs tabular-nums">
                    {fmtMs(phasesTotal)}
                  </td>
                  <td class="py-0.5 text-right font-mono text-xs tabular-nums">
                    {wall ? ((phasesTotal / wall) * 100).toFixed(1) : '—'}%
                  </td>
                </tr>
                {#if unaccounted && unaccounted > 0.5}
                  <tr class="text-fg-muted/80">
                    <td class="py-0.5 pl-5 text-xs italic">Unaccounted</td>
                    <td class="py-0.5 pr-2 text-right font-mono text-xs italic tabular-nums">
                      {fmtMs(unaccounted)}
                    </td>
                    <td class="py-0.5 text-right font-mono text-xs italic tabular-nums">
                      {wall ? ((unaccounted / wall) * 100).toFixed(1) : '—'}%
                    </td>
                  </tr>
                {/if}
              {/if}
            </tbody>
          </table>
        </section>
      {/if}

      {#if exchange.stt_no_speech_prob != null || exchange.stt_avg_logprob != null}
        <section class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
          <span class="text-[0.65rem] font-semibold uppercase tracking-[0.08em] text-fg-muted">
            STT confidence
          </span>
          <span class="font-mono">
            no_speech_prob:
            <strong class="text-fg">
              {exchange.stt_no_speech_prob != null ? exchange.stt_no_speech_prob.toFixed(4) : '—'}
            </strong>
          </span>
          <span class="font-mono">
            avg_logprob:
            <strong class="text-fg">
              {exchange.stt_avg_logprob != null ? exchange.stt_avg_logprob.toFixed(4) : '—'}
            </strong>
          </span>
          {#if rejectionReason}
            <span class="font-mono font-semibold text-danger">({rejectionReason})</span>
          {/if}
        </section>
      {/if}

      {#if exchange.llm_calls.length > 0}
        <section class="flex flex-col gap-2">
          <p class="text-[0.65rem] font-semibold uppercase tracking-[0.08em] text-fg-muted">
            LLM calls
          </p>
          {#each exchange.llm_calls as call, i (i)}
            <LlmCallCard {call} />
          {/each}
        </section>
      {:else}
        <p class="text-xs text-fg-muted">No LLM calls for this exchange.</p>
      {/if}
    </div>
  {/if}
</article>
