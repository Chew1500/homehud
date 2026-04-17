<script lang="ts">
  import { ExternalLink, Wrench } from 'lucide-svelte';
</script>

<div class="flex flex-col gap-4">
  <div>
    <h1 class="text-2xl font-semibold">Admin</h1>
    <p class="mt-1 text-sm text-fg-muted">
      Overview, sessions, logs, config, voice cache, and services.
    </p>
  </div>

  <div
    class="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4 text-sm"
  >
    <div class="flex items-start gap-3">
      <Wrench class="mt-0.5 size-5 shrink-0 text-accent" />
      <div class="flex-1">
        <p class="font-medium text-fg">Admin tools are still on the classic UI.</p>
        <p class="mt-1 text-fg-muted">
          Tabs on the left will be ported one by one. Until then, the classic dashboard
          has everything you need.
        </p>
      </div>
    </div>
    <a
      href="/?ui=old"
      class="flex w-fit items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-xs font-medium text-fg hover:bg-surface-muted"
    >
      Open classic admin
      <ExternalLink class="size-3" />
    </a>
  </div>
</div>
