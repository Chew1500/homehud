<!--
  CollapsibleSection — titled panel with a chevron toggle. Used for the
  water-balance, forecast, and watering-log tables on the Garden page.
-->
<script lang="ts">
  import { ChevronRight } from 'lucide-svelte';
  import type { Snippet } from 'svelte';

  interface Props {
    title: string;
    subtitle?: string;
    defaultOpen?: boolean;
    children: Snippet;
  }

  let { title, subtitle, defaultOpen = true, children }: Props = $props();
  let open = $state(defaultOpen);
</script>

<section class="overflow-hidden rounded-xl border border-border bg-surface">
  <button
    type="button"
    onclick={() => (open = !open)}
    aria-expanded={open}
    class="flex w-full items-center gap-2 px-4 py-3 text-left"
  >
    <ChevronRight
      class="size-4 shrink-0 text-fg-muted transition-transform {open ? 'rotate-90' : ''}"
    />
    <div class="flex-1">
      <p class="text-sm font-semibold">{title}</p>
      {#if subtitle}
        <p class="text-xs text-fg-muted">{subtitle}</p>
      {/if}
    </div>
  </button>
  {#if open}
    <div class="border-t border-border px-2 pb-3 pt-2 sm:px-4">
      {@render children()}
    </div>
  {/if}
</section>
