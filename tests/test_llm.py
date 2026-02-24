"""Tests for the LLM abstraction layer."""

import os
import sys
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
