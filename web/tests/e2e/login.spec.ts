/**
 * End-to-end: login flow.
 *
 * Assumes the Python server is running with ``web_auth_enabled=true``
 * and the SPA has been built (or Vite dev is proxying). Not run in CI
 * automatically — use ``pnpm run test:e2e`` locally.
 */

import { expect, test } from '@playwright/test';

test('shows pairing screen when authEnabled and no token', async ({ page }) => {
  await page.addInitScript(() => {
    const cfg = document.getElementById('hud-config');
    if (cfg) cfg.textContent = JSON.stringify({ authEnabled: true, voiceThreadTtlMs: 300000 });
  });
  await page.goto('/voice');
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByText(/pair this device/i)).toBeVisible();
});
