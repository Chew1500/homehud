import { requireAdmin } from '$lib/auth/guard';

// Belt-and-suspenders: explicitly opt out of SSR/prerender for this
// route so the build emits a client-side node even if the inherited
// layout config somehow isn't picked up.
export const ssr = false;
export const prerender = false;

export const load = async ({ url }) => {
  await requireAdmin(url.pathname);
  return {};
};
