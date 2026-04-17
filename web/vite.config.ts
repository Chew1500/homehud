import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [tailwindcss(), sveltekit()],
  server: {
    port: 5173,
    proxy: {
      // Forward API calls + same-origin static assets to the Python
      // server during `pnpm run dev`. Assumes the Python server is
      // running at http://127.0.0.1:8080 with ?ui=old (default).
      '/api': 'http://127.0.0.1:8080',
      '/audio-processor.js': 'http://127.0.0.1:8080',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/unit/setup.ts'],
    include: ['tests/unit/**/*.{test,spec}.ts'],
  },
});
