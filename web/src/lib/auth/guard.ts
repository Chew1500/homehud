/**
 * Route guard helpers used from ``+layout.ts`` / ``+page.ts`` load
 * functions. They throw SvelteKit redirects, which propagate through
 * the router.
 */

import { redirect } from '@sveltejs/kit';
import { config } from '$lib/config';
import { currentAuth, refreshAuth } from './store';

/**
 * Ensures the user is authenticated (or that auth is disabled entirely).
 * If not, redirects to /login with the current path preserved.
 */
export async function requireAuth(currentPath: string): Promise<void> {
  if (!config.authEnabled) return;
  let auth = currentAuth();
  if (!auth.initialised) auth = await refreshAuth();
  if (!auth.authenticated) {
    const qs = new URLSearchParams({ returnTo: currentPath });
    throw redirect(303, `/login?${qs.toString()}`);
  }
}

/**
 * Ensures the user is an admin. Non-admins are bounced to the user app.
 */
export async function requireAdmin(currentPath: string): Promise<void> {
  await requireAuth(currentPath);
  if (!config.authEnabled) return;
  const auth = currentAuth();
  if (!auth.isAdmin) {
    throw redirect(303, '/voice');
  }
}
