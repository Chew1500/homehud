import { requireAdmin } from '$lib/auth/guard';

export const load = async ({ url }) => {
  await requireAdmin(url.pathname);
  return {};
};
