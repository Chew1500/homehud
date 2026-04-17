<!--
  Pagination — reusable Prev/Next with a page-info pill in between.
  Emits the target offset via ``onPage`` rather than managing URL state
  itself, so the owning route decides whether to navigate or just
  reload data.
-->
<script lang="ts">
  import { ChevronLeft, ChevronRight } from 'lucide-svelte';

  interface Props {
    total: number;
    limit: number;
    offset: number;
    onPage: (newOffset: number) => void;
    label?: string;
  }

  let { total, limit, offset, onPage, label = 'items' }: Props = $props();

  const page = $derived(Math.floor(offset / limit) + 1);
  const pages = $derived(Math.max(1, Math.ceil(total / limit)));
  const prevDisabled = $derived(offset <= 0);
  const nextDisabled = $derived(offset + limit >= total);
</script>

<div class="flex items-center justify-between gap-2 text-sm">
  <button
    type="button"
    onclick={() => onPage(Math.max(0, offset - limit))}
    disabled={prevDisabled}
    class="flex items-center gap-1 rounded-full border border-border px-3 py-1.5 text-xs text-fg-muted hover:bg-surface-muted hover:text-fg disabled:opacity-40"
  >
    <ChevronLeft class="size-3.5" />
    Prev
  </button>
  <span class="text-xs text-fg-muted">
    Page {page} of {pages}
    <span class="mx-1">·</span>
    <span class="font-mono">{total}</span>
    {label}
  </span>
  <button
    type="button"
    onclick={() => onPage(offset + limit)}
    disabled={nextDisabled}
    class="flex items-center gap-1 rounded-full border border-border px-3 py-1.5 text-xs text-fg-muted hover:bg-surface-muted hover:text-fg disabled:opacity-40"
  >
    Next
    <ChevronRight class="size-3.5" />
  </button>
</div>
