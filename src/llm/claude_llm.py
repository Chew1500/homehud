"""Claude LLM backend using the Anthropic API."""

from __future__ import annotations

import json
import logging
import time

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


_INTENT_SYSTEM_PROMPT = (
    "You are an intent parser for a Raspberry Pi voice assistant called Home HUD.\n"
    "The user's speech has been transcribed by Whisper and may contain recognition errors.\n"
    "Use the route_intent tool to respond. ALWAYS use this tool.\n\n"
    "## Available Features\n\n"
    "### grocery\n"
    "Actions: add(item), remove(item), list(), clear()\n"
    'Example triggers: "add milk to grocery list", "what\'s on the shopping list"\n\n'
    "### reminder\n"
    "Actions: set(task, time), list(), cancel(task), clear()\n"
    'The "time" parameter should be a natural language time expression.\n'
    'Example triggers: "remind me to call mom in 20 minutes", "remind me at 3pm to..."\n\n'
    "### media\n"
    "Actions: track(title, media_type), list(media_type), check(title),\n"
    "         confirm(), skip(), cancel(), select(index),\n"
    "         refine_year(year), refine_type(media_type), refine_recent()\n"
    'media_type: "movie", "show", or "any"\n'
    'Example triggers: "track the movie Inception", "what shows do I have"\n\n'
    "### solar\n"
    "Actions: query(question)\n"
    'Example triggers: "how much solar am I producing", "am I exporting to the grid"\n\n'
    "### repeat\n"
    "Actions: replay()\n"
    'Example triggers: "what did you say", "repeat that", "say that again"\n\n'
    "### capabilities\n"
    "Actions: list(), describe(feature)\n"
    'Example triggers: "what can you do", "tell me about reminders"\n\n'
    "## Guidelines\n"
    '- Use "action" when the user clearly wants a feature. Use "conversation" for general Q&A.\n'
    '  Use "clarification" only when the transcription is too ambiguous to determine intent.\n'
    '- Common STT errors: "gross free"→"grocery", "rye mend"→"remind", garbled movie titles\n'
    '- Keep "speech" concise (1-2 sentences), suitable for text-to-speech\n'
    "- For actions, still provide a brief speech (used as fallback if feature errors)\n\n"
    "## Follow-up Signal\n"
    '- Set "expects_follow_up": true when asking a question, presenting options, '
    "in a multi-turn flow, or when the input appears cut off\n"
    '- Set "expects_follow_up": false for complete answers and terminal actions\n\n'
    "## Context Priority\n"
    "- When [CONTEXT: ...] is present, ALWAYS prioritize routing to the relevant feature\n"
    "- Partial transcriptions in follow-up should be interpreted in the active context, "
    "not as standalone statements"
)

