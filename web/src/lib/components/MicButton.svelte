<!--
  MicButton — the hero control.

  Behaviour mirrors the classic UI's tap-vs-hold model:
    - Hold  (>= 300ms) → push-to-talk; release stops.
    - Tap   (< 300ms)  → enters "tap mode"; stays listening until the
                          user taps again.

  The RMS-driven ring expands while listening. A subtle pulse animation
  runs during processing/playing so the button never feels "dead".
-->
<script lang="ts">
  import { Mic, Loader2, Volume2 } from 'lucide-svelte';
  import { voiceStatus } from '$lib/voice/state-machine';
  import type { VoiceState } from '$lib/voice/state-machine';

  interface Props {
    onPress: () => void;
    onRelease: () => void;
    /** Disable while the composer is showing a pending text input. */
    disabled?: boolean;
  }

  let { onPress, onRelease, disabled = false }: Props = $props();

  // Tap-vs-hold timer. If the user releases before 300ms, we switch to
  // tap-mode (don't stop on release — wait for a second tap).
  let holdTimer: ReturnType<typeof setTimeout> | null = null;
  let tapMode = false;

  const state = $derived<VoiceState>($voiceStatus.state);
  const rms = $derived($voiceStatus.rms);

  // Ring scales from 1.0 → 1.5 based on RMS. Opacity follows the same
  // curve so low-level speech still renders a visible pulse.
  const ringScale = $derived(1 + Math.min(rms * 8, 0.5));
  const ringOpacity = $derived(state === 'listening' ? Math.min(rms * 10, 0.6) : 0);

  function handleDown(ev: Event) {
    ev.preventDefault();
    if (disabled) return;
    if (state === 'processing' || state === 'playing') return;

    if (state === 'listening' && tapMode) {
      // Second tap in tap mode: stop recording.
      tapMode = false;
      onRelease();
      return;
    }

    tapMode = false;
    holdTimer = setTimeout(() => {
      holdTimer = null;
    }, 300);
    onPress();
  }

  function handleUp(ev: Event) {
    ev.preventDefault();
    if (disabled) return;
    if (state !== 'listening') return;

    if (holdTimer) {
      // Short press → tap mode; don't stop yet.
      clearTimeout(holdTimer);
      holdTimer = null;
      tapMode = true;
      return;
    }
    onRelease();
  }
</script>

<div class="relative flex size-40 items-center justify-center">
  <!-- RMS pulse ring -->
  <div
    class="pointer-events-none absolute inset-0 rounded-full bg-accent/40 transition-[transform,opacity] duration-100"
    style="transform: scale({ringScale}); opacity: {ringOpacity};"
    aria-hidden="true"
  ></div>

  <button
    type="button"
    onmousedown={handleDown}
    onmouseup={handleUp}
    onmouseleave={handleUp}
    ontouchstart={handleDown}
    ontouchend={handleUp}
    oncontextmenu={(e) => e.preventDefault()}
    aria-label={state === 'listening' ? 'Stop recording' : 'Start recording'}
    aria-pressed={state === 'listening'}
    {disabled}
    class="relative z-10 flex size-32 items-center justify-center rounded-full border border-border bg-surface text-accent shadow-soft transition-transform duration-150 active:scale-95 disabled:opacity-50 data-[state=listening]:bg-accent data-[state=listening]:text-accent-fg data-[state=processing]:animate-pulse data-[state=playing]:animate-pulse"
    style="touch-action: none; -webkit-tap-highlight-color: transparent;"
    data-state={state}
  >
    {#if state === 'processing'}
      <Loader2 class="size-14 animate-spin" />
    {:else if state === 'playing'}
      <Volume2 class="size-14" />
    {:else}
      <Mic class="size-14" />
    {/if}
  </button>
</div>
