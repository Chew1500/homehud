"""Abstract base class for LLM backends."""

import time
from abc import ABC, abstractmethod


class BaseLLM(ABC):
    """Common interface for mock and real LLM backends.

    Input is a text string (from STT transcription).
    Output is the LLM's response string.

    Includes conversation history management so subclasses can support
    multi-turn interactions. History is stored as (user, assistant) pairs
    with time-based expiry.
    """

    def __init__(self, config: dict):
        self._config = config
        self._max_history = config.get("llm_max_history", 10)
        self._history_ttl = config.get("llm_history_ttl", 300)
        self._history: list[tuple[str, str, float]] = []  # (user, assistant, timestamp)

    def _expire_history(self) -> None:
        """Remove history entries older than TTL."""
        if self._history_ttl <= 0:
            return
        cutoff = time.monotonic() - self._history_ttl
        self._history = [(u, a, t) for u, a, t in self._history if t > cutoff]

    def _get_messages(self, text: str) -> list[dict]:
        """Build a messages array including history and the new user message."""
        self._expire_history()
        messages = []
        for user_msg, assistant_msg, _ts in self._history:
            messages.append({"role": "user", "content": user_msg})
            messages.append({"role": "assistant", "content": assistant_msg})
        messages.append({"role": "user", "content": text})
        return messages

    def _record_exchange(self, user: str, assistant: str) -> None:
        """Record a user/assistant exchange in history, trimming to max."""
        self._history.append((user, assistant, time.monotonic()))
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def clear_history(self) -> None:
        """Clear all conversation history."""
        self._history.clear()

    @abstractmethod
    def respond(self, text: str) -> str:
        """Generate a response to the given text.

        Args:
            text: User's spoken text (from STT transcription).

        Returns:
            LLM response string.
        """
        ...

    def close(self) -> None:
        """Clean up resources. Override if needed."""
        pass
