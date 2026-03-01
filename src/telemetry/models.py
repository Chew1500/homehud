"""Telemetry data models for voice transaction tracking."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ms_between(start: str, end: str) -> int:
    """Compute milliseconds between two ISO timestamps."""
    t0 = datetime.fromisoformat(start)
    t1 = datetime.fromisoformat(end)
    return int((t1 - t0).total_seconds() * 1000)


@dataclass
class LLMCallInfo:
    """Metadata for a single Anthropic API call."""

    call_type: str  # "parse_intent" | "classify_intent" | "respond"
    started_at: str | None = None
    ended_at: str | None = None
    duration_ms: int | None = None
    model: str | None = None
    system_prompt: str | None = None
    user_message: str | None = None
    response_text: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    stop_reason: str | None = None
    error: str | None = None

    def finish(self) -> None:
        """Set ended_at and compute duration_ms."""
        self.ended_at = _now()
        if self.started_at and self.ended_at:
            self.duration_ms = _ms_between(self.started_at, self.ended_at)


PHASE_NAMES = ("recording", "stt", "routing", "tts", "playback")


@dataclass
class Exchange:
    """One command/response cycle within a session."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    sequence: int = 0

    # Phase timestamps + durations
    recording_started_at: str | None = None
    recording_ended_at: str | None = None
    recording_duration_ms: int | None = None
    stt_started_at: str | None = None
    stt_ended_at: str | None = None
    stt_duration_ms: int | None = None
    routing_started_at: str | None = None
    routing_ended_at: str | None = None
    routing_duration_ms: int | None = None
    tts_started_at: str | None = None
    tts_ended_at: str | None = None
    tts_duration_ms: int | None = None
    playback_started_at: str | None = None
    playback_ended_at: str | None = None
    playback_duration_ms: int | None = None

    # STT output
    transcription: str | None = None

    # Routing decision
    routing_path: str | None = None
    matched_feature: str | None = None
    feature_action: str | None = None
    response_text: str | None = None

    # Flags
    used_vad: bool = False
    had_bargein: bool = False
    is_follow_up: bool = False
    error: str | None = None

    # LLM calls made during this exchange
    llm_calls: list[LLMCallInfo] = field(default_factory=list)

    def start_phase(self, name: str) -> None:
        """Record the start timestamp for a pipeline phase."""
        setattr(self, f"{name}_started_at", _now())

    def end_phase(self, name: str) -> None:
        """Record the end timestamp and compute duration for a pipeline phase."""
        setattr(self, f"{name}_ended_at", _now())
        started = getattr(self, f"{name}_started_at", None)
        ended = getattr(self, f"{name}_ended_at")
        if started and ended:
            setattr(self, f"{name}_duration_ms", _ms_between(started, ended))


@dataclass
class Session:
    """A voice interaction session, starting from wake word detection."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: str = field(default_factory=_now)
    ended_at: str | None = None
    wake_model: str | None = None
    exchanges: list[Exchange] = field(default_factory=list)

    @property
    def exchange_count(self) -> int:
        return len(self.exchanges)

    def create_exchange(self, is_follow_up: bool = False) -> Exchange:
        """Create a new exchange within this session."""
        exchange = Exchange(
            session_id=self.id,
            sequence=len(self.exchanges),
            is_follow_up=is_follow_up,
        )
        self.exchanges.append(exchange)
        return exchange

    def finish(self) -> None:
        """Mark the session as ended."""
        self.ended_at = _now()
