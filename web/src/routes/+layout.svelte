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
      // Attach the controllerchange listener BEFORE register() so that
      // a fast-activating new SW — one that claims clients during the
      // register() promise itself — doesn't slip past us and leave the
      // user stuck on a stale bundle.
      let reloading = false;
      const hadController = Boolean(navigator.serviceWorker.controller);
      navigator.serviceWorker.addEventListener('controllerchange', () => {
        if (reloading) return;
        reloading = true;
        location.reload();
      });

      navigator.serviceWorker
        .register('/sw.js')
        .then((reg) => {
          // Force an update check on every mount so a new deploy gets
          // picked up the next time the user opens the PWA instead of
          // waiting for the browser's lazy update heuristics.
          reg.update().catch(() => {});

          // If an installed SW is already waiting to activate, nudge
          // it along — this handles the case where the user refreshed
          // at just the right moment before controllerchange fired.
          if (reg.waiting && hadController) {
            reg.waiting.postMessage({ type: 'SKIP_WAITING' });
          }

          // Same treatment for a SW that installs mid-session.
          reg.addEventListener('updatefound', () => {
            const nw = reg.installing;
            if (!nw) return;
            nw.addEventListener('statechange', () => {
              if (nw.state === 'installed' && navigator.serviceWorker.controller) {
                nw.postMessage({ type: 'SKIP_WAITING' });
              }
            });
          });
        })
        .catch(() => {
          /* best-effort */
        });
    }
  });
</script>

<div class="flex h-[100dvh] flex-col">
  <main
    class="min-h-0 flex-1 overflow-hidden"
    class:pb-[calc(5rem+env(safe-area-inset-bottom))]={!hideNav}
  >
    {@render children()}
  </main>
  {#if !hideNav}
    <!-- Fixed positioning so the nav stays visible even on mobile
         browsers that resize the viewport mid-scroll (Android URL bar
         hide/show, PWA quirks, etc.). The ``pb-*`` on main reserves
         enough space (5rem + safe-area) to comfortably clear the nav
         with breathing room; the nav itself is ~65 px tall on Android
         and ~90 px on iOS with the home-indicator safe area. -->
    <div class="fixed inset-x-0 bottom-0 z-30">
      <BottomNav />
    </div>
  {/if}
</div>
