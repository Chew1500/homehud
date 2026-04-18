<!--
  Admin error boundary. Renders inside the admin layout so the sidebar
  stays visible when a nested route fails (or doesn't match). Friendlier
  than SvelteKit's default plain "404 Not Found".
-->
<script lang="ts">
  import { page } from '$app/stores';
  import { AlertTriangle, ArrowLeft, RefreshCw } from 'lucide-svelte';
</script>

<div class="flex flex-col gap-4">
  <div class="flex items-start gap-3 rounded-xl border border-danger/40 bg-danger/10 p-4">
    <AlertTriangle class="mt-0.5 size-5 shrink-0 text-danger" />
    <div class="flex-1">
      <p class="font-semibold text-fg">
        {$page.status}
        {$page.status === 404 ? 'Not found' : 'Error'}
      </p>
      <p class="mt-1 text-sm text-fg-muted">
        {$page.error?.message || 'Something went wrong loading this page.'}
      </p>
      <p class="mt-2 font-mono text-xs text-fg-muted break-all">
        {$page.url.pathname}
      </p>
    </div>
  </div>

  <div class="flex gap-2">
    <a
      href="/admin"
      class="flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-sm text-fg-muted hover:text-fg"
    >
      <ArrowLeft class="size-4" />
      Back to Overview
    </a>
    <button
      type="button"
      onclick={() => location.reload()}
      class="flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-sm text-fg-muted hover:text-fg"
    >
      <RefreshCw class="size-4" />
      Reload
    </button>
  </div>
</div>
