<!--
  ChatBubble — single turn in the conversation transcript.

  Roles:
    - user      → right-aligned, accent-tinted
    - assistant → left-aligned, surface-muted

  Modality ("voice" or "text") is shown as a small pill before the text
  so the user can tell at a glance which channel produced each turn.
-->
<script lang="ts">
  import { Mic, MessageSquare } from 'lucide-svelte';

  interface Props {
    role: 'user' | 'assistant';
    modality: 'voice' | 'text';
    text: string;
  }

  let { role, modality, text }: Props = $props();
</script>

<div
  class="flex max-w-[85%] flex-col gap-1 rounded-2xl px-4 py-2.5 text-[0.95rem] leading-snug shadow-soft"
  class:self-end={role === 'user'}
  class:bg-accent={role === 'user'}
  class:text-accent-fg={role === 'user'}
  class:rounded-br-md={role === 'user'}
  class:self-start={role === 'assistant'}
  class:bg-surface={role === 'assistant'}
  class:text-fg={role === 'assistant'}
  class:rounded-bl-md={role === 'assistant'}
>
  <span
    class="flex items-center gap-1 text-[0.6rem] font-semibold uppercase tracking-[0.08em]"
    class:text-accent-fg={role === 'user'}
    class:opacity-70={role === 'user'}
    class:text-fg-muted={role === 'assistant'}
  >
    {#if modality === 'voice'}
      <Mic class="size-3" />
    {:else}
      <MessageSquare class="size-3" />
    {/if}
    {modality}
  </span>
  <p class="whitespace-pre-wrap break-words">{text || '(empty)'}</p>
</div>
