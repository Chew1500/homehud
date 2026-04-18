<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import BottomNav from '$lib/components/BottomNav.svelte';

  let { children } = $props();

  const hideNav = $derived(
    $page.url.pathname === '/login' || $page.url.pathname.startsWith('/admin'),
  );

  onMount(() => {
    if ('serviceWorker' in navigator && location.protocol === 'https:') {
      navigator.serviceWorker
        .register('/sw.js')
        .then((reg) => {
          // Force an update check on every mount so a new deploy gets
          // picked up the next time the user opens the PWA instead of
          // waiting for the browser's lazy update heuristics.
          reg.update().catch(() => {});
          // When a new SW takes control, force a reload so the fresh
          // bundle serves deep routes added in this deploy.
          let reloading = false;
          navigator.serviceWorker.addEventListener('controllerchange', () => {
            if (reloading) return;
            reloading = true;
            location.reload();
          });
        })
        .catch(() => {
          /* best-effort */
        });
    }
  });
</script>

<div class="flex h-[100dvh] flex-col">
  <main class="min-h-0 flex-1 overflow-hidden">
    {@render children()}
  </main>
  {#if !hideNav}
    <BottomNav />
  {/if}
</div>
