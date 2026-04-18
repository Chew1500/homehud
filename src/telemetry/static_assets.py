"""Serves the SvelteKit static build (web/dist) from the telemetry server.

Resolves a URL path to either a concrete file on disk or falls back to
``index.html`` so the SPA router can handle unknown non-API routes.
Guards against path traversal. Reports whether a hit is a Vite-hashed
immutable asset so the HTTP handler can choose the right cache header.
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger("home-hud.telemetry.static_assets")


class StaticAssets:
    """Loads and serves files from a built SvelteKit dist directory."""

    def __init__(self, dist_dir: str | Path):
        self.root = Path(dist_dir).resolve()
        self._index_html: bytes | None = None
        self._load_index()

    def _load_index(self) -> None:
        index_path = self.root / "index.html"
        if index_path.is_file():
            self._index_html = index_path.read_bytes()
            log.info("Loaded SPA shell from %s", index_path)
        else:
            log.warning(
                "SPA build not found at %s — run `make web-build` (or the CI "
                "deploy will produce it for you).",
                index_path,
            )

    @property
    def available(self) -> bool:
        return self._index_html is not None

    def reload(self) -> None:
        """Re-read index.html from disk (useful after a deploy)."""
        self._load_index()

    def resolve(
        self, url_path: str,
    ) -> tuple[Path | None, bytes | None, bool]:
        """Resolve a URL path to (file_path, index_bytes, is_hashed).

        - ``file_path`` set → serve that file.
        - ``index_bytes`` set → serve the SPA shell (with runtime config
          injected by the caller).
        - ``is_hashed`` → the file path is under Vite's immutable folder
          and may be served with ``Cache-Control: public, max-age=...
          immutable``.
        """
        rel = url_path.lstrip("/").split("?", 1)[0].split("#", 1)[0]

        # Root or empty → SPA shell
        if not rel or rel == "index.html":
            return None, self._index_html, False

        candidate = (self.root / rel).resolve()
        # Path traversal guard
        try:
            candidate.relative_to(self.root)
        except ValueError:
            return None, None, False

        if candidate.is_file():
            is_hashed = (
                "/_app/immutable/" in url_path
                or "/immutable/" in url_path
            )
            return candidate, None, is_hashed

        # SPA fallback for unknown non-API routes — only if index loaded.
        # Callers must decide whether to 404 on /api/* themselves.
        return None, self._index_html, False
