<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { pairWithCode } from '$lib/auth/store';
  import { ApiFetchError } from '$lib/api/types';

  let code = $state('');
  let pairing = $state(false);
  let error = $state<string | null>(null);

  const returnTo = $derived($page.url.searchParams.get('returnTo') || '/voice');

  async function submit(ev: SubmitEvent) {
    ev.preventDefault();
    if (code.length < 4 || pairing) return;
    pairing = true;
    error = null;
    try {
      await pairWithCode(code.trim());
      await goto(returnTo, { replaceState: true });
    } catch (err) {
      error =
        err instanceof ApiFetchError && err.status === 401
          ? 'That code is invalid or expired.'
          : 'Pairing failed. Please try again.';
    } finally {
      pairing = false;
    }
  }
</script>

<div class="flex h-full flex-col items-center justify-center overflow-y-auto px-6">
  <div class="w-full max-w-sm space-y-8">
    <div class="space-y-2 text-center">
      <h1 class="text-3xl font-semibold">Pair this device</h1>
      <p class="text-sm text-fg-muted">
        Ask Home HUD: <span class="font-medium text-fg">"generate pairing code"</span>
      </p>
    </div>

    <form onsubmit={submit} class="space-y-4">
      <label class="block">
        <span class="text-xs font-medium uppercase tracking-wide text-fg-muted"
          >Pairing code</span
        >
        <input
          type="text"
          inputmode="numeric"
          autocomplete="one-time-code"
          maxlength="8"
          bind:value={code}
          disabled={pairing}
          class="mt-2 w-full rounded-lg border border-border bg-surface px-4 py-3 text-center text-2xl tracking-[0.3em] focus:border-accent focus:outline-none"
          placeholder="000000"
        />
      </label>

      {#if error}
        <p class="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      {/if}

      <button
        type="submit"
        disabled={pairing || code.length < 4}
        class="w-full rounded-lg bg-accent px-4 py-3 font-medium text-accent-fg disabled:opacity-40"
      >
        {pairing ? 'Pairing…' : 'Continue'}
      </button>
    </form>

    <p class="text-center text-xs text-fg-muted">
      Tailscale users are paired automatically — just refresh this page.
    </p>
  </div>
</div>
