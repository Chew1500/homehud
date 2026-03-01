"""SQLite storage for voice transaction telemetry."""

from __future__ import annotations

import logging
import os
import sqlite3
import threading

from telemetry.models import Exchange, LLMCallInfo, Session

log = logging.getLogger("home-hud.telemetry")

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    exchange_count INTEGER DEFAULT 0,
    wake_model TEXT
);

CREATE TABLE IF NOT EXISTS exchanges (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    sequence INTEGER NOT NULL,

    recording_started_at TEXT, recording_ended_at TEXT, recording_duration_ms INTEGER,
    stt_started_at TEXT, stt_ended_at TEXT, stt_duration_ms INTEGER,
    routing_started_at TEXT, routing_ended_at TEXT, routing_duration_ms INTEGER,
    tts_started_at TEXT, tts_ended_at TEXT, tts_duration_ms INTEGER,
    playback_started_at TEXT, playback_ended_at TEXT, playback_duration_ms INTEGER,

    transcription TEXT,

    routing_path TEXT,
    matched_feature TEXT,
    feature_action TEXT,
    response_text TEXT,

    used_vad INTEGER DEFAULT 0,
    had_bargein INTEGER DEFAULT 0,
    is_follow_up INTEGER DEFAULT 0,
    error TEXT,

    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS llm_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange_id TEXT NOT NULL REFERENCES exchanges(id),
    call_type TEXT NOT NULL,
    started_at TEXT,
    ended_at TEXT,
    duration_ms INTEGER,
    model TEXT,
    system_prompt TEXT,
    user_message TEXT,
    response_text TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    stop_reason TEXT,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_exchanges_session ON exchanges(session_id);
CREATE INDEX IF NOT EXISTS idx_exchanges_created ON exchanges(created_at);
CREATE INDEX IF NOT EXISTS idx_llm_calls_exchange ON llm_calls(exchange_id);
"""


class TelemetryStore:
    """Thread-safe SQLite storage for voice transaction telemetry."""

    def __init__(self, db_path: str, max_size_mb: int = 10240):
        self._db_path = db_path
        self._max_size_bytes = max_size_mb * 1024 * 1024
        self._lock = threading.Lock()

        # Ensure parent directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def save_session(self, session: Session) -> None:
        """Persist a complete session with all exchanges and LLM calls."""
        with self._lock:
            self._conn.execute(
                "INSERT INTO sessions (id, started_at, ended_at, exchange_count, wake_model) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    session.id,
                    session.started_at,
                    session.ended_at,
                    session.exchange_count,
                    session.wake_model,
                ),
            )

            for exchange in session.exchanges:
                self._save_exchange(exchange)

            self._conn.commit()

        self._maybe_prune()

    def _save_exchange(self, exchange: Exchange) -> None:
        """Insert an exchange and its LLM calls (must be called within lock)."""
        self._conn.execute(
            "INSERT INTO exchanges ("
            "  id, session_id, sequence,"
            "  recording_started_at, recording_ended_at, recording_duration_ms,"
            "  stt_started_at, stt_ended_at, stt_duration_ms,"
            "  routing_started_at, routing_ended_at, routing_duration_ms,"
            "  tts_started_at, tts_ended_at, tts_duration_ms,"
            "  playback_started_at, playback_ended_at, playback_duration_ms,"
            "  transcription, routing_path, matched_feature, feature_action,"
            "  response_text, used_vad, had_bargein, is_follow_up, error"
            ") VALUES ("
            "  ?, ?, ?,"
            "  ?, ?, ?,"
            "  ?, ?, ?,"
            "  ?, ?, ?,"
            "  ?, ?, ?,"
            "  ?, ?, ?,"
            "  ?, ?, ?, ?,"
            "  ?, ?, ?, ?, ?"
            ")",
            (
                exchange.id,
                exchange.session_id,
                exchange.sequence,
                exchange.recording_started_at,
                exchange.recording_ended_at,
                exchange.recording_duration_ms,
                exchange.stt_started_at,
                exchange.stt_ended_at,
                exchange.stt_duration_ms,
                exchange.routing_started_at,
                exchange.routing_ended_at,
                exchange.routing_duration_ms,
                exchange.tts_started_at,
                exchange.tts_ended_at,
                exchange.tts_duration_ms,
                exchange.playback_started_at,
                exchange.playback_ended_at,
                exchange.playback_duration_ms,
                exchange.transcription,
                exchange.routing_path,
                exchange.matched_feature,
                exchange.feature_action,
                exchange.response_text,
                int(exchange.used_vad),
                int(exchange.had_bargein),
                int(exchange.is_follow_up),
                exchange.error,
            ),
        )

        for call in exchange.llm_calls:
            self._save_llm_call(exchange.id, call)

    def _save_llm_call(self, exchange_id: str, call: LLMCallInfo) -> None:
        """Insert an LLM call record (must be called within lock)."""
        self._conn.execute(
            "INSERT INTO llm_calls ("
            "  exchange_id, call_type, started_at, ended_at, duration_ms,"
            "  model, system_prompt, user_message, response_text,"
            "  input_tokens, output_tokens, stop_reason, error"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                exchange_id,
                call.call_type,
                call.started_at,
                call.ended_at,
                call.duration_ms,
                call.model,
                call.system_prompt,
                call.user_message,
                call.response_text,
                call.input_tokens,
                call.output_tokens,
                call.stop_reason,
                call.error,
            ),
        )

    def _maybe_prune(self) -> None:
        """If DB exceeds max size, delete the oldest 10% of sessions."""
        try:
            size = os.path.getsize(self._db_path)
            if size <= self._max_size_bytes:
                return

            with self._lock:
                total = self._conn.execute(
                    "SELECT COUNT(*) FROM sessions"
                ).fetchone()[0]
                if total == 0:
                    return

                to_delete = max(1, total // 10)
                oldest = self._conn.execute(
                    "SELECT id FROM sessions ORDER BY started_at ASC LIMIT ?",
                    (to_delete,),
                ).fetchall()
                ids = [row[0] for row in oldest]
                placeholders = ",".join("?" * len(ids))

                # Cascade: delete LLM calls for exchanges in these sessions
                self._conn.execute(
                    f"DELETE FROM llm_calls WHERE exchange_id IN "
                    f"(SELECT id FROM exchanges WHERE session_id IN ({placeholders}))",
                    ids,
                )
                self._conn.execute(
                    f"DELETE FROM exchanges WHERE session_id IN ({placeholders})",
                    ids,
                )
                self._conn.execute(
                    f"DELETE FROM sessions WHERE id IN ({placeholders})",
                    ids,
                )
                self._conn.commit()
                self._conn.execute("VACUUM")

                log.info(
                    "Pruned %d oldest sessions (DB was %dMB, limit %dMB)",
                    len(ids),
                    size // (1024 * 1024),
                    self._max_size_bytes // (1024 * 1024),
                )
        except Exception:
            log.exception("Telemetry prune failed (non-fatal)")

    def close(self) -> None:
        """Close the database connection."""
        try:
            self._conn.close()
        except Exception:
            pass
