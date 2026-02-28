"""Tests for LLM parse_intent() — tool_use response parsing and error handling."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from llm.mock_llm import MockLLM


def test_mock_parse_intent_returns_none():
    """MockLLM.parse_intent should always return None."""
    llm = MockLLM({})
    result = llm.parse_intent("add milk to the grocery list", [])
    assert result is None


def test_mock_parse_intent_with_context():
    """MockLLM.parse_intent should return None even with context."""
    llm = MockLLM({})
    result = llm.parse_intent("yes", [], context="Media disambiguation active")
    assert result is None


def test_record_exchange_public_api():
    """record_exchange() should add entries to history."""
    llm = MockLLM({})
    assert len(llm._history) == 0

    llm.record_exchange("hello", "hi there")
    assert len(llm._history) == 1
    assert llm._history[0][0] == "hello"
    assert llm._history[0][1] == "hi there"


def test_record_exchange_respects_max_history():
    """record_exchange() should trim at max_history."""
    llm = MockLLM({"llm_max_history": 2})
    llm.record_exchange("q1", "a1")
    llm.record_exchange("q2", "a2")
    llm.record_exchange("q3", "a3")
    assert len(llm._history) == 2
    assert llm._history[0][0] == "q2"
    assert llm._history[1][0] == "q3"


def test_parse_intent_does_not_affect_history():
    """parse_intent should not pollute conversation history."""
    llm = MockLLM({})
    llm.respond("hello")
    assert len(llm._history) == 1

    llm.parse_intent("garbled text", [])
    assert len(llm._history) == 1  # unchanged


# -- Claude LLM parse_intent tests (mocked API) --

try:
    import anthropic  # noqa: F401
    _has_anthropic = True
except ImportError:
    _has_anthropic = False

_skip_no_anthropic = pytest.mark.skipif(
    not _has_anthropic, reason="anthropic package not installed"
)


@_skip_no_anthropic
def test_claude_parse_intent_extracts_tool_use():
    """ClaudeLLM.parse_intent should extract the tool_use input dict."""
    from llm.claude_llm import ClaudeLLM

    tool_input = {
        "type": "action",
        "feature": "grocery",
        "action": "add",
        "parameters": {"item": "milk"},
        "speech": "Adding milk to your grocery list.",
        "expects_follow_up": False,
    }

    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = "route_intent"
    mock_block.input = tool_input

    mock_message = MagicMock()
    mock_message.content = [mock_block]

    with patch("anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = mock_message

        llm = ClaudeLLM({"anthropic_api_key": "test-key"})
        result = llm.parse_intent("add milk", [])

    assert result is not None
    assert result["type"] == "action"
    assert result["feature"] == "grocery"
    assert result["action"] == "add"
    assert result["parameters"]["item"] == "milk"


@_skip_no_anthropic
def test_claude_parse_intent_returns_none_on_no_tool_use():
    """parse_intent should return None when no tool_use block is present."""
    from llm.claude_llm import ClaudeLLM

    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = "I'm not sure what you mean."

    mock_message = MagicMock()
    mock_message.content = [mock_block]

    with patch("anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = mock_message

        llm = ClaudeLLM({"anthropic_api_key": "test-key"})
        result = llm.parse_intent("gibberish", [])

    assert result is None


@_skip_no_anthropic
def test_claude_parse_intent_returns_none_on_exception():
    """parse_intent should return None when the API raises an exception."""
    from llm.claude_llm import ClaudeLLM

    with patch("anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.side_effect = RuntimeError("API error")

        llm = ClaudeLLM({"anthropic_api_key": "test-key"})
        result = llm.parse_intent("add milk", [])

    assert result is None


@_skip_no_anthropic
def test_claude_parse_intent_passes_context():
    """parse_intent should prepend context to the user message."""
    from llm.claude_llm import ClaudeLLM

    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = "route_intent"
    mock_block.input = {"type": "action", "feature": "media", "action": "confirm",
                        "parameters": {}, "speech": "Confirmed.",
                        "expects_follow_up": False}

    mock_message = MagicMock()
    mock_message.content = [mock_block]

    with patch("anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = mock_message

        llm = ClaudeLLM({"anthropic_api_key": "test-key"})
        llm.parse_intent("yes", [], context="Media disambiguation active for Dune")

    call_kwargs = instance.messages.create.call_args
    messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
    user_msg = messages[-1]["content"]
    assert "[CONTEXT:" in user_msg
    assert "Dune" in user_msg
    assert "yes" in user_msg


@_skip_no_anthropic
def test_claude_parse_intent_does_not_record_history():
    """parse_intent should NOT record the exchange in history."""
    from llm.claude_llm import ClaudeLLM

    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = "route_intent"
    mock_block.input = {"type": "conversation", "speech": "Hello!",
                        "expects_follow_up": False}

    mock_message = MagicMock()
    mock_message.content = [mock_block]

    with patch("anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = mock_message

        llm = ClaudeLLM({"anthropic_api_key": "test-key"})
        llm.parse_intent("hello", [])

    assert len(llm._history) == 0


@_skip_no_anthropic
def test_claude_parse_intent_uses_intent_max_tokens():
    """parse_intent should use llm_intent_max_tokens config."""
    from llm.claude_llm import ClaudeLLM

    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = "route_intent"
    mock_block.input = {"type": "conversation", "speech": "Test",
                        "expects_follow_up": False}

    mock_message = MagicMock()
    mock_message.content = [mock_block]

    with patch("anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = mock_message

        llm = ClaudeLLM({"anthropic_api_key": "test-key", "llm_intent_max_tokens": 500})
        llm.parse_intent("test", [])

    call_kwargs = instance.messages.create.call_args
    max_tokens = call_kwargs.kwargs.get("max_tokens") or call_kwargs[1].get("max_tokens")
    assert max_tokens == 500


# -- Integration tests (require ANTHROPIC_API_KEY) --


@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)
def test_claude_parse_intent_integration():
    """parse_intent should return a structured dict from the real API."""
    from llm.claude_llm import ClaudeLLM

    llm = ClaudeLLM({"anthropic_api_key": os.getenv("ANTHROPIC_API_KEY")})
    result = llm.parse_intent("add milk to the grocery list", [])
    assert result is not None
    assert result["type"] == "action"
    assert result["feature"] == "grocery"
    assert result["action"] == "add"
    assert "milk" in result["parameters"].get("item", "").lower()
    assert len(llm._history) == 0
