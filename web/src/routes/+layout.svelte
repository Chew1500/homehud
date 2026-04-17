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
      navigator.serviceWorker.register('/sw.js').catch(() => {
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
