<!--
  Voice Cache — inspect cached TTS clips. Click the play button to
  stream the audio directly from /api/tts-cache/{hash}/audio.
-->
<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { AlertCircle, Pause, Play, RefreshCw } from 'lucide-svelte';
  import StatCard from '$lib/components/admin/StatCard.svelte';
  import { fetchTtsCache, ttsCacheAudioUrl, type TtsCacheResponse } from '$lib/api/tts-cache';
  import { fmtBytes } from '$lib/admin/bytes';
  import { fmtInt, fmtRelative } from '$lib/admin/format';

  let data = $state<TtsCacheResponse | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  let currentAudio: HTMLAudioElement | null = null;
  let playingHash = $state<string | null>(null);

  async function load() {
    loading = true;
    error = null;
    try {
      data = await fetchTtsCache();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load cache';
    } finally {
      loading = false;
    }
  }

  function stopAudio() {
    if (currentAudio) {
      currentAudio.pause();
      currentAudio.src = '';
      currentAudio = null;
    }
    playingHash = null;
  }

  function togglePlay(hash: string) {
    if (playingHash === hash) {
      stopAudio();
      return;
    }
    stopAudio();
    const audio = new Audio(ttsCacheAudioUrl(hash));
    audio.addEventListener('ended', () => {
      if (playingHash === hash) stopAudio();
    });
    audio.addEventListener('error', () => {
      if (playingHash === hash) stopAudio();
    });
    currentAudio = audio;
    playingHash = hash;
    void audio.play().catch(() => stopAudio());
  }

  const totalHits = $derived(
    data ? data.entries.reduce((a, e) => a + (e.hit_count || 0), 0) : 0,
  );
  const sortedEntries = $derived(
    data ? [...data.entries].sort((a, b) => (b.hit_count || 0) - (a.hit_count || 0)) : [],
  );

  onMount(() => {
    load();
  });

  onDestroy(() => {
    stopAudio();
  });
</script>

<div class="flex flex-col gap-4">
  <header class="flex items-start justify-between gap-3">
    <div>
      <h1 class="text-2xl font-semibold">Voice cache</h1>
      <p class="mt-1 text-sm text-fg-muted">
        Cached TTS clips. Hot entries avoid a synthesis round-trip.
      </p>
    </div>
    <button
      type="button"
      onclick={load}
      disabled={loading}
      aria-label="Refresh"
      class="flex size-9 items-center justify-center rounded-full border border-border text-fg-muted hover:bg-surface-muted hover:text-fg disabled:opacity-40"
    >
      <RefreshCw class="size-4 {loading ? 'animate-spin' : ''}" />
    </button>
  </header>

  {#if error}
    <div
      class="flex items-start gap-2 rounded-xl border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger"
    >
      <AlertCircle class="mt-0.5 size-4 shrink-0" />
      <span>{error}</span>
    </div>
  {/if}

  {#if data}
    <section class="grid grid-cols-3 gap-2">
      <StatCard label="Entries" value={fmtInt(data.total_entries)} />
      <StatCard label="Total size" value={fmtBytes(data.total_size_bytes)} />
      <StatCard label="Total hits" value={fmtInt(totalHits)} />
    </section>

    {#if data.entries.length === 0}
      <p class="rounded-xl border border-border bg-surface p-6 text-center text-sm text-fg-muted">
        Cache is empty.
      </p>
    {:else}
      <ul class="flex flex-col gap-1.5">
        {#each sortedEntries as entry (entry.hash)}
          {@const isPlaying = playingHash === entry.hash}
          <li
            class="flex items-center gap-3 rounded-xl border border-border bg-surface px-3 py-2.5"
          >
            <button
              type="button"
              onclick={() => togglePlay(entry.hash)}
              aria-label={isPlaying ? 'Stop playback' : 'Play clip'}
              class="flex size-9 shrink-0 items-center justify-center rounded-full transition-colors"
              class:bg-accent={isPlaying}
              class:text-accent-fg={isPlaying}
              class:bg-surface-muted={!isPlaying}
              class:text-fg={!isPlaying}
            >
              {#if isPlaying}
                <Pause class="size-4" />
              {:else}
                <Play class="size-4" />
              {/if}
            </button>
            <div class="flex flex-1 min-w-0 flex-col gap-0.5">
              <p class="truncate text-sm text-fg">{entry.text || '(empty)'}</p>
              <div class="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[0.7rem] text-fg-muted">
                {#if entry.voice}
                  <span>
                    Voice <strong class="font-mono text-fg">{entry.voice}</strong>
                  </span>
                {/if}
                {#if entry.model}
                  <span>
                    Model <strong class="font-mono text-fg">{entry.model}</strong>
                  </span>
                {/if}
                <span>
                  Hits <strong class="font-mono text-fg">{fmtInt(entry.hit_count)}</strong>
                </span>
                <span>
                  Size <strong class="font-mono text-fg">{fmtBytes(entry.size_bytes)}</strong>
                </span>
                {#if entry.created_at}
                  <span class="text-fg-muted">{fmtRelative(entry.created_at)}</span>
                {/if}
              </div>
            </div>
          </li>
        {/each}
      </ul>
    {/if}
  {/if}
</div>
