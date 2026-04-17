<!--
  Garden — ambient watering advisory.

  Reads from /api/garden on mount. Layout: zone cards at the top (the
  "should I water?" answer), then expandable detail sections for water
  balance, forecast, and recent watering events.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { AlertCircle, CloudRain, Leaf } from 'lucide-svelte';
  import ZoneCard from '$lib/components/garden/ZoneCard.svelte';
  import CollapsibleSection from '$lib/components/garden/CollapsibleSection.svelte';
  import { garden, loadGarden } from '$lib/garden/store';
  import { formatInches, friendlyDate, mmToInches } from '$lib/garden/units';

  const state = $derived($garden);
  const data = $derived(state.data);

  const summary = $derived.by(() => {
    if (!data) return null;
    const totalRainMm = data.history.reduce((a, d) => a + d.precipitation_mm, 0);
    const totalEtMm = data.history.reduce((a, d) => a + d.et0_mm, 0);
    const forecastRain = data.zones[0]?.forecast_rain_inches ?? 0;
    return {
      rainInches: mmToInches(totalRainMm),
      etInches: mmToInches(totalEtMm),
      netInches: mmToInches(totalRainMm - totalEtMm),
      forecastRain,
    };
  });

  onMount(() => {
    loadGarden();
  });
</script>

