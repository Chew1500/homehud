"""Tests for telemetry SQLite store."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from telemetry.models import LLMCallInfo, Session
from telemetry.store import TelemetryStore


def _make_store(tmp_path=None, max_size_mb=10240):
    """Create a TelemetryStore with a temp DB."""
    if tmp_path is None:
        tmp_path = tempfile.mkdtemp()
    db_path = os.path.join(tmp_path, "test_telemetry.db")
    return TelemetryStore(db_path, max_size_mb=max_size_mb)


def _make_session(with_exchange=True, with_llm_call=True):
    """Create a Session with optional exchange and LLM call."""
    session = Session(wake_model="hey_jarvis")
    if with_exchange:
        exchange = session.create_exchange()
        exchange.transcription = "add milk"
        exchange.routing_path = "llm_parse"
        exchange.matched_feature = "grocery"
        exchange.feature_action = "add"
        exchange.response_text = "Added milk."
        exchange.start_phase("recording")
        exchange.end_phase("recording")
        if with_llm_call:
            call = LLMCallInfo(
                call_type="parse_intent",
                model="claude-sonnet-4-5-20250929",
                system_prompt="You are an intent parser.",
                user_message="add milk",
                response_text='{"type":"action"}',
                input_tokens=100,
                output_tokens=50,
                stop_reason="end_turn",
                duration_ms=200,
            )
            exchange.llm_calls.append(call)
    session.finish()
    return session


def test_tables_created_on_init(tmp_path):
    """Store should create sessions, exchanges, and llm_calls tables."""
    store = _make_store(str(tmp_path))
    tables = store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names = {row[0] for row in tables}
    assert "sessions" in table_names
    assert "exchanges" in table_names
    assert "llm_calls" in table_names
    store.close()


def test_save_session_round_trip(tmp_path):
    """save_session should persist all fields and they should be retrievable."""
    store = _make_store(str(tmp_path))
    session = _make_session()

    store.save_session(session)

    # Verify session
    row = store._conn.execute(
        "SELECT * FROM sessions WHERE id = ?", (session.id,)
    ).fetchone()
    assert row is not None
    assert row["wake_model"] == "hey_jarvis"
    assert row["exchange_count"] == 1
    assert row["ended_at"] is not None

    # Verify exchange
    ex_row = store._conn.execute(
        "SELECT * FROM exchanges WHERE session_id = ?", (session.id,)
    ).fetchone()
    assert ex_row is not None
    assert ex_row["transcription"] == "add milk"
    assert ex_row["routing_path"] == "llm_parse"
    assert ex_row["matched_feature"] == "grocery"
    assert ex_row["feature_action"] == "add"
    assert ex_row["response_text"] == "Added milk."
    assert ex_row["recording_started_at"] is not None
    assert ex_row["recording_duration_ms"] is not None

    # Verify LLM call
    llm_row = store._conn.execute(
        "SELECT * FROM llm_calls WHERE exchange_id = ?",
        (session.exchanges[0].id,),
    ).fetchone()
    assert llm_row is not None
    assert llm_row["call_type"] == "parse_intent"
    assert llm_row["model"] == "claude-sonnet-4-5-20250929"
    assert llm_row["input_tokens"] == 100
    assert llm_row["output_tokens"] == 50
    assert llm_row["duration_ms"] == 200

    store.close()


def test_cascading_prune(tmp_path):
    """When DB exceeds max size, oldest sessions and their data should be deleted."""
    # Use a tiny max_size to trigger pruning
    store = _make_store(str(tmp_path), max_size_mb=0)  # 0 MB = always prune

    # Save multiple sessions
    sessions = []
    for i in range(5):
        s = _make_session()
        sessions.append(s)
        store.save_session(s)

    # Pruning should have removed oldest sessions
    remaining = store._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert remaining < 5

    # Verify cascading: no orphaned exchanges or LLM calls
    orphan_exchanges = store._conn.execute(
        "SELECT COUNT(*) FROM exchanges WHERE session_id NOT IN "
        "(SELECT id FROM sessions)"
    ).fetchone()[0]
    assert orphan_exchanges == 0

    orphan_calls = store._conn.execute(
        "SELECT COUNT(*) FROM llm_calls WHERE exchange_id NOT IN "
        "(SELECT id FROM exchanges)"
    ).fetchone()[0]
    assert orphan_calls == 0

    store.close()


def test_close_safe_to_call_twice(tmp_path):
    """close() should not raise when called twice."""
    store = _make_store(str(tmp_path))
    store.close()
    store.close()  # Should not raise


def test_save_session_without_exchanges(tmp_path):
    """Saving a session with no exchanges should work."""
    store = _make_store(str(tmp_path))
    session = Session(wake_model="hey_jarvis")
    session.finish()
    store.save_session(session)

    row = store._conn.execute(
        "SELECT * FROM sessions WHERE id = ?", (session.id,)
    ).fetchone()
    assert row is not None
    assert row["exchange_count"] == 0
    store.close()


def test_save_exchange_without_llm_calls(tmp_path):
    """Saving an exchange with no LLM calls should work."""
    store = _make_store(str(tmp_path))
    session = _make_session(with_llm_call=False)
    store.save_session(session)

    llm_count = store._conn.execute(
        "SELECT COUNT(*) FROM llm_calls WHERE exchange_id = ?",
        (session.exchanges[0].id,),
    ).fetchone()[0]
    assert llm_count == 0
    store.close()


def test_boolean_fields_stored_as_int(tmp_path):
    """Boolean fields (used_vad, had_bargein, is_follow_up) should be stored as integers."""
    store = _make_store(str(tmp_path))
    session = Session()
    exchange = session.create_exchange(is_follow_up=True)
    exchange.used_vad = True
    exchange.had_bargein = True
    session.finish()
    store.save_session(session)

    row = store._conn.execute(
        "SELECT used_vad, had_bargein, is_follow_up FROM exchanges WHERE id = ?",
        (exchange.id,),
    ).fetchone()
    assert row["used_vad"] == 1
    assert row["had_bargein"] == 1
    assert row["is_follow_up"] == 1
    store.close()
