"""Integration tests for telemetry with the voice pipeline and router."""

import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from intent.router import IntentRouter
from telemetry.store import TelemetryStore
from voice_pipeline import start_voice_pipeline

CHUNK = b"\x00\x00" * 1280


def _make_audio():
    audio = MagicMock()
    audio.sample_rate = 16000
    audio.record.return_value = b"\x00\x00" * 16000
    audio.is_playing.return_value = False

    def fake_stream(chunk_duration_ms=80):
        while True:
            yield CHUNK

    audio.stream.side_effect = fake_stream
    return audio


def _make_wake(trigger_on_chunk=1):
    wake = MagicMock()
    call_count = {"n": 0}

    def fake_detect(chunk):
        call_count["n"] += 1
        return call_count["n"] == trigger_on_chunk

    wake.detect.side_effect = fake_detect
    return wake


def _make_config():
    return {
        "voice_record_duration": 1,
        "voice_wake_feedback": False,
        "voice_vad_enabled": False,
        "voice_bargein_enabled": False,
        "wake_model": "hey_jarvis",
    }


def _make_router(response="Mock response."):
    router = MagicMock()
    router.route.return_value = response
    router.expects_follow_up = False
    router._last_route_info = {
        "path": "llm_parse",
        "matched_feature": "grocery",
        "feature_action": "add",
    }
    router._last_llm_calls = [{
        "call_type": "parse_intent",
        "model": "test-model",
        "system_prompt": "test prompt",
        "user_message": "test input",
        "response_text": "test response",
        "input_tokens": 10,
        "output_tokens": 5,
        "stop_reason": "end_turn",
        "duration_ms": 100,
    }]
    return router


def _make_tts():
    tts = MagicMock()
    tts.synthesize.return_value = b"\x00\x00" * 16000
    return tts


def test_pipeline_with_no_telemetry_store():
    """Pipeline should work unchanged when telemetry_store is None."""
    audio = _make_audio()
    stt = MagicMock()
    stt.transcribe.return_value = "hello"
    wake = _make_wake()
    router = _make_router()
    tts = _make_tts()

    running = threading.Event()
    running.set()

    thread = start_voice_pipeline(
        audio, stt, wake, router, tts, _make_config(), running,
        telemetry_store=None,
    )
    time.sleep(0.3)
    running.clear()
    thread.join(timeout=3)

    router.route.assert_called_with("hello")


def test_pipeline_with_real_store_saves_session(tmp_path):
    """Pipeline with a real store should save a session with correct data."""
    store = TelemetryStore(str(tmp_path / "telemetry.db"))

    audio = _make_audio()
    stt = MagicMock()
    stt.transcribe.return_value = "add milk"
    wake = _make_wake()
    router = _make_router("Added milk.")
    tts = _make_tts()

    running = threading.Event()
    running.set()

    thread = start_voice_pipeline(
        audio, stt, wake, router, tts, _make_config(), running,
        telemetry_store=store,
    )
    time.sleep(0.5)
    running.clear()
    thread.join(timeout=3)

    # Verify session was saved
    sessions = store._conn.execute("SELECT * FROM sessions").fetchall()
    assert len(sessions) >= 1

    session_row = sessions[0]
    assert session_row["wake_model"] == "hey_jarvis"
    assert session_row["exchange_count"] >= 1

    # Verify exchange
    exchanges = store._conn.execute("SELECT * FROM exchanges").fetchall()
    assert len(exchanges) >= 1

    ex_row = exchanges[0]
    assert ex_row["transcription"] == "add milk"
    assert ex_row["routing_path"] == "llm_parse"
    assert ex_row["matched_feature"] == "grocery"
    assert ex_row["response_text"] == "Added milk."

    # Verify LLM call
    llm_calls = store._conn.execute("SELECT * FROM llm_calls").fetchall()
    assert len(llm_calls) >= 1
    assert llm_calls[0]["call_type"] == "parse_intent"

    store.close()


def test_router_exposes_route_info_llm_parse():
    """Router should populate _last_route_info for LLM parse path."""
    feat = MagicMock()
    feat.name = "Grocery List"
    feat.description = ""
    feat.action_schema = {"add": {"item": "str"}}
    feat.get_llm_context.return_value = None
    feat.execute.return_value = "Added milk."
    feat.expects_follow_up = False
    feat.matches.return_value = False

    llm = MagicMock()
    llm._last_call_info = {
        "call_type": "parse_intent",
        "model": "test",
        "duration_ms": 100,
    }
    llm.parse_intent.return_value = {
        "type": "action",
        "feature": "grocery_list",
        "action": "add",
        "parameters": {"item": "milk"},
        "speech": "Adding milk.",
        "expects_follow_up": False,
    }

    router = IntentRouter({}, [feat], llm)
    router.route("add milk")

    assert router._last_route_info is not None
    assert router._last_route_info["path"] == "llm_parse"
    assert router._last_route_info["matched_feature"] == "grocery_list"
    assert router._last_route_info["feature_action"] == "add"


