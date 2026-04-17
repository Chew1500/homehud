<!--
  ConfigField — one row of the admin Config form.

  Renders the appropriate input based on param.type. Sensitive values
  are masked and read-only (set them via .env on the Pi). Emits the
  current edited value via ``onChange`` so the parent can track dirty
  state centrally.
-->
<script lang="ts">
  import { Lock } from 'lucide-svelte';
  import type { ConfigParam } from '$lib/api/config';

  interface Props {
    param: ConfigParam;
    /** Current (possibly dirty) value. May be string | number | boolean. */
    value: string | number | boolean | null;
    dirty: boolean;
    onChange: (next: string | number | boolean) => void;
  }

  let { param, value, dirty, onChange }: Props = $props();

  const sourceLabel: Record<string, string> = {
    file: 'file',
    env: 'env',
    default: 'default',
  };

  function onInput(ev: Event) {
    const el = ev.currentTarget as HTMLInputElement;
    if (param.type === 'bool') {
      onChange(el.checked);
    } else if (param.type === 'int') {
      onChange(el.value === '' ? '' : Number.parseInt(el.value, 10));
    } else if (param.type === 'float') {
      onChange(el.value === '' ? '' : Number.parseFloat(el.value));
    } else {
      onChange(el.value);
    }
  }
</script>

<div
  class="flex flex-col gap-2 border-b border-border py-3 last:border-b-0 sm:flex-row sm:items-center"
>
  <div class="flex-1 min-w-0">
    <div class="flex items-center gap-2">
      <code class="font-mono text-sm text-fg">{param.key}</code>
      <span
        class="rounded-full px-1.5 py-0.5 text-[0.6rem] font-semibold uppercase tracking-wide"
        class:bg-accent={param.source === 'file'}
        class:text-accent-fg={param.source === 'file'}
        class:bg-surface-muted={param.source !== 'file'}
        class:text-fg-muted={param.source !== 'file'}
      >
        {sourceLabel[param.source] ?? param.source}
      </span>
      {#if param.sensitive}
        <Lock class="size-3.5 text-fg-muted" />
      {/if}
      {#if dirty}
        <span
          class="rounded-full bg-warn/20 px-1.5 py-0.5 text-[0.6rem] font-semibold uppercase tracking-wide text-warn"
        >
          dirty
        </span>
      {/if}
    </div>
    <p class="mt-0.5 text-xs text-fg-muted">{param.description}</p>
  </div>

  <div class="shrink-0 sm:w-72">
    {#if param.sensitive}
      <input
        type="text"
        value="••••••••"
        disabled
        class="w-full cursor-not-allowed rounded-lg border border-border bg-surface-muted px-3 py-2 font-mono text-sm text-fg-muted"
      />
    {:else if param.type === 'bool'}
      <label class="flex cursor-pointer items-center gap-3 rounded-lg border border-border bg-surface px-3 py-2">
        <span class="flex-1 text-xs text-fg-muted">
          {value ? 'Enabled' : 'Disabled'}
        </span>
        <input
          type="checkbox"
          checked={Boolean(value)}
          oninput={onInput}
          class="size-4 accent-accent"
        />
      </label>
    {:else if param.type === 'int' || param.type === 'float'}
      <input
        type="number"
        inputmode="decimal"
        step={param.type === 'float' ? 'any' : '1'}
        value={value ?? ''}
        oninput={onInput}
        class="w-full rounded-lg border border-border bg-surface px-3 py-2 font-mono text-sm text-fg focus:border-accent focus:outline-none"
        class:border-warn={dirty}
      />
    {:else}
      <input
        type="text"
        value={value == null ? '' : String(value)}
        oninput={onInput}
        autocomplete="off"
        autocapitalize="off"
        spellcheck="false"
        class="w-full rounded-lg border border-border bg-surface px-3 py-2 font-mono text-sm text-fg focus:border-accent focus:outline-none"
        class:border-warn={dirty}
      />
    {/if}
  </div>
</div>
