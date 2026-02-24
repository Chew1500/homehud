"""Claude LLM backend using the Anthropic API."""

import logging

from llm.base import BaseLLM

log = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful voice assistant on a Raspberry Pi smart display. "
    "Keep responses concise — 2 to 3 sentences max. "
    "Be conversational and direct."
)


class ClaudeLLM(BaseLLM):
    """LLM backend that calls the Anthropic Claude API."""

    def __init__(self, config: dict):
        super().__init__(config)

        api_key = config.get("anthropic_api_key")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is required for claude LLM mode. "
                "Set it in .env or as an environment variable."
            )

        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = config.get("llm_model", "claude-sonnet-4-5-20250929")
        self._max_tokens = config.get("llm_max_tokens", 1024)
        self._system_prompt = config.get("llm_system_prompt") or DEFAULT_SYSTEM_PROMPT

    def respond(self, text: str) -> str:
        """Send text to Claude and return the response."""
        try:
            message = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=self._system_prompt,
                messages=[{"role": "user", "content": text}],
            )
            return message.content[0].text
        except Exception:
            log.exception("Claude API error")
            return "Sorry, I wasn't able to process that. Please try again."
