<script lang="ts">
  import AdminNav from '$lib/components/AdminNav.svelte';

  let { children } = $props();
</script>

<div class="mx-auto flex h-full w-full max-w-6xl flex-col md:flex-row">
  <AdminNav />
  <div class="min-h-0 flex-1 overflow-y-auto p-6">
    {@render children()}
  </div>
</div>
