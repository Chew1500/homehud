"""Claude LLM backend using the Anthropic API."""

import logging

from llm.base import BaseLLM

log = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful voice assistant on a Raspberry Pi smart display. "
    "Keep responses concise — 2 to 3 sentences max. "
    "Be conversational and direct. "
    "If the user corrects a previous statement (e.g. 'no, I meant...'), "
    "use the conversation history to understand what they're correcting.\n\n"
    "You are part of a voice assistant that has these built-in features "
    "(handled before you):\n"
    '- Grocery/shopping list: "add X to grocery list", "remove X", '
    '"what\'s on my grocery list", "clear grocery list"\n'
    '- Reminders: "remind me to X in Y minutes"\n'
    "- Solar monitoring: questions about solar panels, production, energy, "
    "inverters\n"
    '- Repeat: "what did you say", "repeat that"\n\n'
    "If a query seems related to these features but was likely misheard by "
    "speech recognition, suggest the correct phrasing rather than trying to "
    'answer yourself. For example, if someone says "what\'s on the growth '
    'unit", they probably meant "what\'s on the grocery list".'
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
