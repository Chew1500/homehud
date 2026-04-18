"""Lightweight web server for the telemetry dashboard."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import struct
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from telemetry.static_assets import StaticAssets

log = logging.getLogger("home-hud.telemetry.web")

# Mime lookup for SPA static assets served from web/dist.
_STATIC_MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript",
    ".mjs": "application/javascript",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".webmanifest": "application/manifest+json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".map": "application/json",
    ".txt": "text/plain; charset=utf-8",
}

# Regex for /api/sessions/<uuid>
_SESSION_RE = re.compile(r"^/api/sessions/([0-9a-f-]+)$")
# Regex for /api/tts-cache/<hash>/audio
_TTS_CACHE_RE = re.compile(r"^/api/tts-cache/([0-9a-f]{64})/audio$")
# Regex for /api/monitor/services/<id> and /api/monitor/services/<id>/history
_MONITOR_SVC_RE = re.compile(r"^/api/monitor/services/(\d+)$")
_MONITOR_HIST_RE = re.compile(r"^/api/monitor/services/(\d+)/history$")
# Regex for /api/recipes/<id>
_RECIPE_RE = re.compile(r"^/api/recipes/([0-9a-f-]+)$")
# Regex for /api/grocery/<id>
_GROCERY_RE = re.compile(r"^/api/grocery/([0-9a-f]+)$")

# Log line parsing: matches "2024-01-15 10:30:45,123 [INFO] home-hud: message"
_LOG_LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})"  # timestamp
    r" \[(\w+)\]"  # level
    r" ([\w.\-]+):"  # logger name
    r" (.*)$"  # message
)
_LEVEL_ORDER = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}




# Paths that never require authentication. SPA asset paths (``/``,
# ``/_app/*``, ``/manifest.webmanifest``, etc.) are served via
# ``_serve_static`` *before* ``_authenticate`` runs, so they don't
# need to be listed here.
_AUTH_EXEMPT = frozenset({"/api/health"})
_AUTH_EXEMPT_PREFIXES = ("/api/auth/",)


class _Handler(BaseHTTPRequestHandler):
    """Request handler — routes to dashboard or JSON API endpoints."""

    def setup(self):
        self.request.settimeout(60)
        super().setup()

    def log_message(self, format, *args):  # noqa: A002
        log.debug(format, *args)

    def _identify_user(self) -> str:
        """Best-effort user identification (never rejects).

        Tries Tailscale identity, then Bearer token, then falls back
        to "anonymous".  Used by endpoints that want to know who the
        caller is without enforcing auth.
        """
        auth_mgr = getattr(self.server, "auth_manager", None)
        if auth_mgr is None:
            return "anonymous"

        client_ip = self.client_address[0]
        if client_ip in ("127.0.0.1", "::1"):
            return "localhost"

        if client_ip.startswith("100."):
            ts_user = auth_mgr.check_tailscale_identity(client_ip)
            if ts_user:
                return ts_user

        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            payload = auth_mgr.verify_token(token)
            if payload and auth_mgr.is_registered(payload.get("uid", "")):
                return payload["uid"]

        return "anonymous"

    def _authenticate(self, path: str) -> str | None:
        """Check authentication. Returns user_id or None (sends 401).

        Returns "anonymous" and skips auth when auth is disabled or the
        path is exempt.
        """
        auth_mgr = getattr(self.server, "auth_manager", None)
        if auth_mgr is None:
            return "anonymous"

        # Exempt paths (no auth required)
        if path in _AUTH_EXEMPT or any(
            path.startswith(p) for p in _AUTH_EXEMPT_PREFIXES
        ):
            return "anonymous"

        # Full identity check with 401 on failure
        user_id = self._identify_user()
        if user_id == "anonymous":
            self._send_json(
                {"error": "Unauthorized"}, HTTPStatus.UNAUTHORIZED,
            )
            return None
        return user_id

    def _is_admin(self, user_id: str) -> bool:
        """Check if a user has admin privileges."""
        if user_id in ("localhost", "anonymous"):
            return True
        auth_mgr = getattr(self.server, "auth_manager", None)
        if auth_mgr is None:
            return True  # no auth = everyone is admin
        return auth_mgr.is_admin(user_id)

    def _require_admin(self, user_id: str) -> bool:
        """Check admin access; sends 403 if not. Returns True if allowed."""
        if self._is_admin(user_id):
            return True
        self._send_json(
            {"error": "Admin access required"}, HTTPStatus.FORBIDDEN,
        )
        return False

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        params = parse_qs(parsed.query)

        # Everything that isn't an API call is an SPA route or bundle
        # asset — serve straight from web/dist/. The SPA shell itself
        # is public; the SvelteKit router handles the login screen
        # client-side by consulting /api/auth/status (which is auth-
        # exempt on the server).
        if not path.startswith("/api/"):
            self._serve_static(path)
            return

        user_id = self._authenticate(path)
        if user_id is None:
            return

        if path == "/api/health":
            self._send_json({"ok": True})
        elif path == "/api/stats":
            if self._require_admin(user_id):
                self._handle_stats()
        elif path == "/api/config":
            if self._require_admin(user_id):
                self._handle_config()
        elif path == "/api/display":
            if self._require_admin(user_id):
                self._handle_display()
        elif path == "/api/logs":
            if self._require_admin(user_id):
                self._handle_logs(params)
        elif path == "/api/sessions":
            if self._require_admin(user_id):
                self._handle_sessions(params)
        elif path == "/api/tts-cache":
            if self._require_admin(user_id):
                self._handle_tts_cache_list()
        elif m := _TTS_CACHE_RE.match(path):
            if self._require_admin(user_id):
                self._handle_tts_cache_audio(m.group(1))
        elif path == "/api/garden":
            self._handle_garden()
        elif path == "/api/monitor/services":
            if self._require_admin(user_id):
                self._handle_monitor_list()
        elif m := _MONITOR_HIST_RE.match(path):
            if self._require_admin(user_id):
                self._handle_monitor_history(int(m.group(1)), params)
        elif m := _MONITOR_SVC_RE.match(path):
            if self._require_admin(user_id):
                self._handle_monitor_detail(int(m.group(1)))
        elif m := _SESSION_RE.match(path):
            if self._require_admin(user_id):
                self._handle_session_detail(m.group(1))
        elif path == "/api/recipes":
            self._handle_recipes_list()
        elif m := _RECIPE_RE.match(path):
            self._handle_recipe_detail(m.group(1))
        elif path == "/api/grocery":
            self._handle_grocery_get()
        elif path == "/api/auth/status":
            # Use _identify_user for best-effort identity (even on
            # exempt paths where _authenticate returns "anonymous")
            real_id = self._identify_user()
            self._send_json({
                "authenticated": real_id != "anonymous",
                "user_id": real_id,
                "admin": self._is_admin(real_id),
            })
        else:
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        user_id = self._authenticate(path)
        if user_id is None:
            return

        if path == "/api/config":
            if self._require_admin(user_id):
                self._handle_config_save()
        elif path == "/api/voice":
            self._handle_voice()
        elif path == "/api/text":
            self._handle_text()
        elif path == "/api/conversation/reset":
            self._handle_conversation_reset()
        elif path == "/api/auth/pair":
            self._handle_auth_pair()
        elif path == "/api/auth/generate-code":
            if self._require_admin(user_id):
                self._handle_auth_generate_code()
        elif path == "/api/monitor/services":
            self._handle_monitor_add()
        elif path == "/api/monitor/test":
            self._handle_monitor_test()
        elif path == "/api/recipes/upload-image":
            self._handle_recipe_upload_image()
        elif path == "/api/recipes":
            self._handle_recipe_create()
        elif path == "/api/grocery":
            self._handle_grocery_add()
        elif path == "/api/grocery/reorder":
            self._handle_grocery_reorder()
        elif path == "/api/grocery/category-order":
            self._handle_grocery_category_order()
        elif path == "/api/grocery/clear-checked":
            self._handle_grocery_clear_checked()
        else:
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_DELETE(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        user_id = self._authenticate(path)
        if user_id is None:
            return

        if m := _MONITOR_SVC_RE.match(path):
            self._handle_monitor_remove(int(m.group(1)))
        elif m := _RECIPE_RE.match(path):
            self._handle_recipe_delete(m.group(1))
        elif m := _GROCERY_RE.match(path):
            self._handle_grocery_delete(m.group(1))
        else:
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_PATCH(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        user_id = self._authenticate(path)
        if user_id is None:
            return

        if m := _MONITOR_SVC_RE.match(path):
            self._handle_monitor_update(int(m.group(1)))
        elif m := _RECIPE_RE.match(path):
            self._handle_recipe_update(m.group(1))
        elif m := _GROCERY_RE.match(path):
            self._handle_grocery_update(m.group(1))
        else:
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    # --- API handlers ---

    def _handle_config(self):
        config = getattr(self.server, "config", None)
        if config is None:
            self._send_json({"error": "Config not available"})
            return
        from config import get_config_metadata

        self._send_json(get_config_metadata(config))

    def _handle_config_save(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            self._send_json({"error": "Invalid JSON"}, HTTPStatus.BAD_REQUEST)
            return

        from config import CONFIG_REGISTRY, save_config_file

        valid_keys = {p.key for p in CONFIG_REGISTRY if not p.sensitive}
        filtered = {k: v for k, v in body.items() if k in valid_keys}

        if not filtered:
            self._send_json({"error": "No valid parameters"}, HTTPStatus.BAD_REQUEST)
            return

        try:
            save_config_file(filtered)
        except OSError as e:
            self._send_json(
                {"error": f"Failed to save: {e}"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return

        self._send_json({
            "saved": True,
            "restart_required": True,
            "keys": list(filtered.keys()),
        })

    def _handle_auth_pair(self):
        """POST /api/auth/pair — submit pairing code, get auth token."""
        auth_mgr = getattr(self.server, "auth_manager", None)
        if auth_mgr is None:
            self._send_json(
                {"error": "Auth not enabled"}, HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            self._send_json({"error": "Invalid JSON"}, HTTPStatus.BAD_REQUEST)
            return

        code = str(body.get("code", "")).strip()
        if not code:
            self._send_json(
                {"error": "Missing 'code' field"}, HTTPStatus.BAD_REQUEST,
            )
            return

        user_id = auth_mgr.verify_pairing_code(code)
        if user_id is None:
            self._send_json(
                {"error": "Invalid or expired code"}, HTTPStatus.UNAUTHORIZED,
            )
            return

        token = auth_mgr.create_token(user_id, source="pairing")
        self._send_json({"token": token, "user_id": user_id})

    def _handle_auth_generate_code(self):
        """POST /api/auth/generate-code — generate a new pairing code.

        Only accessible from localhost or authenticated users.
        """
        auth_mgr = getattr(self.server, "auth_manager", None)
        if auth_mgr is None:
            self._send_json(
                {"error": "Auth not enabled"}, HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return

        # Only allow from localhost or authenticated users
        client_ip = self.client_address[0]
        if client_ip not in ("127.0.0.1", "::1"):
            auth_header = self.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                self._send_json(
                    {"error": "Unauthorized"}, HTTPStatus.UNAUTHORIZED,
                )
                return
            payload = auth_mgr.verify_token(auth_header[7:])
            if not payload:
                self._send_json(
                    {"error": "Unauthorized"}, HTTPStatus.UNAUTHORIZED,
                )
                return

        code = auth_mgr.generate_pairing_code()
        self._send_json({"code": code, "expires_in": 300})

    def _handle_voice(self):
        """POST /api/voice — accept PCM/WAV audio, return WAV response."""
        handler = getattr(self.server, "voice_handler", None)
        if handler is None:
            self._send_json(
                {"error": "Voice not available"},
                HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return

        # Read request body
        try:
            length = int(self.headers.get("Content-Length", 0))
        except (ValueError, TypeError):
            self._send_json({"error": "Missing Content-Length"}, HTTPStatus.BAD_REQUEST)
            return

        max_size = 1_048_576  # 1 MB (~30s of 16kHz mono int16)
        if length <= 0 or length > max_size:
            self._send_json(
                {"error": f"Content-Length must be 1–{max_size} bytes"},
                HTTPStatus.BAD_REQUEST,
            )
            return

        body = self.rfile.read(length)
        content_type = (self.headers.get("Content-Type") or "").lower()

        # Strip WAV header if the client sent audio/wav
        if content_type.startswith("audio/wav") or content_type.startswith("audio/x-wav"):
            if len(body) > 44 and body[:4] == b"RIFF":
                body = body[44:]

        try:
            wav_bytes, metadata = handler.handle_voice_request(body)
        except Exception:
            log.exception("Voice handler error")
            self._send_json(
                {"error": "Voice processing failed"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return

        # Return WAV audio with metadata in headers
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(wav_bytes)))
        self.send_header("X-Transcription",
                         quote(metadata.get("transcription", ""), safe=""))
        self.send_header("X-Response-Text",
                         quote(metadata.get("response_text", ""), safe=""))
        self.send_header("X-Thread-Active",
                         "1" if metadata.get("thread_active") else "0")
        self.send_header("Access-Control-Expose-Headers",
                         "X-Transcription, X-Response-Text, X-Thread-Active")
        self.end_headers()
        self.wfile.write(wav_bytes)

    def _handle_text(self):
        """POST /api/text — accept JSON {text}, return JSON response.

        Shares the IntentRouter and LLM history with /api/voice, so voice
        and text turns live in the same conversation thread.
        """
        handler = getattr(self.server, "voice_handler", None)
        if handler is None:
            self._send_json(
                {"error": "Voice not available"},
                HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
        except (ValueError, TypeError):
            self._send_json(
                {"error": "Missing Content-Length"}, HTTPStatus.BAD_REQUEST,
            )
            return

        if length <= 0 or length > 16_384:
            self._send_json(
                {"error": "Content-Length must be 1–16384 bytes"},
                HTTPStatus.BAD_REQUEST,
            )
            return

        try:
            body = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            self._send_json({"error": "Invalid JSON"}, HTTPStatus.BAD_REQUEST)
            return

        text = str(body.get("text", "")).strip()
        if not text:
            self._send_json(
                {"error": "Missing 'text' field"}, HTTPStatus.BAD_REQUEST,
            )
            return

        try:
            metadata = handler.handle_text_request(text)
        except Exception:
            log.exception("Text handler error")
            self._send_json(
                {"error": "Text processing failed"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return

        self._send_json({
            "transcription": metadata.get("transcription", ""),
            "response_text": metadata.get("response_text", ""),
            "thread_active": bool(metadata.get("thread_active")),
            "expects_follow_up": bool(metadata.get("expects_follow_up")),
            "error": metadata.get("error"),
        })

    def _handle_conversation_reset(self):
        """POST /api/conversation/reset — clear LLM history + follow-up state."""
        handler = getattr(self.server, "voice_handler", None)
        if handler is None:
            self._send_json(
                {"error": "Voice not available"},
                HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return
        try:
            handler.reset_conversation()
        except Exception:
            log.exception("Conversation reset failed")
            self._send_json(
                {"error": "Reset failed"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return
        self._send_json({"ok": True})

    def _handle_display(self):
        snapshot_path = getattr(self.server, "display_snapshot_path", None)
        if not snapshot_path:
            self._send_json(
                {"error": "Display snapshot not configured"}, HTTPStatus.NOT_FOUND
            )
            return
        p = Path(snapshot_path)
        if not p.is_file():
            self._send_json(
                {"error": "No display snapshot available"}, HTTPStatus.NOT_FOUND
            )
            return
        try:
            body = p.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            self._send_json(
                {"error": "Failed to read snapshot"}, HTTPStatus.INTERNAL_SERVER_ERROR
            )

    def _handle_stats(self):
        db = self.server.db_path
        conn = _ro_connect(db)
        try:
            row = conn.execute(
                "SELECT"
                "  COUNT(*) AS total_sessions,"
                "  (SELECT COUNT(*) FROM exchanges) AS total_exchanges,"
                "  (SELECT COUNT(*) FROM llm_calls) AS total_llm_calls,"
                "  (SELECT COALESCE(SUM(input_tokens), 0) FROM llm_calls) AS total_input_tokens,"
                "  (SELECT COALESCE(SUM(output_tokens), 0) FROM llm_calls) AS total_output_tokens,"
                "  (SELECT COUNT(*) FROM exchanges WHERE error IS NOT NULL) AS error_count,"
                "  (SELECT COUNT(*) FROM exchanges"
                "    WHERE routing_path LIKE 'rejected_%') AS rejected_count,"
                "  (SELECT AVG(recording_duration_ms) FROM exchanges"
                "    WHERE recording_duration_ms IS NOT NULL) AS avg_recording_ms,"
                "  (SELECT AVG(stt_duration_ms) FROM exchanges"
                "    WHERE stt_duration_ms IS NOT NULL) AS avg_stt_ms,"
                "  (SELECT AVG(routing_duration_ms) FROM exchanges"
                "    WHERE routing_duration_ms IS NOT NULL) AS avg_routing_ms,"
                "  (SELECT AVG(tts_duration_ms) FROM exchanges"
                "    WHERE tts_duration_ms IS NOT NULL) AS avg_tts_ms,"
                "  (SELECT AVG(playback_duration_ms) FROM exchanges"
                "    WHERE playback_duration_ms IS NOT NULL)"
                "    AS avg_playback_ms,"
                "  (SELECT AVG(CAST("
                "    (julianday(stt_started_at)"
                "     - julianday(recording_ended_at))"
                "    * 86400000 AS INTEGER))"
                "    FROM exchanges"
                "    WHERE stt_started_at IS NOT NULL"
                "    AND recording_ended_at IS NOT NULL)"
                "    AS avg_rec_to_stt_gap_ms,"
                "  (SELECT AVG(CAST("
                "    (julianday(routing_started_at)"
                "     - julianday(stt_ended_at))"
                "    * 86400000 AS INTEGER))"
                "    FROM exchanges"
                "    WHERE routing_started_at IS NOT NULL"
                "    AND stt_ended_at IS NOT NULL)"
                "    AS avg_stt_to_routing_gap_ms,"
                "  (SELECT AVG(CAST("
                "    (julianday(tts_started_at)"
                "     - julianday(routing_ended_at))"
                "    * 86400000 AS INTEGER))"
                "    FROM exchanges"
                "    WHERE tts_started_at IS NOT NULL"
                "    AND routing_ended_at IS NOT NULL)"
                "    AS avg_routing_to_tts_gap_ms,"
                "  (SELECT AVG(CAST("
                "    (julianday(playback_started_at)"
                "     - julianday(tts_ended_at))"
                "    * 86400000 AS INTEGER))"
                "    FROM exchanges"
                "    WHERE playback_started_at IS NOT NULL"
                "    AND tts_ended_at IS NOT NULL)"
                "    AS avg_tts_to_playback_gap_ms,"
                "  (SELECT AVG(CAST("
                "    (julianday(playback_ended_at)"
                "     - julianday(recording_started_at))"
                "    * 86400000 AS INTEGER))"
                "    FROM exchanges"
                "    WHERE playback_ended_at IS NOT NULL"
                "    AND recording_started_at IS NOT NULL)"
                "    AS avg_wall_clock_ms"
                " FROM sessions"
            ).fetchone()

            data = dict(row)

            # Feature counts
            feature_rows = conn.execute(
                "SELECT matched_feature, COUNT(*) AS cnt FROM exchanges"
                " WHERE matched_feature IS NOT NULL"
                " GROUP BY matched_feature ORDER BY cnt DESC"
            ).fetchall()
            data["feature_counts"] = {r["matched_feature"]: r["cnt"] for r in feature_rows}

            # Routing counts
            routing_rows = conn.execute(
                "SELECT routing_path, COUNT(*) AS cnt FROM exchanges"
                " WHERE routing_path IS NOT NULL"
                " GROUP BY routing_path ORDER BY cnt DESC"
            ).fetchall()
            data["routing_counts"] = {r["routing_path"]: r["cnt"] for r in routing_rows}

            # Today counts
            today_row = conn.execute(
                "SELECT"
                "  (SELECT COUNT(*) FROM sessions"
                "    WHERE started_at >= date('now')) AS sessions_today,"
                "  (SELECT COUNT(*) FROM exchanges"
                "    WHERE created_at >= date('now')) AS exchanges_today"
            ).fetchone()
            data["sessions_today"] = today_row["sessions_today"]
            data["exchanges_today"] = today_row["exchanges_today"]

            self._send_json(data)
        finally:
            conn.close()

    def _handle_sessions(self, params):
        limit = min(int(params.get("limit", [50])[0]), 200)
        offset = max(int(params.get("offset", [0])[0]), 0)

        db = self.server.db_path
        conn = _ro_connect(db)
        try:
            total = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]

            rows = conn.execute(
                "SELECT s.id, s.started_at, s.ended_at, s.exchange_count, s.wake_model"
                " FROM sessions s ORDER BY s.started_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()

            sessions = []
            for r in rows:
                sid = r["id"]

                # Duration
                duration_ms = None
                if r["started_at"] and r["ended_at"]:
                    from datetime import datetime

                    t0 = datetime.fromisoformat(r["started_at"])
                    t1 = datetime.fromisoformat(r["ended_at"])
                    duration_ms = int((t1 - t0).total_seconds() * 1000)

                # First transcription
                first = conn.execute(
                    "SELECT transcription FROM exchanges"
                    " WHERE session_id = ? ORDER BY sequence ASC LIMIT 1",
                    (sid,),
                ).fetchone()

                # Features used
                feat_rows = conn.execute(
                    "SELECT DISTINCT matched_feature FROM exchanges"
                    " WHERE session_id = ? AND matched_feature IS NOT NULL",
                    (sid,),
                ).fetchall()

                # Had error
                err_count = conn.execute(
                    "SELECT COUNT(*) FROM exchanges"
                    " WHERE session_id = ? AND error IS NOT NULL",
                    (sid,),
                ).fetchone()[0]

                sessions.append({
                    "id": sid,
                    "started_at": r["started_at"],
                    "ended_at": r["ended_at"],
                    "duration_ms": duration_ms,
                    "exchange_count": r["exchange_count"],
                    "wake_model": r["wake_model"],
                    "first_transcription": first["transcription"] if first else None,
                    "features_used": [fr["matched_feature"] for fr in feat_rows],
                    "had_error": err_count > 0,
                })

            self._send_json({
                "sessions": sessions,
                "total": total,
                "limit": limit,
                "offset": offset,
            })
        finally:
            conn.close()

    def _handle_session_detail(self, session_id):
        db = self.server.db_path
        conn = _ro_connect(db)
        try:
            session_row = conn.execute(
                "SELECT id, started_at, ended_at, exchange_count, wake_model"
                " FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()

            if not session_row:
                self._send_json({"error": "Session not found"}, HTTPStatus.NOT_FOUND)
                return

            exchange_rows = conn.execute(
                "SELECT * FROM exchanges WHERE session_id = ? ORDER BY sequence",
                (session_id,),
            ).fetchall()

            exchanges = []
            for ex in exchange_rows:
                ex_dict = dict(ex)
                ex_id = ex_dict["id"]

                # Boolean conversions
                ex_dict["used_vad"] = bool(ex_dict.get("used_vad"))
                ex_dict["had_bargein"] = bool(ex_dict.get("had_bargein"))
                ex_dict["is_follow_up"] = bool(ex_dict.get("is_follow_up"))

                # LLM calls
                llm_rows = conn.execute(
                    "SELECT * FROM llm_calls WHERE exchange_id = ? ORDER BY id",
                    (ex_id,),
                ).fetchall()
                ex_dict["llm_calls"] = [dict(lr) for lr in llm_rows]

                exchanges.append(ex_dict)

            self._send_json({
                "session": dict(session_row),
                "exchanges": exchanges,
            })
        finally:
            conn.close()

    def _handle_tts_cache_list(self):
        cache_dir = getattr(self.server, "tts_cache_dir", None)
        if not cache_dir:
            self._send_json({"entries": [], "total_entries": 0, "total_size_bytes": 0})
            return

        cache_path = Path(cache_dir)
        if not cache_path.is_dir():
            self._send_json({"entries": [], "total_entries": 0, "total_size_bytes": 0})
            return

        entries = []
        seen_hashes = set()
        total_size = 0

        # Read sidecars
        for meta_file in cache_path.glob("*.json"):
            h = meta_file.stem
            seen_hashes.add(h)
            try:
                data = json.loads(meta_file.read_text(encoding="utf-8"))
                size = data.get("size_bytes", 0)
                total_size += size
                entries.append({
                    "hash": h,
                    "text": data.get("text", "(unknown)"),
                    "voice": data.get("voice", ""),
                    "model": data.get("model", ""),
                    "created_at": data.get("created_at", ""),
                    "hit_count": data.get("hit_count", 0),
                    "size_bytes": size,
                })
            except (json.JSONDecodeError, OSError):
                continue

        # Detect orphaned .pcm files (no sidecar)
        for pcm_file in cache_path.glob("*.pcm"):
            h = pcm_file.stem
            if h not in seen_hashes:
                size = pcm_file.stat().st_size
                total_size += size
                entries.append({
                    "hash": h,
                    "text": "(unknown)",
                    "voice": "",
                    "model": "",
                    "created_at": "",
                    "hit_count": 0,
                    "size_bytes": size,
                })

        entries.sort(key=lambda e: e.get("created_at", ""), reverse=True)
        self._send_json({
            "entries": entries,
            "total_entries": len(entries),
            "total_size_bytes": total_size,
        })

    def _handle_tts_cache_audio(self, hash_id: str):
        cache_dir = getattr(self.server, "tts_cache_dir", None)
        if not cache_dir:
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return

        pcm_path = Path(cache_dir) / f"{hash_id}.pcm"
        if not pcm_path.is_file():
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return

        try:
            pcm = pcm_path.read_bytes()
            wav = _pcm_to_wav(pcm)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(wav)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(wav)
        except Exception:
            self._send_json(
                {"error": "Failed to read audio"}, HTTPStatus.INTERNAL_SERVER_ERROR
            )

    def _handle_logs(self, params):
        log_dir = getattr(self.server, "log_dir", None)
        if not log_dir:
            # Return 200 with a soft "unavailable" payload so the SPA
            # can render a friendly empty state rather than confusing
            # the caller with a routing-style 404.
            self._send_json({
                "lines": [], "total_lines": 0,
                "log_file": "homehud.log", "filters": {},
                "message": "Log directory not configured on this server.",
            })
            return

        log_path = Path(log_dir) / "homehud.log"
        if not log_path.is_file():
            self._send_json({
                "lines": [], "total_lines": 0,
                "log_file": "homehud.log", "filters": {},
                "message": f"Log file {log_path} does not exist yet.",
            })
            return

        limit = min(int(params.get("lines", [200])[0]), 2000)
        level_filter = params.get("level", [None])[0]

        raw_lines = _tail_log(log_path, max_lines=limit * 3)  # over-read for filtering
        entries = _parse_log_lines(raw_lines, level_filter, limit)

        self._send_json({
            "lines": entries,
            "total_lines": len(entries),
            "log_file": "homehud.log",
            "filters": {"level": level_filter, "limit": limit},
        })

    # --- Garden handler ---

    def _handle_garden(self):
        """Return garden watering balance breakdown."""
        garden = getattr(self.server, "garden_feature", None)
        if not garden:
            self._send_json({"enabled": False, "zones": []})
            return

        weather_client = getattr(self.server, "weather_client", None)
        weather = weather_client.get_weather() if weather_client else None

        zones = []
        try:
            statuses = garden.get_status()
            for s in statuses:
                zones.append({
                    "zone": s.zone,
                    "label": s.label,
                    "deficit_inches": s.deficit_inches,
                    "threshold_inches": s.threshold_inches,
                    "urgency": s.urgency,
                    "forecast_rain_inches": s.forecast_rain_inches,
                    "days_since_rain": s.days_since_rain,
                    "days_since_watered": s.days_since_watered,
                    "pct_of_threshold": round(
                        s.deficit_inches / s.threshold_inches * 100, 1,
                    ) if s.threshold_inches else 0,
                })
        except Exception:
            log.exception("Garden status fetch failed")

        # Include weather history for the balance breakdown
        history = []
        if weather and weather.history:
            for d in weather.history:
                history.append({
                    "date": d.date.isoformat(),
                    "precipitation_mm": round(d.precipitation_mm, 1),
                    "et0_mm": round(d.et0_mm, 1),
                    "temp_max_f": round(d.temp_max_f, 1),
                    "weather_code": d.weather_code,
                })

        forecast = []
        if weather and weather.forecast:
            for d in weather.forecast:
                forecast.append({
                    "date": d.date.isoformat(),
                    "precipitation_mm": round(d.precipitation_mm, 1),
                    "precipitation_probability": d.precipitation_probability,
                    "et0_mm": round(d.et0_mm, 1),
                    "temp_max_f": round(d.temp_max_f, 1),
                    "weather_code": d.weather_code,
                })

        # Watering log
        watering_events = []
        try:
            events = garden._watering_log.get_events(days=14)
            for e in events:
                watering_events.append({
                    "zone": e.get("zone", "unknown"),
                    "timestamp": e.get("timestamp", ""),
                    "amount_inches": e.get("amount_inches", 0),
                })
        except Exception:
            pass

        self._send_json({
            "enabled": True,
            "zones": zones,
            "history": history,
            "forecast": forecast,
            "watering_events": watering_events,
        })

    # --- Monitor handlers ---

    def _get_monitor_storage(self):
        """Get the MonitorStorage instance, or None."""
        return getattr(self.server, "monitor_storage", None)

    def _handle_monitor_list(self):
        storage = self._get_monitor_storage()
        if not storage:
            self._send_json({"services": [], "monitoring_enabled": False})
            return

        services = storage.get_latest_results()
        enriched = []
        for svc in services:
            summary = storage.get_uptime_summary(svc["id"], days=30)
            enriched.append({**svc, **summary})
        self._send_json({"services": enriched, "monitoring_enabled": True})

    def _handle_monitor_detail(self, service_id: int):
        storage = self._get_monitor_storage()
        if not storage:
            self._send_json({"error": "Monitoring not enabled"}, HTTPStatus.NOT_FOUND)
            return

        svc = storage.get_service(service_id)
        if not svc:
            self._send_json({"error": "Service not found"}, HTTPStatus.NOT_FOUND)
            return

        summary = storage.get_uptime_summary(service_id, days=30)
        self._send_json({**svc, **summary})

    def _handle_monitor_history(self, service_id: int, params: dict):
        storage = self._get_monitor_storage()
        if not storage:
            self._send_json({"error": "Monitoring not enabled"}, HTTPStatus.NOT_FOUND)
            return

        days = min(int(params.get("days", [30])[0]), 90)
        history = storage.get_service_history(service_id, days=days)
        self._send_json({"service_id": service_id, "days": days, "checks": history})

    def _handle_monitor_add(self):
        storage = self._get_monitor_storage()
        if not storage:
            self._send_json(
                {"error": "Monitoring not enabled"}, HTTPStatus.BAD_REQUEST
            )
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            self._send_json({"error": "Invalid JSON"}, HTTPStatus.BAD_REQUEST)
            return

        name = body.get("name", "").strip()
        url = body.get("url", "").strip()
        check_type = body.get("check_type", "http").strip()

        if not name or not url:
            self._send_json(
                {"error": "name and url are required"}, HTTPStatus.BAD_REQUEST
            )
            return
        if check_type not in ("http", "ping"):
            self._send_json(
                {"error": "check_type must be 'http' or 'ping'"}, HTTPStatus.BAD_REQUEST
            )
            return

        try:
            service_id = storage.add_service(name, url, check_type)
        except Exception as exc:
            self._send_json(
                {"error": str(exc)}, HTTPStatus.BAD_REQUEST
            )
            return

        self._send_json({"id": service_id, "name": name, "url": url})

    def _handle_monitor_remove(self, service_id: int):
        storage = self._get_monitor_storage()
        if not storage:
            self._send_json(
                {"error": "Monitoring not enabled"}, HTTPStatus.BAD_REQUEST
            )
            return

        if storage.remove_service(service_id):
            self._send_json({"deleted": True, "id": service_id})
        else:
            self._send_json({"error": "Service not found"}, HTTPStatus.NOT_FOUND)

    def _handle_monitor_update(self, service_id: int):
        storage = self._get_monitor_storage()
        if not storage:
            self._send_json(
                {"error": "Monitoring not enabled"}, HTTPStatus.BAD_REQUEST
            )
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            self._send_json(
                {"error": "Invalid JSON"}, HTTPStatus.BAD_REQUEST
            )
            return

        updated = False
        if "enabled" in body:
            updated = storage.toggle_service(
                service_id, bool(body["enabled"])
            )
        name = body.get("name", "").strip() or None
        url = body.get("url", "").strip() or None
        check_type = body.get("check_type", "").strip() or None
        if name or url or check_type:
            try:
                updated = storage.update_service(
                    service_id, name=name, url=url,
                    check_type=check_type,
                ) or updated
            except Exception as exc:
                self._send_json(
                    {"error": str(exc)}, HTTPStatus.BAD_REQUEST
                )
                return

        if updated:
            self._send_json({"id": service_id, "updated": True})
        else:
            self._send_json(
                {"error": "Service not found"}, HTTPStatus.NOT_FOUND
            )

    def _handle_monitor_test(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            self._send_json(
                {"error": "Invalid JSON"}, HTTPStatus.BAD_REQUEST
            )
            return

        url = body.get("url", "").strip()
        check_type = body.get("check_type", "http").strip()
        if not url:
            self._send_json(
                {"error": "url is required"}, HTTPStatus.BAD_REQUEST
            )
            return

        from monitor.checker import check_http, check_ping

        timeout = 10
        config = getattr(self.server, "config", None)
        if config:
            timeout = config.get("monitor_check_timeout", 10)

        if check_type == "ping":
            is_up, ms, code, error = check_ping(url, timeout)
        else:
            is_up, ms, code, error = check_http(url, timeout)

        self._send_json({
            "is_up": is_up,
            "response_time_ms": ms,
            "status_code": code,
            "error": error,
        })

    # --- Response helpers ---

    def _send_json(self, data, status=HTTPStatus.OK):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # --- SPA (SvelteKit dist) serving ---

    def _runtime_config_dict(self) -> dict:
        """Return the runtime config snapshot injected into the SPA shell.

        Kept small — the SPA fetches anything variable over the API.
        """
        config = getattr(self.server, "config", None) or {}
        try:
            ttl_s = int(config.get("llm_history_ttl", 300))
        except (TypeError, ValueError):
            ttl_s = 300
        return {
            "voiceThreadTtlMs": ttl_s * 1000,
            "pwaName": config.get("pwa_name", "Home HUD"),
            "pwaThemeColor": config.get("pwa_theme_color", "#F39060"),
            "authEnabled": bool(config.get("web_auth_enabled", False)),
            "serverTime": int(time.time()),
        }

    def _inject_runtime_config(self, index_bytes: bytes) -> bytes:
        """Fill the ``<script id="hud-config">{}</script>`` placeholder."""
        cfg_json = json.dumps(self._runtime_config_dict()).encode()
        placeholder = (
            b'<script id="hud-config" type="application/json">{}</script>'
        )
        replacement = (
            b'<script id="hud-config" type="application/json">'
            + cfg_json
            + b"</script>"
        )
        return index_bytes.replace(placeholder, replacement, 1)

    def _serve_static(self, url_path: str) -> None:
        """Serve SPA assets (bundle, manifest, icons) or the SPA shell.

        Unknown non-API paths fall back to index.html so the SvelteKit
        client router can handle them.
        """
        assets = getattr(self.server, "static_assets", None)
        if assets is None or not assets.available:
            self._send_json(
                {"error": "SPA build not available — run `make web-build`"},
                HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return
        file_path, index_bytes, is_hashed = assets.resolve(url_path)
        if index_bytes is not None:
            body = self._inject_runtime_config(index_bytes)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Permissions-Policy", "microphone=(self)")
            self.end_headers()
            self.wfile.write(body)
            return
        if file_path is None:
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        body = file_path.read_bytes()
        mime = _STATIC_MIME.get(
            file_path.suffix.lower(), "application/octet-stream",
        )
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        if is_hashed:
            self.send_header(
                "Cache-Control", "public, max-age=31536000, immutable",
            )
        else:
            self.send_header("Cache-Control", "no-cache")
        if file_path.name == "audio-processor.js":
            self.send_header("Permissions-Policy", "microphone=(self)")
        self.end_headers()
        self.wfile.write(body)


    # --- Recipe API handlers ---

    def _handle_recipes_list(self):
        """GET /api/recipes — list all recipes."""
        storage = getattr(self.server, "recipe_storage", None)
        if storage is None:
            self._send_json({"error": "Recipe storage not available"},
                            HTTPStatus.SERVICE_UNAVAILABLE)
            return
        self._send_json(storage.get_all())

    def _handle_recipe_detail(self, recipe_id: str):
        """GET /api/recipes/<id> — single recipe detail."""
        storage = getattr(self.server, "recipe_storage", None)
        if storage is None:
            self._send_json({"error": "Recipe storage not available"},
                            HTTPStatus.SERVICE_UNAVAILABLE)
            return
        recipe = storage.get_by_id(recipe_id)
        if recipe is None:
            self._send_json({"error": "Recipe not found"}, HTTPStatus.NOT_FOUND)
            return
        self._send_json(recipe)

    def _handle_recipe_create(self):
        """POST /api/recipes — create a recipe from JSON body."""
        storage = getattr(self.server, "recipe_storage", None)
        if storage is None:
            self._send_json({"error": "Recipe storage not available"},
                            HTTPStatus.SERVICE_UNAVAILABLE)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            self._send_json({"error": "Invalid JSON"}, HTTPStatus.BAD_REQUEST)
            return
        name = body.get("name", "").strip()
        if not name:
            self._send_json({"error": "Recipe name is required"},
                            HTTPStatus.BAD_REQUEST)
            return
        if "source" not in body:
            body["source"] = "manual"
        recipe_id = storage.add(body)
        self._send_json({"id": recipe_id, "recipe": storage.get_by_id(recipe_id)})

    def _handle_recipe_upload_image(self):
        """POST /api/recipes/upload-image — parse recipe from a photo."""
        storage = getattr(self.server, "recipe_storage", None)
        llm = getattr(self.server, "llm", None)
        if storage is None or llm is None:
            self._send_json(
                {"error": "Recipe storage or LLM not available"},
                HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 10_485_760:  # 10 MB limit
                self._send_json({"error": "Image too large (max 10MB)"},
                                HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                return
            body = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            self._send_json({"error": "Invalid JSON"}, HTTPStatus.BAD_REQUEST)
            return
        image_b64 = body.get("image", "")
        if not image_b64:
            self._send_json({"error": "No image data provided"},
                            HTTPStatus.BAD_REQUEST)
            return
        media_type = body.get("media_type", "image/jpeg")
        recipe_data = llm.parse_recipe_image(image_b64, media_type)
        if recipe_data is None:
            self._send_json(
                {"error": "Failed to parse recipe from image"},
                HTTPStatus.UNPROCESSABLE_ENTITY,
            )
            return
        # Return parsed data for user review (not saved yet)
        self._send_json({"recipe": recipe_data, "saved": False})

    def _handle_recipe_update(self, recipe_id: str):
        """PATCH /api/recipes/<id> — update recipe fields."""
        storage = getattr(self.server, "recipe_storage", None)
        if storage is None:
            self._send_json({"error": "Recipe storage not available"},
                            HTTPStatus.SERVICE_UNAVAILABLE)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            self._send_json({"error": "Invalid JSON"}, HTTPStatus.BAD_REQUEST)
            return
        if not storage.update(recipe_id, body):
            self._send_json({"error": "Recipe not found"}, HTTPStatus.NOT_FOUND)
            return
        self._send_json({"ok": True, "recipe": storage.get_by_id(recipe_id)})

    def _handle_recipe_delete(self, recipe_id: str):
        """DELETE /api/recipes/<id> — remove a recipe."""
        storage = getattr(self.server, "recipe_storage", None)
        if storage is None:
            self._send_json({"error": "Recipe storage not available"},
                            HTTPStatus.SERVICE_UNAVAILABLE)
            return
        if not storage.delete(recipe_id):
            self._send_json({"error": "Recipe not found"}, HTTPStatus.NOT_FOUND)
            return
        self._send_json({"ok": True})

    # --- Grocery API handlers ---

    def _grocery_feature(self):
        grocery = getattr(self.server, "grocery_feature", None)
        if grocery is None:
            self._send_json({"error": "Grocery feature not available"},
                            HTTPStatus.SERVICE_UNAVAILABLE)
        return grocery

    def _read_json_body(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length <= 0:
                return {}
            return json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            self._send_json({"error": "Invalid JSON"}, HTTPStatus.BAD_REQUEST)
            return None

    def _categorize_pending(self, grocery) -> None:
        """Fill in categories for uncategorized items, using cache + LLM."""
        pending = grocery.uncategorized_names()
        if not pending:
            return

        cache = getattr(self.server, "grocery_category_cache", None)
        llm = getattr(self.server, "llm", None)

        cached: dict[str, str] = {}
        misses = pending
        if cache is not None:
            cached, misses = cache.lookup_many(pending)

        fresh: dict[str, str] = {}
        if misses and llm is not None and hasattr(llm, "categorize_grocery_items"):
            from features.grocery import DEFAULT_CATEGORIES
            try:
                fresh = llm.categorize_grocery_items(misses, DEFAULT_CATEGORIES)
            except Exception:
                log.exception("Grocery LLM categorization failed")
                fresh = {}
            if fresh and cache is not None:
                cache.put_many(fresh)

        merged = {**cached, **fresh}
        if merged:
            grocery.apply_categories(merged)

    def _handle_grocery_get(self):
        """GET /api/grocery — full list state, categorizing as needed."""
        grocery = self._grocery_feature()
        if grocery is None:
            return
        try:
            self._categorize_pending(grocery)
            self._send_json(grocery.get_state())
        except Exception:
            log.exception("Grocery get failed")
            self._send_json({"error": "Internal error"},
                            HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_grocery_add(self):
        """POST /api/grocery — add a new item."""
        grocery = self._grocery_feature()
        if grocery is None:
            return
        body = self._read_json_body()
        if body is None:
            return
        name = (body.get("name") or "").strip()
        if not name:
            self._send_json({"error": "Name required"}, HTTPStatus.BAD_REQUEST)
            return

        quantity = body.get("quantity")
        unit = body.get("unit")

        # Try the cache first for instant categorization
        category = None
        cache = getattr(self.server, "grocery_category_cache", None)
        if cache is not None:
            category = cache.get(name)

        item = grocery.add_item(name, category, quantity=quantity, unit=unit)
        if item is None:
            self._send_json({"error": "Item already on list"},
                            HTTPStatus.CONFLICT)
            return
        self._send_json({"ok": True, "item": item})

    def _handle_grocery_update(self, item_id: str):
        """PATCH /api/grocery/<id> — update item fields."""
        grocery = self._grocery_feature()
        if grocery is None:
            return
        body = self._read_json_body()
        if body is None:
            return
        item = grocery.update_item(item_id, body)
        if item is None:
            self._send_json({"error": "Item not found"}, HTTPStatus.NOT_FOUND)
            return
        self._send_json({"ok": True, "item": item})

    def _handle_grocery_delete(self, item_id: str):
        grocery = self._grocery_feature()
        if grocery is None:
            return
        if not grocery.delete_item(item_id):
            self._send_json({"error": "Item not found"}, HTTPStatus.NOT_FOUND)
            return
        self._send_json({"ok": True})

    def _handle_grocery_reorder(self):
        grocery = self._grocery_feature()
        if grocery is None:
            return
        body = self._read_json_body()
        if body is None:
            return
        ids = body.get("ids")
        if not isinstance(ids, list):
            self._send_json({"error": "ids must be a list"},
                            HTTPStatus.BAD_REQUEST)
            return
        grocery.reorder_items([str(i) for i in ids])
        self._send_json({"ok": True})

    def _handle_grocery_category_order(self):
        grocery = self._grocery_feature()
        if grocery is None:
            return
        body = self._read_json_body()
        if body is None:
            return
        order = body.get("order")
        if not isinstance(order, list):
            self._send_json({"error": "order must be a list"},
                            HTTPStatus.BAD_REQUEST)
            return
        new_order = grocery.set_category_order([str(c) for c in order])
        self._send_json({"ok": True, "category_order": new_order})

    def _handle_grocery_clear_checked(self):
        grocery = self._grocery_feature()
        if grocery is None:
            return
        removed = grocery.clear_checked()
        self._send_json({"ok": True, "removed": removed})


def _pcm_to_wav(pcm: bytes, sample_rate: int = 16000, channels: int = 1, bits: int = 16) -> bytes:
    """Prepend a 44-byte WAV header to raw PCM data (int16 LE)."""
    data_size = len(pcm)
    byte_rate = sample_rate * channels * bits // 8
    block_align = channels * bits // 8
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,           # chunk size
        1,            # PCM format
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits,
        b"data",
        data_size,
    )
    return header + pcm


def _ro_connect(db_path: str) -> sqlite3.Connection:
    """Open a read-only SQLite connection."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def _tail_log(path: Path, max_lines: int = 600) -> list[str]:
    """Read the last `max_lines` lines from a log file efficiently."""
    chunk_size = 8192
    lines: list[str] = []
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)  # end of file
            remaining = f.tell()
            buf = b""
            while remaining > 0 and len(lines) < max_lines:
                read_size = min(chunk_size, remaining)
                remaining -= read_size
                f.seek(remaining)
                buf = f.read(read_size) + buf
                lines = buf.decode("utf-8", errors="replace").splitlines()
            return lines[-max_lines:]
    except Exception:
        return []


