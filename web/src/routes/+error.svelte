<!--
  Root error boundary. Shown when no nearer +error.svelte applies.
  Kept minimal — it inherits the theme from app.css but doesn't need
  the bottom nav or other chrome.
-->
<script lang="ts">
  import { page } from '$app/stores';
  import { AlertTriangle, Home, RefreshCw } from 'lucide-svelte';
</script>

<div class="flex h-[100dvh] items-center justify-center px-6">
  <div class="flex w-full max-w-md flex-col gap-4 rounded-2xl border border-border bg-surface p-6">
    <div class="flex items-start gap-3">
      <AlertTriangle class="mt-1 size-6 shrink-0 text-danger" />
      <div>
        <p class="text-2xl font-semibold">
          {$page.status}
          {$page.status === 404 ? 'Not found' : 'Error'}
        </p>
        <p class="mt-1 text-sm text-fg-muted">
          {$page.error?.message || 'Something went wrong.'}
        </p>
      </div>
    </div>
    <p class="font-mono text-xs text-fg-muted break-all">
      {$page.url.pathname}
    </p>
    <div class="flex gap-2">
      <a
        href="/voice"
        class="flex flex-1 items-center justify-center gap-1.5 rounded-full bg-accent px-3 py-2 text-sm font-medium text-accent-fg"
      >
        <Home class="size-4" />
        Home
      </a>
      <button
        type="button"
        onclick={() => location.reload()}
        class="flex flex-1 items-center justify-center gap-1.5 rounded-full border border-border px-3 py-2 text-sm text-fg-muted hover:text-fg"
      >
        <RefreshCw class="size-4" />
        Reload
      </button>
    </div>
  </div>
</div>
