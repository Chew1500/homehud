<!--
  ConversationThread — scrollable list of ChatBubble entries with
  timestamp-chip dividers between separate conversations.

  Owns its own scroll container; auto-scrolls to the bottom whenever a
  new turn is appended. The parent passes in an array of turns.
-->
<script lang="ts">
  import { tick } from 'svelte';
  import ChatBubble from './ChatBubble.svelte';
  import type { ConversationTurn } from '$lib/voice/turn';

  interface Props {
    turns: ConversationTurn[];
  }

  let { turns }: Props = $props();
  let scroller: HTMLDivElement | undefined = $state();
  let lastLength = $state(0);

  $effect(() => {
    if (turns.length > lastLength && scroller) {
      lastLength = turns.length;
      tick().then(() => {
        if (scroller) scroller.scrollTop = scroller.scrollHeight;
      });
    } else if (turns.length < lastLength) {
      lastLength = turns.length;
    }
  });

  function formatDividerTime(d: Date): string {
    const now = new Date();
    const sameDay =
      d.getFullYear() === now.getFullYear() &&
      d.getMonth() === now.getMonth() &&
      d.getDate() === now.getDate();
    const time = d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    return sameDay ? time : `${d.toLocaleDateString([], { month: 'short', day: 'numeric' })} · ${time}`;
  }
</script>

<div
  bind:this={scroller}
  class="flex max-h-[50dvh] min-h-[30dvh] flex-col gap-2 overflow-y-auto rounded-2xl p-2"
>
  {#if turns.length === 0}
    <p class="m-auto px-4 py-6 text-center text-sm text-fg-muted">
      Hold the mic to talk, or type below.
    </p>
  {:else}
    {#each turns as turn (turn.id)}
      {#if turn.divider}
        <div
          class="my-2 flex items-center gap-2 text-[0.7rem] font-semibold uppercase tracking-[0.08em] text-fg-muted"
        >
          <span class="h-px flex-1 bg-border"></span>
          <span>{turn.divider.label}</span>
          <span class="text-fg-muted/60">{formatDividerTime(turn.divider.time)}</span>
          <span class="h-px flex-1 bg-border"></span>
        </div>
      {/if}
      <ChatBubble role={turn.role} modality={turn.modality} text={turn.text} />
    {/each}
  {/if}
</div>
