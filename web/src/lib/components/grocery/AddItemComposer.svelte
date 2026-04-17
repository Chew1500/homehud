<!--
  Add-item composer. Parses the user's text into name/quantity/unit and
  delegates to the store. Surfaces a short-lived "already on list" hint
  when the server rejects a duplicate.
-->
<script lang="ts">
  import { Plus } from 'lucide-svelte';
  import { parseGroceryInput } from '$lib/grocery/parser';
  import { addItem } from '$lib/grocery/store';

  let input = $state('');
  let busy = $state(false);
  let hint = $state<string | null>(null);
  let hintTimer: ReturnType<typeof setTimeout> | null = null;

  function flashHint(message: string) {
    hint = message;
    if (hintTimer) clearTimeout(hintTimer);
    hintTimer = setTimeout(() => {
      hint = null;
    }, 2500);
  }

  async function submit(ev?: Event) {
    ev?.preventDefault();
    const raw = input.trim();
    if (!raw || busy) return;
    const parsed = parseGroceryInput(raw);
    if (!parsed.name) return;
    busy = true;
    const result = await addItem(parsed);
    busy = false;
    if (result === 'ok') {
      input = '';
    } else if (result === 'duplicate') {
      flashHint(`"${parsed.name}" is already on the list`);
    } else if (result === 'error') {
      flashHint('Failed to add — please retry');
    }
  }

  function onKeydown(ev: KeyboardEvent) {
    if (ev.key === 'Enter') submit(ev);
  }
</script>

<form onsubmit={submit} class="flex flex-col gap-1">
  <div
    class="flex items-center gap-2 rounded-2xl border border-border bg-surface px-2 py-1.5"
  >
    <input
      type="text"
      bind:value={input}
      onkeydown={onKeydown}
      placeholder="Add an item…"
      disabled={busy}
      autocomplete="off"
      autocorrect="off"
      autocapitalize="sentences"
      class="flex-1 bg-transparent px-2 py-2 text-[1rem] text-fg placeholder:text-fg-muted focus:outline-none disabled:opacity-40"
    />
    <button
      type="submit"
      disabled={!input.trim() || busy}
      aria-label="Add item"
      class="flex size-10 shrink-0 items-center justify-center rounded-full bg-accent text-accent-fg transition-opacity disabled:opacity-40"
    >
      <Plus class="size-5" />
    </button>
  </div>
  {#if hint}
    <p class="px-3 text-xs text-fg-muted">{hint}</p>
  {/if}
</form>
