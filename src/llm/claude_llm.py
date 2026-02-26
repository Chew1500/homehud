"""Claude LLM backend using the Anthropic API."""

from __future__ import annotations

import logging

from llm.base import BaseLLM

log = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful voice assistant on a Raspberry Pi smart display. "
    "Keep responses concise — 2 to 3 sentences max. "
    "Be conversational and direct. "
    "If the user corrects a previous statement (e.g. 'no, I meant...'), "
    "use the conversation history to understand what they're correcting."
)

_CLASSIFY_SYSTEM_PROMPT = (
    "You are a speech-recognition error detector for a voice assistant. "
    "The assistant has these built-in features:\n\n"
    "{features}\n\n"
    "Your job: determine if the user's text is a misheard version of a command "
    "for one of these features. Speech recognition often garbles key trigger words "
    '(e.g. "grocery list" → "gross free list", "remind me" → "rye mend me").\n\n'
    "If the text is a misheard command, respond with ONLY the corrected command text. "
    "Nothing else — no explanation, no quotes, no punctuation beyond what the command needs.\n\n"
    "If the text is a genuine question or not related to any feature, respond with "
    "exactly: NONE\n\n"
    "Examples:\n"
    '- "what is on the gross free list" → what is on the grocery list\n'
    '- "add milk to the grow shriek list" → add milk to the grocery list\n'
    '- "rye mend me to buy eggs in ten minutes" → remind me to buy eggs in ten minutes\n'
    '- "what is the capital of France" → NONE\n'
    '- "tell me a joke" → NONE'
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
            messages = self._get_messages(text)
            message = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=self._system_prompt,
                messages=messages,
            )
            response = message.content[0].text
            self._record_exchange(text, response)
            return response
        except Exception:
            log.exception("Claude API error")
            return "Sorry, I wasn't able to process that. Please try again."

    def classify_intent(self, text: str, feature_descriptions: list[str]) -> str | None:
        """Detect misheard command via a focused, stateless API call."""
        try:
            features_block = "\n".join(
                f"- {desc}" for desc in feature_descriptions if desc
            )
            system = _CLASSIFY_SYSTEM_PROMPT.format(features=features_block)
            message = self._client.messages.create(
                model=self._model,
                max_tokens=100,
                system=system,
                messages=[{"role": "user", "content": text}],
            )
            result = message.content[0].text.strip()
            if result == "NONE":
                return None
            log.info("Intent classification corrected %r → %r", text, result)
            return result
        except Exception:
            log.exception("Intent classification error")
            return None
