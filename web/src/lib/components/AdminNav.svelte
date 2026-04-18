<script lang="ts">
  import { page } from '$app/stores';
  import {
    LayoutDashboard,
    ListTree,
    ScrollText,
    Sliders,
    Volume2,
    Activity,
    LogOut,
    ArrowLeft,
  } from 'lucide-svelte';
  import { logout } from '$lib/auth/store';
  import { goto } from '$app/navigation';

  const items = [
    { href: '/admin', label: 'Overview', Icon: LayoutDashboard, exact: true },
    { href: '/admin/sessions', label: 'Sessions', Icon: ListTree },
    { href: '/admin/logs', label: 'Logs', Icon: ScrollText },
    { href: '/admin/config', label: 'Config', Icon: Sliders },
    { href: '/admin/voice-cache', label: 'Voice cache', Icon: Volume2 },
    { href: '/admin/services', label: 'Services', Icon: Activity },
  ] as const;

  const active = $derived($page.url.pathname);

  function isActive(href: string, exact: boolean) {
    return exact ? active === href : active === href || active.startsWith(href + '/');
  }

  async function handleLogout() {
    logout();
    await goto('/voice', { replaceState: true });
  }
</script>

<aside
  class="flex shrink-0 flex-row gap-1 overflow-x-auto border-b border-border bg-surface p-2 md:w-56 md:flex-col md:border-b-0 md:border-r md:p-4"
>
  <!-- Exit back to the user app. Leads the nav on mobile (horizontal
       strip) and sits above the Admin heading on desktop (sidebar),
       so it's always one tap away no matter how deep you are. -->
  <a
    href="/voice"
    class="flex shrink-0 items-center gap-2 whitespace-nowrap rounded-md border border-border px-3 py-2 text-sm text-fg-muted transition-colors hover:bg-surface-muted hover:text-fg md:border-0 md:px-2 md:py-1.5"
  >
    <ArrowLeft class="size-4" />
    <span>Back to app</span>
  </a>

  <div
    class="hidden border-t border-border/60 px-2 pb-1 pt-3 text-sm font-semibold text-fg-muted md:block"
  >
    Admin
  </div>

  {#each items as item (item.href)}
    {@const act = isActive(item.href, 'exact' in item ? item.exact : false)}
    <a
      href={item.href}
      class="flex items-center gap-2 whitespace-nowrap rounded-md px-3 py-2 text-sm transition-colors {act
        ? 'bg-accent/10 text-accent'
        : 'text-fg-muted hover:bg-surface-muted hover:text-fg'}"
    >
      <item.Icon class="size-4" />
      <span>{item.label}</span>
    </a>
  {/each}
  <div class="flex-1 md:mt-auto"></div>
  <button
    type="button"
    onclick={handleLogout}
    class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-fg-muted hover:bg-surface-muted hover:text-fg"
  >
    <LogOut class="size-4" />
    <span>Sign out</span>
  </button>
</aside>
