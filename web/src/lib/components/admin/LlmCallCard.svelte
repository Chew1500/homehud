<!--
  LlmCallCard — single LLM call with collapsible prompt / response text.

  System prompts are often long; we collapse them behind a disclosure
  toggle so the eye lands on the user message + response first.
-->
<script lang="ts">
  import { ChevronRight } from 'lucide-svelte';
  import type { LlmCall } from '$lib/api/sessions';
  import { fmtInt, fmtMs } from '$lib/admin/format';

  interface Props {
    call: LlmCall;
  }

  let { call }: Props = $props();
  let showSystem = $state(false);
</script>

<article class="flex flex-col gap-2 rounded-xl border border-border bg-surface p-3 text-sm">
  <header class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-fg-muted">
    <span>
      Type <strong class="font-mono text-fg">{call.call_type}</strong>
    </span>
    <span>
      Model <strong class="font-mono text-fg">{call.model || '—'}</strong>
    </span>
    <span>
      Duration <strong class="font-mono text-fg">{fmtMs(call.duration_ms)}</strong>
    </span>
    <span>
      Tokens
      <strong class="font-mono text-fg">
        {fmtInt(call.input_tokens)} in / {fmtInt(call.output_tokens)} out
      </strong>
    </span>
    <span>
      Stop <strong class="font-mono text-fg">{call.stop_reason || '—'}</strong>
    </span>
  </header>

  {#if call.error}
    <p class="rounded-md border border-danger/40 bg-danger/10 px-2 py-1 text-xs text-danger">
      {call.error}
    </p>
  {/if}

  {#if call.system_prompt}
    <div>
      <button
        type="button"
        onclick={() => (showSystem = !showSystem)}
        class="flex items-center gap-1 text-[0.65rem] font-semibold uppercase tracking-[0.08em] text-fg-muted hover:text-fg"
      >
        <ChevronRight class="size-3 transition-transform {showSystem ? 'rotate-90' : ''}" />
        System prompt
      </button>
      {#if showSystem}
        <pre
          class="mt-1 max-h-64 overflow-auto rounded-md bg-surface-muted p-2 font-mono text-[0.75rem] leading-snug text-fg whitespace-pre-wrap break-words"
        >{call.system_prompt}</pre>
      {/if}
    </div>
  {/if}

  {#if call.user_message}
    <div>
      <p class="text-[0.65rem] font-semibold uppercase tracking-[0.08em] text-fg-muted">
        User message
      </p>
      <pre
        class="mt-1 max-h-40 overflow-auto rounded-md bg-surface-muted p-2 font-mono text-[0.75rem] leading-snug text-fg whitespace-pre-wrap break-words"
      >{call.user_message}</pre>
    </div>
  {/if}

  {#if call.response_text}
    <div>
      <p class="text-[0.65rem] font-semibold uppercase tracking-[0.08em] text-fg-muted">
        Response
      </p>
      <pre
        class="mt-1 max-h-60 overflow-auto rounded-md bg-surface-muted p-2 font-mono text-[0.75rem] leading-snug text-fg whitespace-pre-wrap break-words"
      >{call.response_text}</pre>
    </div>
  {/if}
</article>
