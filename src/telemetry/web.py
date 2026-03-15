"""Lightweight web server for the telemetry dashboard."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import struct
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from telemetry.dashboard import DASHBOARD_HTML

log = logging.getLogger("home-hud.telemetry.web")

# Regex for /api/sessions/<uuid>
_SESSION_RE = re.compile(r"^/api/sessions/([0-9a-f-]+)$")
# Regex for /api/tts-cache/<hash>/audio
_TTS_CACHE_RE = re.compile(r"^/api/tts-cache/([0-9a-f]{64})/audio$")

# Log line parsing: matches "2024-01-15 10:30:45,123 [INFO] home-hud: message"
_LOG_LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})"  # timestamp
    r" \[(\w+)\]"  # level
    r" ([\w.\-]+):"  # logger name
    r" (.*)$"  # message
)
_LEVEL_ORDER = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}


_SENSITIVE_KEYS = frozenset({
    "anthropic_api_key",
    "elevenlabs_api_key",
    "enphase_token",
    "enphase_password",
    "enphase_email",
    "sonarr_api_key",
    "radarr_api_key",
    "jellyfin_api_key",
})


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
        elif path == "/api/config":
            self._handle_config()
        elif path == "/api/display":
            self._handle_display()
        elif path == "/api/logs":
            self._handle_logs(params)
        elif path == "/api/sessions":
            self._handle_sessions(params)
        elif path == "/api/tts-cache":
            self._handle_tts_cache_list()
        elif m := _TTS_CACHE_RE.match(path):
            self._handle_tts_cache_audio(m.group(1))
        elif m := _SESSION_RE.match(path):
            self._handle_session_detail(m.group(1))
        else:
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    # --- API handlers ---

    def _handle_config(self):
        config = getattr(self.server, "config", None)
        if config is None:
            self._send_json({"error": "Config not available"})
            return
        filtered = {k: v for k, v in config.items() if k not in _SENSITIVE_KEYS}
        self._send_json(filtered)

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
            self._send_json({"error": "Log directory not configured"}, HTTPStatus.NOT_FOUND)
            return

        log_path = Path(log_dir) / "homehud.log"
        if not log_path.is_file():
            self._send_json({
                "lines": [], "total_lines": 0,
                "log_file": "homehud.log", "filters": {},
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
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
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
    ):
        self._db_path = db_path
        self._host = host
        self._port = port
        self._display_snapshot_path = display_snapshot_path
        self._log_dir = log_dir
        self._config = config
        self._tts_cache_dir = tts_cache_dir
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> threading.Thread:
        """Start the web server in a daemon thread."""
        self._server = HTTPServer((self._host, self._port), _Handler)
        self._server.db_path = self._db_path  # attach for handler access
        self._server.display_snapshot_path = self._display_snapshot_path
        self._server.log_dir = self._log_dir
        self._server.config = self._config
        self._server.tts_cache_dir = self._tts_cache_dir
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
