<script lang="ts">
  import { page } from '$app/stores';
  import { Mic, ShoppingBasket, CookingPot, Sprout } from 'lucide-svelte';

  const items = [
    { href: '/voice', label: 'Voice', Icon: Mic },
    { href: '/grocery', label: 'Grocery', Icon: ShoppingBasket },
    { href: '/recipes', label: 'Recipes', Icon: CookingPot },
    { href: '/garden', label: 'Garden', Icon: Sprout },
  ] as const;

  const active = $derived($page.url.pathname);
</script>

<nav
  class="shrink-0 border-t border-border bg-surface/95 pb-[max(0.5rem,env(safe-area-inset-bottom))] backdrop-blur"
>
  <ul class="mx-auto flex max-w-xl">
    {#each items as item (item.href)}
      {@const isActive = active === item.href || active.startsWith(item.href + '/')}
      <li class="flex-1">
        <a
          href={item.href}
          class="flex flex-col items-center gap-1 py-2 text-xs transition-colors {isActive
            ? 'text-accent'
            : 'text-fg-muted hover:text-fg'}"
          aria-current={isActive ? 'page' : undefined}
        >
          <item.Icon class="size-5" />
          <span>{item.label}</span>
        </a>
      </li>
    {/each}
  </ul>
</nav>