<div class="h-full overflow-y-auto">
  <div
    class="mx-auto flex w-full max-w-xl flex-col gap-4 px-4 pb-8 pt-[max(1rem,env(safe-area-inset-top))]"
  >
    <header class="flex items-center gap-2">
      <Leaf class="size-6 text-success" />
      <h1 class="text-2xl font-semibold">Garden</h1>
    </header>

    {#if state.error}
      <div
        class="flex items-start gap-2 rounded-xl border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger"
      >
        <AlertCircle class="mt-0.5 size-4 shrink-0" />
        <span>{state.error}</span>
      </div>
    {/if}

    {#if state.loading && !data}
      <p class="py-8 text-center text-sm text-fg-muted">Loading…</p>
    {:else if data && !data.enabled}
      <div
        class="flex flex-col gap-2 rounded-xl border border-border bg-surface p-4 text-sm text-fg-muted"
      >
        <p class="text-fg">Garden watering advisory is off.</p>
        <p>
          Flip <span class="font-mono text-xs text-fg">garden_enabled = true</span>
          in the admin Config tab to start tracking rainfall, ET₀, and zone deficits.
        </p>
      </div>
    {:else if data}
      <!-- Zones -->
      {#if data.zones.length === 0}
        <div class="rounded-xl border border-border bg-surface p-4 text-sm text-fg-muted">
          No zones configured.
        </div>
      {:else}
        <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {#each data.zones as zone (zone.label)}
            <ZoneCard {zone} />
          {/each}
        </div>
      {/if}

      <!-- Summary pill -->
      {#if summary && (summary.rainInches > 0 || summary.forecastRain > 0)}
        <div
          class="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl border border-border bg-surface px-4 py-3 text-sm"
        >
          <span class="flex items-center gap-1 text-fg-muted">
            <CloudRain class="size-4" />
            <span>7-day rain</span>
            <span class="font-mono text-fg">{formatInches(summary.rainInches)}</span>
          </span>
          <span class="flex items-center gap-1 text-fg-muted">
            <span>Net</span>
            <span
              class="font-mono"
              class:text-success={summary.netInches >= 0}
              class:text-warn={summary.netInches < 0}
            >
              {summary.netInches >= 0 ? '+' : ''}{summary.netInches.toFixed(2)}"
            </span>
          </span>
          {#if summary.forecastRain > 0}
            <span class="flex items-center gap-1 text-fg-muted">
              <span>3-day forecast</span>
              <span class="font-mono text-fg">{formatInches(summary.forecastRain)}</span>
            </span>
          {/if}
        </div>
      {/if}

      <!-- Water balance -->
      <CollapsibleSection title="Water balance" subtitle="Last 7 days">
        {#if data.history.length === 0}
          <p class="p-3 text-sm text-fg-muted">No history yet.</p>
        {:else}
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="text-[0.65rem] uppercase tracking-wide text-fg-muted">
                <tr>
                  <th class="py-1.5 pr-2 text-left font-medium">Date</th>
                  <th class="py-1.5 pr-2 text-right font-medium">Rain</th>
                  <th class="py-1.5 pr-2 text-right font-medium">ET₀</th>
                  <th class="py-1.5 pr-2 text-right font-medium">Net</th>
                  <th class="py-1.5 text-right font-medium">High</th>
                </tr>
              </thead>
              <tbody class="font-mono text-xs">
                {#each data.history as d (d.date)}
                  {@const net = d.precipitation_mm - d.et0_mm}
                  <tr class="border-t border-border">
                    <td class="py-1.5 pr-2 text-left">{friendlyDate(d.date)}</td>
                    <td class="py-1.5 pr-2 text-right">{d.precipitation_mm.toFixed(1)}</td>
                    <td class="py-1.5 pr-2 text-right">{d.et0_mm.toFixed(1)}</td>
                    <td
                      class="py-1.5 pr-2 text-right"
                      class:text-success={net >= 0}
                      class:text-warn={net < 0}
                    >
                      {net >= 0 ? '+' : ''}{net.toFixed(1)}
                    </td>
                    <td class="py-1.5 text-right">{d.temp_max_f.toFixed(0)}°</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </CollapsibleSection>

      <!-- Forecast -->
      <CollapsibleSection title="Forecast" subtitle="Next 5 days" defaultOpen={false}>
        {#if data.forecast.length === 0}
          <p class="p-3 text-sm text-fg-muted">No forecast available.</p>
        {:else}
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="text-[0.65rem] uppercase tracking-wide text-fg-muted">
                <tr>
                  <th class="py-1.5 pr-2 text-left font-medium">Date</th>
                  <th class="py-1.5 pr-2 text-right font-medium">Rain</th>
                  <th class="py-1.5 pr-2 text-right font-medium">Prob</th>
                  <th class="py-1.5 pr-2 text-right font-medium">ET₀</th>
                  <th class="py-1.5 text-right font-medium">High</th>
                </tr>
              </thead>
              <tbody class="font-mono text-xs">
                {#each data.forecast as d (d.date)}
                  <tr class="border-t border-border">
                    <td class="py-1.5 pr-2 text-left">{friendlyDate(d.date)}</td>
                    <td class="py-1.5 pr-2 text-right">{d.precipitation_mm.toFixed(1)}</td>
                    <td class="py-1.5 pr-2 text-right">{d.precipitation_probability}%</td>
                    <td class="py-1.5 pr-2 text-right">{d.et0_mm.toFixed(1)}</td>
                    <td class="py-1.5 text-right">{d.temp_max_f.toFixed(0)}°</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </CollapsibleSection>

      <!-- Watering log -->
      <CollapsibleSection
        title="Watering log"
        subtitle="Last 14 days"
        defaultOpen={false}
      >
        {#if data.watering_events.length === 0}
          <p class="p-3 text-sm text-fg-muted">No watering events recorded.</p>
        {:else}
          <ul class="flex flex-col divide-y divide-border">
            {#each data.watering_events as ev (ev.timestamp + ev.zone)}
              <li class="flex items-center justify-between py-2 text-sm">
                <div>
                  <p class="font-medium text-fg">{ev.zone}</p>
                  <p class="text-xs text-fg-muted">
                    {friendlyDate(ev.timestamp)} · {ev.timestamp.slice(11, 16)}
                  </p>
                </div>
                <span class="font-mono text-sm text-accent">
                  {ev.amount_inches.toFixed(2)}"
                </span>
              </li>
            {/each}
          </ul>
        {/if}
      </CollapsibleSection>
    {/if}
  </div>
</div>