_ROUTE_INTENT_TOOL = {
    "name": "route_intent",
    "description": (
        "Parse the user's voice command and route to the appropriate "
        "action or respond conversationally."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": ["action", "conversation", "clarification"],
            },
            "feature": {"type": "string"},
            "action": {"type": "string"},
            "parameters": {"type": "object"},
            "speech": {"type": "string"},
            "expects_follow_up": {
                "type": "boolean",
                "description": (
                    "True when this response asks the user a question, "
                    "presents options, or needs further input."
                ),
            },
        },
        "required": ["type", "speech", "expects_follow_up"],
    },
}


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
        self._intent_max_tokens = config.get("llm_intent_max_tokens", 300)
        self._system_prompt = config.get("llm_system_prompt") or DEFAULT_SYSTEM_PROMPT

    def parse_intent(
        self, text: str, feature_schemas: list[dict], context: str | None = None
    ) -> dict | None:
        """Parse user intent via Claude tool_use for structured output."""
        self._last_call_info = None
        t0 = time.monotonic()
        try:
            user_content = text
            if context:
                user_content = f"[CONTEXT: {context}]\n\n{text}"

            messages = self._get_messages(user_content)

            message = self._client.messages.create(
                model=self._model,
                max_tokens=self._intent_max_tokens,
                system=[{
                    "type": "text",
                    "text": _INTENT_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=messages,
                tools=[_ROUTE_INTENT_TOOL],
                tool_choice={"type": "tool", "name": "route_intent"},
            )

            # Extract response for telemetry
            response_text = None
            result = None
            for block in message.content:
                if block.type == "tool_use" and block.name == "route_intent":
                    result = block.input
                    response_text = json.dumps(result)

            self._last_call_info = {
                "call_type": "parse_intent",
                "model": self._model,
                "system_prompt": _INTENT_SYSTEM_PROMPT,
                "user_message": user_content,
                "response_text": response_text,
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
                "stop_reason": message.stop_reason,
                "duration_ms": int((time.monotonic() - t0) * 1000),
            }

            if result is not None:
                log.info(
                    "Intent parsed: type=%s feature=%s action=%s",
                    result.get("type"),
                    result.get("feature"),
                    result.get("action"),
                )
                return result

            block_summary = [
                f"{b.type}({b.text[:80]}...)" if b.type == "text" else b.type
                for b in message.content
            ]
            log.warning(
                "No tool_use block in parse_intent response: "
                "stop_reason=%s blocks=%s",
                getattr(message, "stop_reason", "unknown"),
                block_summary,
            )
            return None
        except Exception as exc:
            self._last_call_info = {
                "call_type": "parse_intent",
                "model": self._model,
                "system_prompt": _INTENT_SYSTEM_PROMPT,
                "user_message": text,
                "response_text": None,
                "input_tokens": None,
                "output_tokens": None,
                "stop_reason": None,
                "duration_ms": int((time.monotonic() - t0) * 1000),
                "error": str(exc),
            }
            log.exception("parse_intent error")
            return None

    def respond(self, text: str) -> str:
        """Send text to Claude and return the response."""
        self._last_call_info = None
        t0 = time.monotonic()
        try:
            messages = self._get_messages(text)
            message = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=self._system_prompt,
                messages=messages,
            )
            response = message.content[0].text
            self._last_call_info = {
                "call_type": "respond",
                "model": self._model,
                "system_prompt": self._system_prompt,
                "user_message": text,
                "response_text": response,
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
                "stop_reason": message.stop_reason,
                "duration_ms": int((time.monotonic() - t0) * 1000),
            }
            self._record_exchange(text, response)
            return response
        except Exception as exc:
            self._last_call_info = {
                "call_type": "respond",
                "model": self._model,
                "system_prompt": self._system_prompt,
                "user_message": text,
                "response_text": None,
                "input_tokens": None,
                "output_tokens": None,
                "stop_reason": None,
                "duration_ms": int((time.monotonic() - t0) * 1000),
                "error": str(exc),
            }
            log.exception("Claude API error")
            return "Sorry, I wasn't able to process that. Please try again."

    def classify_intent(self, text: str, feature_descriptions: list[str]) -> str | None:
        """Detect misheard command via a focused, stateless API call."""
        self._last_call_info = None
        t0 = time.monotonic()
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
            self._last_call_info = {
                "call_type": "classify_intent",
                "model": self._model,
                "system_prompt": system,
                "user_message": text,
                "response_text": result,
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
                "stop_reason": message.stop_reason,
                "duration_ms": int((time.monotonic() - t0) * 1000),
            }
            if result == "NONE":
                return None
            log.info("Intent classification corrected %r → %r", text, result)
            return result
        except Exception as exc:
            self._last_call_info = {
                "call_type": "classify_intent",
                "model": self._model,
                "system_prompt": None,
                "user_message": text,
                "response_text": None,
                "input_tokens": None,
                "output_tokens": None,
                "stop_reason": None,
                "duration_ms": int((time.monotonic() - t0) * 1000),
                "error": str(exc),
            }
            log.exception("Intent classification error")
            return None
