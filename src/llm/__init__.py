"""LLM abstraction layer.

Provides a unified interface for LLM backends:
- MockLLM: returns canned responses (for development)
- ClaudeLLM: Anthropic Claude API (for production)
"""

from llm.base import BaseLLM
from llm.mock_llm import MockLLM


def get_llm(config: dict) -> BaseLLM:
    """Factory: return the appropriate LLM backend based on config."""
    mode = config.get("llm_mode", "mock")

    if mode == "claude":
        from llm.claude_llm import ClaudeLLM
        return ClaudeLLM(config)
    else:
        return MockLLM(config)