def test_router_exposes_route_info_regex():
    """Router should populate _last_route_info for regex path."""
    feat = MagicMock()
    feat.name = "Grocery List"
    feat.description = ""
    feat.action_schema = {}
    feat.get_llm_context.return_value = None
    feat.matches.return_value = True
    feat.handle.return_value = "List is empty."
    feat.expects_follow_up = False

    llm = MagicMock()
    llm._last_call_info = None
    llm.parse_intent.return_value = None

    router = IntentRouter({}, [feat], llm)
    router.route("grocery list")

    assert router._last_route_info is not None
    assert router._last_route_info["path"] == "regex"
    assert router._last_route_info["matched_feature"] == "Grocery List"


def test_router_exposes_route_info_recovery():
    """Router should populate _last_route_info for recovery path."""
    feat = MagicMock()
    feat.name = "Grocery"
    feat.description = "Grocery list"
    feat.action_schema = {}
    feat.get_llm_context.return_value = None
    feat.matches.side_effect = [False, True]
    feat.handle.return_value = "List is empty."
    feat.expects_follow_up = False

    llm = MagicMock()
    llm._last_call_info = {"call_type": "classify_intent"}
    llm.parse_intent.return_value = None
    llm.classify_intent.return_value = "grocery list"

    router = IntentRouter({}, [feat], llm)
    router.route("gross free list")

    assert router._last_route_info is not None
    assert router._last_route_info["path"] == "recovery"


def test_router_exposes_route_info_llm_fallback():
    """Router should populate _last_route_info for LLM fallback path."""
    feat = MagicMock()
    feat.name = "Grocery"
    feat.description = ""
    feat.action_schema = {}
    feat.get_llm_context.return_value = None
    feat.matches.return_value = False
    feat.expects_follow_up = False

    llm = MagicMock()
    llm._last_call_info = {"call_type": "respond"}
    llm.parse_intent.return_value = None
    llm.classify_intent.return_value = None
    llm.respond.return_value = "I don't know."

    router = IntentRouter({"intent_recovery_enabled": False}, [feat], llm)
    router.route("what is the meaning of life")

    assert router._last_route_info is not None
    assert router._last_route_info["path"] == "llm_fallback"


def test_router_collects_llm_calls():
    """Router should collect _last_llm_calls from each LLM method call."""
    feat = MagicMock()
    feat.name = "Grocery"
    feat.description = "Grocery list"
    feat.action_schema = {}
    feat.get_llm_context.return_value = None
    feat.matches.return_value = False
    feat.expects_follow_up = False

    llm = MagicMock()
    call_infos = [
        {"call_type": "parse_intent", "duration_ms": 100},
        {"call_type": "classify_intent", "duration_ms": 50},
        {"call_type": "respond", "duration_ms": 200},
    ]
    call_iter = iter(call_infos)

    def set_call_info(*args, **kwargs):
        llm._last_call_info = next(call_iter, None)
        return None

    llm.parse_intent.side_effect = set_call_info
    llm.classify_intent.side_effect = lambda *a, **kw: (
        setattr(llm, '_last_call_info', next(call_iter, None)) or None
    )
    llm.respond.side_effect = lambda *a, **kw: (
        setattr(llm, '_last_call_info', next(call_iter, None)) or "fallback"
    )

    router = IntentRouter({}, [feat], llm)
    router.route("what is life")

    assert len(router._last_llm_calls) >= 2


def test_telemetry_save_failure_is_nonfatal(tmp_path):
    """A failing telemetry store should not crash the pipeline."""
    store = MagicMock()
    store.save_session.side_effect = RuntimeError("DB write failed")

    audio = _make_audio()
    stt = MagicMock()
    stt.transcribe.return_value = "hello"
    wake = _make_wake()
    router = _make_router()
    tts = _make_tts()

    running = threading.Event()
    running.set()

    thread = start_voice_pipeline(
        audio, stt, wake, router, tts, _make_config(), running,
        telemetry_store=store,
    )
    time.sleep(0.5)
    running.clear()
    thread.join(timeout=3)

    # Pipeline should have still processed the command
    router.route.assert_called()
    # Store should have been called (and failed gracefully)
    store.save_session.assert_called()