def _parse_log_lines(
    raw_lines: list[str], level_filter: str | None, limit: int,
) -> list[dict]:
    """Parse raw log lines into structured entries, attaching continuations."""
    min_level = 0
    if level_filter and level_filter.upper() in _LEVEL_ORDER:
        min_level = _LEVEL_ORDER[level_filter.upper()]

    entries: list[dict] = []
    for line in raw_lines:
        m = _LOG_LINE_RE.match(line)
        if m:
            level = m.group(2).upper()
            if _LEVEL_ORDER.get(level, 0) >= min_level:
                entries.append({
                    "timestamp": m.group(1),
                    "level": level,
                    "logger": m.group(3),
                    "message": m.group(4),
                })
        elif entries:
            # Continuation line (traceback, multi-line message)
            entries[-1]["message"] += "\n" + line

    return entries[-limit:]


class TelemetryWeb:
    """Lightweight HTTP server for the telemetry dashboard.

    Runs in a daemon thread, serves the dashboard HTML and JSON API endpoints.
    Opens its own read-only SQLite connection — independent from the pipeline's writes.
    """

    def __init__(
        self,
        db_path: str,
        host: str = "0.0.0.0",
        port: int = 8080,
        display_snapshot_path: str | None = None,
        log_dir: str | None = None,
        config: dict | None = None,
        tts_cache_dir: str | None = None,
        monitor_storage: object | None = None,
        garden_feature: object | None = None,
        weather_client: object | None = None,
        voice_handler: object | None = None,
        auth_manager: object | None = None,
        tls_cert: str | None = None,
        tls_key: str | None = None,
        recipe_storage: object | None = None,
        llm: object | None = None,
        grocery_feature: object | None = None,
        grocery_category_cache: object | None = None,
    ):
        self._db_path = db_path
        self._host = host
        self._port = port
        self._display_snapshot_path = display_snapshot_path
        self._log_dir = log_dir
        self._config = config
        self._tts_cache_dir = tts_cache_dir
        self._monitor_storage = monitor_storage
        self._garden_feature = garden_feature
        self._weather_client = weather_client
        self._voice_handler = voice_handler
        self._auth_manager = auth_manager
        self._tls_cert = tls_cert
        self._tls_key = tls_key
        self._recipe_storage = recipe_storage
        self._llm = llm
        self._grocery_feature = grocery_feature
        self._grocery_category_cache = grocery_category_cache
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def set_voice_handler(self, handler: object) -> None:
        """Attach a voice handler after construction (for late binding)."""
        self._voice_handler = handler
        if self._server is not None:
            self._server.voice_handler = handler

    def start(self) -> threading.Thread:
        """Start the web server in a daemon thread."""
        self._setup_server()
        self._shutting_down = False
        self._thread = threading.Thread(target=self._serve_loop, daemon=True)
        self._thread.start()
        log.info("Telemetry dashboard at http://%s:%d", self._host, self._port)
        return self._thread

    def _setup_server(self) -> None:
        """Create and configure the HTTP server instance."""
        self._server = ThreadingHTTPServer((self._host, self._port), _Handler)
        self._server.daemon_threads = True
        self._server.db_path = self._db_path
        self._server.display_snapshot_path = self._display_snapshot_path
        self._server.log_dir = self._log_dir
        self._server.config = self._config
        self._server.tts_cache_dir = self._tts_cache_dir
        self._server.monitor_storage = self._monitor_storage
        self._server.garden_feature = self._garden_feature
        self._server.weather_client = self._weather_client
        self._server.voice_handler = self._voice_handler
        self._server.auth_manager = self._auth_manager
        self._server.recipe_storage = self._recipe_storage
        self._server.llm = self._llm
        self._server.grocery_feature = self._grocery_feature
        self._server.grocery_category_cache = self._grocery_category_cache

        # SPA (SvelteKit static build). Looks up web/dist relative to
        # the repo root. Missing dist is logged but non-fatal — the old
        # Python-strings dashboard keeps working.
        repo_root = Path(__file__).resolve().parent.parent.parent
        self._server.static_assets = StaticAssets(repo_root / "web" / "dist")

        # Optional TLS
        if self._tls_cert and self._tls_key:
            import ssl

            cert_path = Path(self._tls_cert)
            key_path = Path(self._tls_key)
            if cert_path.exists() and key_path.exists():
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ctx.load_cert_chain(str(cert_path), str(key_path))
                self._server.socket = ctx.wrap_socket(
                    self._server.socket, server_side=True,
                )
                log.info("TLS enabled with cert %s", cert_path)
            else:
                log.warning(
                    "TLS cert/key not found (%s / %s) — running HTTP",
                    cert_path, key_path,
                )

    def _serve_loop(self) -> None:
        """Run serve_forever with auto-restart on crash."""
        while not self._shutting_down:
            try:
                self._server.serve_forever()
            except Exception:
                if self._shutting_down:
                    return
                log.exception("Telemetry web server crashed — restarting in 5s")
                try:
                    self._server.server_close()
                except Exception:
                    pass
                time.sleep(5)
                try:
                    self._setup_server()
                except Exception:
                    log.exception("Telemetry web server failed to rebind — giving up")
                    return

    @property
    def is_alive(self) -> bool:
        """Return True if the server thread is still running."""
        return self._thread is not None and self._thread.is_alive()

    def check_health(self, timeout: float = 5) -> bool:
        """Actively probe /api/health to verify the server is responsive."""
        import urllib.request

        try:
            if self._tls_cert and self._tls_key:
                import ssl

                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                url = f"https://127.0.0.1:{self._port}/api/health"
                with urllib.request.urlopen(url, timeout=timeout, context=ctx) as resp:
                    return resp.status == 200
            else:
                url = f"http://127.0.0.1:{self._port}/api/health"
                with urllib.request.urlopen(url, timeout=timeout) as resp:
                    return resp.status == 200
        except Exception:
            return False

    def close(self) -> None:
        """Shut down the server."""
        self._shutting_down = True
        if self._server:
            self._server.shutdown()
            if self._thread:
                self._thread.join(timeout=5)
            self._server.server_close()
            log.info("Telemetry web server stopped")
