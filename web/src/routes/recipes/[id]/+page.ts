import { error } from '@sveltejs/kit';
import { requireAuth } from '$lib/auth/guard';
import { getRecipe } from '$lib/recipes/store';
import type { Recipe } from '$lib/api/recipes';
import { ApiFetchError } from '$lib/api/types';

export const load = async ({ params, url }) => {
  await requireAuth(url.pathname);
  try {
    const recipe: Recipe = await getRecipe(params.id);
    return { recipe };
  } catch (err) {
    if (err instanceof ApiFetchError && err.status === 404) {
      throw error(404, 'Recipe not found');
    }
    throw err;
  }
};
