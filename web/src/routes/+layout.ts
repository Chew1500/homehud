import { browser } from '$app/environment';
import { refreshAuth } from '$lib/auth/store';

export const prerender = false;
export const ssr = false;
export const trailingSlash = 'never';

export async function load() {
  if (browser) {
    await refreshAuth();
  }
  return {};
}
