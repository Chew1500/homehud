"""Tests for telemetry data models."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from telemetry.models import Exchange, LLMCallInfo, Session


def test_exchange_phase_timing():
    """start_phase/end_phase should set timestamps and compute duration_ms."""
    exchange = Exchange()
    exchange.start_phase("recording")
    time.sleep(0.01)
    exchange.end_phase("recording")

    assert exchange.recording_started_at is not None
    assert exchange.recording_ended_at is not None
    assert exchange.recording_duration_ms is not None
    assert exchange.recording_duration_ms >= 0


def test_exchange_multiple_phases():
    """Each phase should track independently."""
    exchange = Exchange()
    for phase in ("recording", "stt", "routing", "tts", "playback"):
        exchange.start_phase(phase)
        exchange.end_phase(phase)
        assert getattr(exchange, f"{phase}_started_at") is not None
        assert getattr(exchange, f"{phase}_ended_at") is not None
        assert getattr(exchange, f"{phase}_duration_ms") is not None


def test_session_creates_exchanges_with_sequential_numbering():
    """Session should assign sequential numbers and propagate session_id."""
    session = Session()
    e0 = session.create_exchange()
    e1 = session.create_exchange(is_follow_up=True)

    assert e0.session_id == session.id
    assert e1.session_id == session.id
    assert e0.sequence == 0
    assert e1.sequence == 1
    assert e0.is_follow_up is False
    assert e1.is_follow_up is True
    assert session.exchange_count == 2


def test_session_finish():
    """Session.finish() should set ended_at."""
    session = Session()
    assert session.ended_at is None
    session.finish()
    assert session.ended_at is not None


def test_llm_call_info_finish():
    """LLMCallInfo.finish() should set ended_at and compute duration_ms."""
    call = LLMCallInfo(call_type="parse_intent")
    from telemetry.models import _now

    call.started_at = _now()
    time.sleep(0.01)
    call.finish()

    assert call.ended_at is not None
    assert call.duration_ms is not None
    assert call.duration_ms >= 0


def test_exchange_has_unique_ids():
    """Each exchange should have a unique UUID."""
    e1 = Exchange()
    e2 = Exchange()
    assert e1.id != e2.id


def test_session_has_unique_ids():
    """Each session should have a unique UUID."""
    s1 = Session()
    s2 = Session()
    assert s1.id != s2.id
