/* Home HUD service worker.
 *
 * Strategy:
 *   - never cache /api/voice (always network — session-specific audio + headers)
 *   - never cache non-GET
 *   - never cache HTML (navigation requests / .html responses). We MUST
 *     re-fetch the SPA shell on every navigation, otherwise a user who
 *     visited a route that later got a real page stays on the stale
 *     bundle that doesn't know about that route → spurious 404s.
 *   - cache-first for Vite's hashed immutable assets (_app/immutable/**)
 *   - network-only for /api/* (don't mask stale data)
 *
 * CACHE_NAME bumped → old caches purged on `activate`.
 */

const CACHE_NAME = 'homehud-spa-v3';

self.addEventListener('install', (event) => {
  // Skip waiting so the new SW takes over immediately.
  self.skipWaiting();
  // Don't precache the shell — we want every navigation to get a fresh
  // index.html from the server so deep routes work after new deploys.
  event.waitUntil(caches.open(CACHE_NAME));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))),
      )
      .then(() => self.clients.claim()),
  );
});

function isImmutableAsset(url) {
  return (
    url.pathname.startsWith('/_app/immutable/') ||
    url.pathname.startsWith('/fonts/') ||
    url.pathname.startsWith('/icons/')
  );
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // Voice + all API calls: straight to network, never cache. /api/*
  // responses change often and stale data is worse than a spinner.
  if (url.pathname.startsWith('/api/')) return;

  // Navigation requests (SPA shell fetches) and any HTML response:
  // pass through to the network, never cache. This guarantees a fresh
  // index.html after every deploy so the SPA router has all routes.
  if (req.mode === 'navigate' || req.destination === 'document') return;

  if (isImmutableAsset(url)) {
    event.respondWith(cacheFirst(req));
    return;
  }

  // Everything else (service worker file, manifest, audio-processor,
  // etc.): network with cache fallback.
  event.respondWith(networkFallback(req));
});

async function cacheFirst(req) {
  const cache = await caches.open(CACHE_NAME);
  const hit = await cache.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok) cache.put(req, res.clone());
  return res;
}

async function networkFallback(req) {
  const cache = await caches.open(CACHE_NAME);
  try {
    const res = await fetch(req);
    if (res.ok && !isHtml(res)) cache.put(req, res.clone());
    return res;
  } catch {
    const hit = await cache.match(req);
    if (hit) return hit;
    throw new Error('offline');
  }
}

function isHtml(res) {
  const ct = res.headers.get('Content-Type') || '';
  return ct.includes('text/html');
}
