import { error } from '@sveltejs/kit';
import { requireAdmin } from '$lib/auth/guard';
import { fetchSessionDetail } from '$lib/api/sessions';
import { ApiFetchError } from '$lib/api/types';

export const load = async ({ params, url }) => {
  await requireAdmin(url.pathname);
  try {
    const detail = await fetchSessionDetail(params.id);
    return { detail };
  } catch (err) {
    if (err instanceof ApiFetchError && err.status === 404) {
      throw error(404, 'Session not found');
    }
    throw err;
  }
};
