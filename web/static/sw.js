/* Home HUD service worker.
 *
 * Minimal strategy for the scaffolding phase:
 *   - never cache /api/voice (always go to network — response is
 *     session-specific audio + headers)
 *   - never cache non-GET
 *   - network-first for /api/*  (stale backing store for flaky networks)
 *   - cache-first for Vite's hashed immutable assets (_app/immutable/**)
 *   - network-first for the SPA shell and everything else
 *
 * Cache name deliberately differs from the classic UI ('homehud-v2-grocery')
 * so that flipping ?ui=new wipes the old cache on activate.
 */

const CACHE_NAME = 'homehud-spa-v1';
const SHELL_URLS = ['/', '/audio-processor.js', '/manifest.webmanifest'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((c) => c.addAll(SHELL_URLS)));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))),
    ),
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  if (url.pathname.startsWith('/api/voice')) return;

  // Hashed immutable assets: cache-first, forever.
  if (url.pathname.startsWith('/_app/immutable/')) {
    event.respondWith(cacheFirst(req));
    return;
  }

  // Everything else: network-first with cache fallback.
  event.respondWith(networkFirst(req));
});

async function cacheFirst(req) {
  const cache = await caches.open(CACHE_NAME);
  const hit = await cache.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok) cache.put(req, res.clone());
  return res;
}

async function networkFirst(req) {
  const cache = await caches.open(CACHE_NAME);
  try {
    const res = await fetch(req);
    if (res.ok) cache.put(req, res.clone());
    return res;
  } catch {
    const hit = await cache.match(req);
    if (hit) return hit;
    throw new Error('offline');
  }
}
