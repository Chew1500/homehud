<!--
  Voice — the hero tab. Mobile-first, centred vertically.

  Composer behaviour:
    - Mic button is the primary action. Hold-to-talk or tap-to-toggle.
    - Text input below. When it has content, the Send arrow replaces
      the mic's role as "submit"; when empty, the mic is the only action.
    - Transcript fills the middle between status + composer.

  The AudioWorklet state machine and thread logic live in $lib/voice/*.
  This file is just the composition layer.
-->
<script lang="ts">
  import { Send, RotateCcw } from 'lucide-svelte';
  import MicButton from '$lib/components/MicButton.svelte';
  import ConversationThread from '$lib/components/ConversationThread.svelte';
  import type { ConversationTurn } from '$lib/voice/turn';
  import { sendText, sendVoice } from '$lib/api/voice';
  import { ApiFetchError } from '$lib/api/types';
  import { startCapture, MicPermissionError, type CaptureHandle } from '$lib/voice/audio-capture';
  import { playWav } from '$lib/voice/playback';
  import {
    currentVoiceState,
    setVoiceError,
    setVoiceState,
    voiceStatus,
  } from '$lib/voice/state-machine';
  import {
    clearPendingDivider,
    currentThread,
    markHistory,
    resetConversation,
    setThreadActive,
    threadStore,
  } from '$lib/voice/thread';

  let turns = $state<ConversationTurn[]>([]);
  let textInput = $state('');
  let inputEl: HTMLTextAreaElement | undefined = $state();
  let capture: CaptureHandle | null = null;
  let turnCounter = 0;

  const status = $derived($voiceStatus);
  const thread = $derived($threadStore);

  const statusLabel = $derived(
    status.error ??
      status.message ??
      {
        idle: 'Tap to talk',
        listening: 'Listening…',
        processing: 'Thinking…',
        playing: 'Speaking…',
      }[status.state],
  );

  function nextId(): string {
    turnCounter += 1;
    return `turn-${turnCounter}-${Date.now()}`;
  }

  function appendTurn(role: 'user' | 'assistant', modality: 'voice' | 'text', text: string) {
    const t = currentThread();
    const shouldDivide = role === 'user' && t.pendingDivider;
    turns = [
      ...turns,
      {
        id: nextId(),
        role,
        modality,
        text,
        divider: shouldDivide ? { label: 'New conversation', time: new Date() } : undefined,
      },
    ];
    if (shouldDivide) clearPendingDivider();
    markHistory();
  }

  // ── Mic flow ──────────────────────────────────────────────────────

  async function startListening() {
    if (currentVoiceState() !== 'idle') return;
    setVoiceState('listening');
    try {
      capture = await startCapture(async (pcm) => {
        capture = null;
        setVoiceState('processing');
        await submitVoice(pcm);
      });
    } catch (err) {
      capture = null;
      if (err instanceof MicPermissionError) {
        setVoiceError(err.message);
      } else {
        setVoiceError(err instanceof Error ? err.message : 'Microphone failed');
      }
    }
  }

  function stopListening() {
    if (!capture) return;
    capture.stop();
    capture = null;
    setVoiceState('processing');
  }

  async function submitVoice(pcm: ArrayBuffer) {
    try {
      const turn = await sendVoice(pcm);
      appendTurn('user', 'voice', turn.transcription);
      appendTurn('assistant', 'voice', turn.responseText);
      setThreadActive(turn.threadActive);
      if (turn.wav.byteLength > 44) {
        setVoiceState('playing');
        await playWav(turn.wav);
      }
      setVoiceState('idle');
    } catch (err) {
      const msg = err instanceof ApiFetchError
        ? `Server error ${err.status}`
        : err instanceof Error
          ? err.message
          : 'Voice request failed';
      appendTurn('assistant', 'voice', msg);
      setVoiceError(msg);
    }
  }

  // ── Text flow ─────────────────────────────────────────────────────

  async function submitText() {
    const text = textInput.trim();
    if (!text) return;
    if (currentVoiceState() === 'processing' || currentVoiceState() === 'playing') return;
    textInput = '';
    autosize();
    appendTurn('user', 'text', text);
    setVoiceState('processing');
    try {
      const turn = await sendText(text);
      appendTurn('assistant', 'text', turn.responseText);
      setThreadActive(turn.threadActive);
      setVoiceState('idle');
    } catch (err) {
      const msg = err instanceof ApiFetchError
        ? `Server error ${err.status}`
        : err instanceof Error
          ? err.message
          : 'Message failed';
      appendTurn('assistant', 'text', msg);
      setVoiceError(msg);
    } finally {
      inputEl?.focus();
    }
  }

  function onTextKeydown(ev: KeyboardEvent) {
    if (ev.key === 'Enter' && !ev.shiftKey) {
      ev.preventDefault();
      submitText();
    }
  }

  function autosize() {
    if (!inputEl) return;
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + 'px';
  }

  const textBusy = $derived(
    status.state === 'processing' || status.state === 'playing',
  );
  const hasText = $derived(textInput.trim().length > 0);

  async function onReset() {
    await resetConversation();
  }
</script>

<section
  class="mx-auto flex h-full w-full max-w-xl flex-col gap-4 px-4 pb-2 pt-[env(safe-area-inset-top)]"
>
  <!-- Header: thread state + reset -->
  <header class="flex items-center justify-between pt-2">
    <span class="text-xs font-medium uppercase tracking-[0.08em] text-fg-muted">
      {thread.active ? 'Conversation active' : 'No active conversation'}
    </span>
    <button
      type="button"
      onclick={onReset}
      disabled={!thread.active}
      class="flex items-center gap-1 rounded-full border border-border px-3 py-1 text-xs text-fg-muted transition-opacity hover:text-fg disabled:opacity-40"
    >
      <RotateCcw class="size-3" />
      <span>New conversation</span>
    </button>
  </header>

  <!-- Transcript -->
  <div class="flex-1 overflow-hidden">
    <ConversationThread {turns} />
  </div>

  <!-- Status + mic -->
  <div class="flex flex-col items-center gap-3">
    <p
      class="text-center text-sm font-medium"
      class:text-danger={status.error}
      class:text-fg-muted={!status.error}
    >
      {statusLabel}
    </p>
    <MicButton
      onPress={startListening}
      onRelease={stopListening}
      disabled={textBusy || hasText}
    />
  </div>

  <!-- Text composer -->
  <div
    class="flex items-end gap-2 rounded-2xl border border-border bg-surface p-2 pb-[max(0.5rem,env(safe-area-inset-bottom))]"
  >
    <textarea
      bind:this={inputEl}
      bind:value={textInput}
      onkeydown={onTextKeydown}
      oninput={autosize}
      disabled={textBusy}
      rows="1"
      placeholder="Type a message…"
      class="flex-1 resize-none bg-transparent px-3 py-2 text-[1rem] leading-snug text-fg placeholder:text-fg-muted focus:outline-none disabled:opacity-40"
      style="min-height: 44px; max-height: 120px;"
    ></textarea>
    <button
      type="button"
      onclick={submitText}
      disabled={!hasText || textBusy}
      aria-label="Send message"
      class="flex size-10 shrink-0 items-center justify-center rounded-full bg-accent text-accent-fg transition-opacity disabled:opacity-40"
    >
      <Send class="size-4" />
    </button>
  </div>
</section>
