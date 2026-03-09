"""Tests for the LLM abstraction layer."""

import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

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


def test_mock_classify_intent_returns_none():
    """MockLLM.classify_intent should always return None."""
    llm = MockLLM({})
    result = llm.classify_intent("what is on the gross free list", ["Grocery feature"])
    assert result is None


def test_classify_intent_does_not_affect_history():
    """classify_intent should not pollute conversation history."""
    llm = MockLLM({})
    llm.respond("hello")
    assert len(llm._history) == 1

    llm.classify_intent("garbled text", ["Some feature"])
    assert len(llm._history) == 1  # unchanged


def test_claude_personality_replaces_identity(monkeypatch):
    """When llm_personality is set, it replaces default identity but keeps constraints."""
    mock_anthropic = MagicMock()
    monkeypatch.setitem(sys.modules, "anthropic", mock_anthropic)

    from llm.claude_llm import _DEFAULT_IDENTITY, _SYSTEM_CONSTRAINTS, ClaudeLLM

    personality = "You are Geralt of Rivia. Speak in a sardonic tone."
    llm = ClaudeLLM({
        "anthropic_api_key": "test-key",
        "llm_personality": personality,
    })
    assert llm._system_prompt.startswith(personality)
    assert _DEFAULT_IDENTITY not in llm._system_prompt
    assert _SYSTEM_CONSTRAINTS in llm._system_prompt
    assert llm._system_prompt == personality + "\n\n" + _SYSTEM_CONSTRAINTS


def test_claude_personality_injected_into_parse_intent(monkeypatch):
    """When llm_personality is set, parse_intent includes it in system blocks."""
    mock_anthropic = MagicMock()
    monkeypatch.setitem(sys.modules, "anthropic", mock_anthropic)

    from llm.claude_llm import ClaudeLLM

    personality = "You are Geralt of Rivia. Speak in a sardonic tone."
    llm = ClaudeLLM({
        "anthropic_api_key": "test-key",
        "llm_personality": personality,
    })

    # Set up mock response with a tool_use block
    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = "route_intent"
    mock_block.input = {
        "type": "conversation",
        "speech": "Hmm.",
        "expects_follow_up": False,
    }
    mock_message = MagicMock()
    mock_message.content = [mock_block]
    mock_message.usage.input_tokens = 10
    mock_message.usage.output_tokens = 5
    mock_message.stop_reason = "end_turn"
    llm._client.messages.create.return_value = mock_message

    llm.parse_intent("hello", [])

    # Verify system blocks passed to the API
    call_kwargs = llm._client.messages.create.call_args
    system_blocks = call_kwargs.kwargs["system"]
    assert len(system_blocks) == 2
    assert system_blocks[1]["text"].startswith("## Personality")
    assert personality in system_blocks[1]["text"]

    # Verify telemetry records the full prompt
    assert personality in llm._last_call_info["system_prompt"]


def test_claude_no_personality_omits_intent_block(monkeypatch):
    """When llm_personality is empty, parse_intent has only one system block."""
    mock_anthropic = MagicMock()
    monkeypatch.setitem(sys.modules, "anthropic", mock_anthropic)

    from llm.claude_llm import ClaudeLLM

    llm = ClaudeLLM({"anthropic_api_key": "test-key", "llm_personality": ""})

    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = "route_intent"
    mock_block.input = {
        "type": "conversation",
        "speech": "Hello.",
        "expects_follow_up": False,
    }
    mock_message = MagicMock()
    mock_message.content = [mock_block]
    mock_message.usage.input_tokens = 10
    mock_message.usage.output_tokens = 5
    mock_message.stop_reason = "end_turn"
    llm._client.messages.create.return_value = mock_message

    llm.parse_intent("hello", [])

    call_kwargs = llm._client.messages.create.call_args
    system_blocks = call_kwargs.kwargs["system"]
    assert len(system_blocks) == 1


def test_claude_no_personality_uses_default(monkeypatch):
    """When llm_personality is empty, the default system prompt is used unmodified."""
    mock_anthropic = MagicMock()
    monkeypatch.setitem(sys.modules, "anthropic", mock_anthropic)

    from llm.claude_llm import DEFAULT_SYSTEM_PROMPT, ClaudeLLM

    llm = ClaudeLLM({"anthropic_api_key": "test-key", "llm_personality": ""})
    assert llm._system_prompt == DEFAULT_SYSTEM_PROMPT


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


@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)
def test_claude_classify_intent_integration():
    """classify_intent should correct a misheard grocery list command."""
    from llm.claude_llm import ClaudeLLM

    llm = ClaudeLLM({"anthropic_api_key": os.getenv("ANTHROPIC_API_KEY")})
    descriptions = [
        'Grocery/shopping list: triggered by "grocery list" or "shopping list". '
        'Commands: "add X to grocery list", "what\'s on the grocery list".',
    ]
    result = llm.classify_intent("what is on the gross free list", descriptions)
    assert result is not None
    assert "grocery" in result.lower()
    # Should not affect history
    assert len(llm._history) == 0
