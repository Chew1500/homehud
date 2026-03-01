"""Lightweight web server for the telemetry dashboard."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from telemetry.dashboard import DASHBOARD_HTML

log = logging.getLogger("home-hud.telemetry.web")

# Regex for /api/sessions/<uuid>
_SESSION_RE = re.compile(r"^/api/sessions/([0-9a-f-]+)$")


class _Handler(BaseHTTPRequestHandler):
    """Request handler — routes to dashboard or JSON API endpoints."""

    def log_message(self, format, *args):  # noqa: A002
        log.debug(format, *args)

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        params = parse_qs(parsed.query)

        if path == "/":
            self._send_html(DASHBOARD_HTML)
        elif path == "/api/stats":
            self._handle_stats()
        elif path == "/api/sessions":
            self._handle_sessions(params)
        elif m := _SESSION_RE.match(path):
            self._handle_session_detail(m.group(1))
        else:
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    # --- API handlers ---

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
                "  (SELECT AVG(recording_duration_ms) FROM exchanges"
                "    WHERE recording_duration_ms IS NOT NULL) AS avg_recording_ms,"
                "  (SELECT AVG(stt_duration_ms) FROM exchanges"
                "    WHERE stt_duration_ms IS NOT NULL) AS avg_stt_ms,"
                "  (SELECT AVG(routing_duration_ms) FROM exchanges"
                "    WHERE routing_duration_ms IS NOT NULL) AS avg_routing_ms,"
                "  (SELECT AVG(tts_duration_ms) FROM exchanges"
                "    WHERE tts_duration_ms IS NOT NULL) AS avg_tts_ms,"
                "  (SELECT AVG(playback_duration_ms) FROM exchanges"
                "    WHERE playback_duration_ms IS NOT NULL) AS avg_playback_ms"
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

    # --- Response helpers ---

    def _send_json(self, data, status=HTTPStatus.OK):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html):
        body = html.encode()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _ro_connect(db_path: str) -> sqlite3.Connection:
    """Open a read-only SQLite connection."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


class TelemetryWeb:
    """Lightweight HTTP server for the telemetry dashboard.

    Runs in a daemon thread, serves the dashboard HTML and JSON API endpoints.
    Opens its own read-only SQLite connection — independent from the pipeline's writes.
    """

    def __init__(self, db_path: str, host: str = "0.0.0.0", port: int = 8080):
        self._db_path = db_path
        self._host = host
        self._port = port
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> threading.Thread:
        """Start the web server in a daemon thread."""
        self._server = HTTPServer((self._host, self._port), _Handler)
        self._server.db_path = self._db_path  # attach for handler access
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        log.info("Telemetry dashboard at http://%s:%d", self._host, self._port)
        return self._thread

    def close(self) -> None:
        """Shut down the server."""
        if self._server:
            self._server.shutdown()
            if self._thread:
                self._thread.join(timeout=5)
            self._server.server_close()
            log.info("Telemetry web server stopped")
