"""PWA assets: manifest, service worker, and icon generation."""

from __future__ import annotations

import io
import logging

log = logging.getLogger("home-hud.telemetry.pwa")

MANIFEST_JSON = """\
{
  "name": "%(name)s",
  "short_name": "%(short_name)s",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#f5f7fa",
  "theme_color": "%(theme_color)s",
  "icons": [
    {"src": "/icons/192.png", "sizes": "192x192", "type": "image/png"},
    {"src": "/icons/512.png", "sizes": "512x512", "type": "image/png"}
  ]
}
"""

SERVICE_WORKER_JS = """\
const CACHE_NAME = 'homehud-v1';
const SHELL_URLS = ['/', '/audio-processor.js'];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then(c => c.addAll(SHELL_URLS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  // Never cache voice endpoint or API mutations
  if (url.pathname.startsWith('/api/voice') ||
      e.request.method !== 'GET') {
    return;
  }
  // Network-first for API, cache-first for shell
  if (url.pathname.startsWith('/api/')) {
    e.respondWith(
      fetch(e.request).then(res => {
        const clone = res.clone();
        caches.open(CACHE_NAME).then(c => c.put(e.request, clone));
        return res;
      }).catch(() => caches.match(e.request))
    );
  } else {
    e.respondWith(
      fetch(e.request).then(res => {
        const clone = res.clone();
        caches.open(CACHE_NAME).then(c => c.put(e.request, clone));
        return res;
      }).catch(() => caches.match(e.request))
    );
  }
});
"""


# Icon cache — generated once per process
_icon_cache: dict[int, bytes] = {}


def generate_icon(size: int, theme_color: str = "#3b82f6") -> bytes:
    """Generate a simple PWA icon as PNG bytes using Pillow."""
    if size in _icon_cache:
        return _icon_cache[size]

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        # Fallback: 1x1 transparent PNG
        log.warning("Pillow not available for icon generation")
        _icon_cache[size] = _minimal_png(size)
        return _icon_cache[size]

    img = Image.new("RGB", (size, size), theme_color)
    draw = ImageDraw.Draw(img)

    # Draw "HH" text centred
    font_size = size // 3
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            font_size,
        )
    except (OSError, IOError):
        font = ImageFont.load_default()

    text = "HH"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) // 2
    y = (size - th) // 2 - bbox[1]
    draw.text((x, y), text, fill="#ffffff", font=font)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    _icon_cache[size] = buf.getvalue()
    return _icon_cache[size]


def _minimal_png(size: int) -> bytes:
    """Generate a tiny solid-color PNG without Pillow."""
    # 1x1 blue PNG, will look blocky but functional
    import struct
    import zlib

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    # Raw image data: each row is filter byte (0) + RGB pixels
    row = b"\x00" + (b"\x3b\x82\xf6" * size)
    raw = row * size
    idat_data = zlib.compress(raw)
    return sig + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat_data) + _chunk(b"IEND", b"")


def get_manifest(config: dict) -> str:
    """Return the manifest JSON with config-driven values."""
    return MANIFEST_JSON % {
        "name": config.get("pwa_name", "Home HUD"),
        "short_name": config.get("pwa_short_name", "HUD"),
        "theme_color": config.get("pwa_theme_color", "#3b82f6"),
    }
