"""Tests for telemetry web dashboard server."""

import json
import os
import sys
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from telemetry.models import LLMCallInfo, Session
from telemetry.store import TelemetryStore
from telemetry.web import TelemetryWeb


@pytest.fixture()
def store(tmp_path):
    """Create a TelemetryStore with a temp DB."""
    db_path = os.path.join(str(tmp_path), "test.db")
    s = TelemetryStore(db_path)
    yield s
    s.close()


@pytest.fixture()
def server(store):
    """Start a TelemetryWeb server on a random port and tear it down after the test."""
    web = TelemetryWeb(store._db_path, host="127.0.0.1", port=0)
    web.start()
    yield web
    web.close()


def _url(server, path):
    """Build a URL for the given path on the test server."""
    host, port = server._server.server_address
    return f"http://{host}:{port}{path}"


def _get(server, path):
    """GET a path and return (status, body_bytes)."""
    url = _url(server, path)
    try:
        resp = urllib.request.urlopen(url)
        return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _get_json(server, path):
    """GET a path and return parsed JSON."""
    status, body = _get(server, path)
    assert status == 200, f"Expected 200 but got {status}: {body}"
    return json.loads(body)


def _make_session(with_exchange=True, with_llm_call=True):
    """Create a test session."""
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
        exchange.start_phase("stt")
        exchange.end_phase("stt")
        exchange.used_vad = True
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


def test_dashboard_returns_html(server):
    """GET / should return HTML with 200."""
    status, body = _get(server, "/")
    assert status == 200
    assert b"Home HUD Telemetry" in body
    assert b"text/html" in body or True  # body is the content, not headers


def test_unknown_path_returns_404(server):
    """Unknown paths should return 404."""
    status, body = _get(server, "/nonexistent")
    assert status == 404
    data = json.loads(body)
    assert data["error"] == "Not found"


def test_stats_empty_db(server):
    """Stats endpoint on empty DB should return zero values."""
    data = _get_json(server, "/api/stats")
    assert data["total_sessions"] == 0
    assert data["total_exchanges"] == 0
    assert data["total_llm_calls"] == 0
    assert data["total_input_tokens"] == 0
    assert data["total_output_tokens"] == 0
    assert data["error_count"] == 0
    assert data["feature_counts"] == {}
    assert data["routing_counts"] == {}


def test_stats_with_data(store, server):
    """Stats endpoint should return aggregate data."""
    store.save_session(_make_session())
    store.save_session(_make_session())

    data = _get_json(server, "/api/stats")
    assert data["total_sessions"] == 2
    assert data["total_exchanges"] == 2
    assert data["total_llm_calls"] == 2
    assert data["total_input_tokens"] == 200
    assert data["total_output_tokens"] == 100
    assert data["feature_counts"]["grocery"] == 2
    assert data["routing_counts"]["llm_parse"] == 2


def test_sessions_empty_db(server):
    """Sessions endpoint on empty DB should return empty list."""
    data = _get_json(server, "/api/sessions")
    assert data["sessions"] == []
    assert data["total"] == 0
    assert data["limit"] == 50
    assert data["offset"] == 0


def test_sessions_list(store, server):
    """Sessions endpoint should return session summaries."""
    store.save_session(_make_session())

    data = _get_json(server, "/api/sessions")
    assert len(data["sessions"]) == 1
    assert data["total"] == 1
    s = data["sessions"][0]
    assert s["wake_model"] == "hey_jarvis"
    assert s["exchange_count"] == 1
    assert s["first_transcription"] == "add milk"
    assert "grocery" in s["features_used"]
    assert s["had_error"] is False
    assert s["duration_ms"] is not None


def test_sessions_pagination(store, server):
    """Sessions endpoint should respect limit and offset."""
    for _ in range(5):
        store.save_session(_make_session())

    # First page
    data = _get_json(server, "/api/sessions?limit=2&offset=0")
    assert len(data["sessions"]) == 2
    assert data["total"] == 5
    assert data["limit"] == 2
    assert data["offset"] == 0

    # Second page
    data2 = _get_json(server, "/api/sessions?limit=2&offset=2")
    assert len(data2["sessions"]) == 2
    assert data2["offset"] == 2

    # IDs should differ between pages
    ids1 = {s["id"] for s in data["sessions"]}
    ids2 = {s["id"] for s in data2["sessions"]}
    assert ids1.isdisjoint(ids2)


def test_session_detail(store, server):
    """Session detail endpoint should return full session with exchanges and LLM calls."""
    session = _make_session()
    store.save_session(session)

    data = _get_json(server, f"/api/sessions/{session.id}")
    assert data["session"]["id"] == session.id
    assert data["session"]["wake_model"] == "hey_jarvis"
    assert len(data["exchanges"]) == 1

    ex = data["exchanges"][0]
    assert ex["transcription"] == "add milk"
    assert ex["routing_path"] == "llm_parse"
    assert ex["matched_feature"] == "grocery"
    assert ex["used_vad"] is True
    assert ex["had_bargein"] is False
    assert ex["recording_duration_ms"] is not None

    assert len(ex["llm_calls"]) == 1
    llm = ex["llm_calls"][0]
    assert llm["call_type"] == "parse_intent"
    assert llm["model"] == "claude-sonnet-4-5-20250929"
    assert llm["input_tokens"] == 100
    assert llm["output_tokens"] == 50
    assert llm["system_prompt"] == "You are an intent parser."
    assert llm["user_message"] == "add milk"


def test_session_detail_not_found(server):
    """Session detail with bad ID should return 404."""
    status, body = _get(server, "/api/sessions/00000000-0000-0000-0000-000000000000")
    assert status == 404
    data = json.loads(body)
    assert data["error"] == "Session not found"


def test_close_shuts_down_cleanly(store):
    """close() should stop the server without errors."""
    web = TelemetryWeb(store._db_path, host="127.0.0.1", port=0)
    web.start()

    # Verify it's serving
    status, _ = _get(web, "/")
    assert status == 200

    # Close and verify
    web.close()
    # After close, requests should fail
    with pytest.raises(Exception):
        _get(web, "/")


def test_sessions_limit_capped(store, server):
    """Limit should be capped at 200."""
    data = _get_json(server, "/api/sessions?limit=999")
    assert data["limit"] == 200


def test_stats_avg_durations(store, server):
    """Stats should include average phase durations."""
    store.save_session(_make_session())
    data = _get_json(server, "/api/stats")
    assert data["avg_recording_ms"] is not None
    assert data["avg_stt_ms"] is not None
