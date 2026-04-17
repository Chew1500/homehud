import { requireAuth } from '$lib/auth/guard';

export const load = async ({ url }) => {
  await requireAuth(url.pathname);
  return {};
};
