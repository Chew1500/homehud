"""Tests for the LLM abstraction layer."""

import os
import sys
import time
from pathlib import Path

import pytest

# Add src to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from llm import get_llm
from llm.mock_llm import MockLLM


def test_mock_llm_default_response():
    """MockLLM should return the default canned response."""
    llm = MockLLM({})
    result = llm.respond("What is the weather?")
    assert result == "This is a mock LLM response."


def test_mock_llm_custom_response():
    """MockLLM should return a custom response when configured."""
    llm = MockLLM({"llm_mock_response": "Custom response here."})
    result = llm.respond("Tell me a joke")
    assert result == "Custom response here."


def test_mock_llm_ignores_input():
    """MockLLM should return the same response regardless of input."""
    llm = MockLLM({})
    assert llm.respond("") == "This is a mock LLM response."
    assert llm.respond("anything at all") == "This is a mock LLM response."


def test_factory_returns_mock():
    """get_llm() should return MockLLM when mode is 'mock'."""
    llm = get_llm({"llm_mode": "mock"})
    assert isinstance(llm, MockLLM)


def test_factory_returns_mock_when_unset():
    """get_llm() should return MockLLM when llm_mode is not set."""
    llm = get_llm({})
    assert isinstance(llm, MockLLM)


def test_mock_llm_close():
    """close() should not raise."""
    llm = MockLLM({})
    llm.close()


def test_claude_llm_requires_api_key():
    """ClaudeLLM should raise ValueError when API key is missing."""
    from llm.claude_llm import ClaudeLLM

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        ClaudeLLM({"anthropic_api_key": ""})


def test_history_records_exchanges():
    """respond() should record exchanges in history."""
    llm = MockLLM({})
    llm.respond("first question")
    llm.respond("second question")

    assert len(llm._history) == 2
    assert llm._history[0][0] == "first question"
    assert llm._history[1][0] == "second question"


def test_history_trims_at_max():
    """History should be trimmed when it exceeds max_history."""
    llm = MockLLM({"llm_max_history": 3})
    for i in range(5):
        llm.respond(f"question {i}")

    assert len(llm._history) == 3
    # Should keep the 3 most recent
    assert llm._history[0][0] == "question 2"
    assert llm._history[2][0] == "question 4"


def test_history_ttl_expiry():
    """Expired history entries should be removed."""
    llm = MockLLM({"llm_history_ttl": 1})
    llm.respond("old question")

    # Manually backdate the timestamp
    user, assistant, _ts = llm._history[0]
    llm._history[0] = (user, assistant, time.monotonic() - 2)

    # Next call triggers expiry via _get_messages
    messages = llm._get_messages("new question")
    # Should only have the new message, old one expired
    assert len(messages) == 1
    assert messages[0]["content"] == "new question"


def test_history_builds_messages():
    """_get_messages should build correct message array with history."""
    llm = MockLLM({})
    llm.respond("hello")

    messages = llm._get_messages("follow up")
    assert len(messages) == 3  # user, assistant, user
    assert messages[0] == {"role": "user", "content": "hello"}
    assert messages[1] == {"role": "assistant", "content": "This is a mock LLM response."}
    assert messages[2] == {"role": "user", "content": "follow up"}


def test_clear_history():
    """clear_history() should remove all entries."""
    llm = MockLLM({})
    llm.respond("hello")
    llm.respond("world")
    assert len(llm._history) == 2

    llm.clear_history()
    assert len(llm._history) == 0


@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)
def test_claude_llm_integration():
    """ClaudeLLM should return a non-empty response from the real API."""
    from llm.claude_llm import ClaudeLLM

    llm = ClaudeLLM({"anthropic_api_key": os.getenv("ANTHROPIC_API_KEY")})
    result = llm.respond("Say hello in exactly three words.")
    assert isinstance(result, str)
    assert len(result) > 0
