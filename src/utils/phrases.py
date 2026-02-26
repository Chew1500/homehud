"""Phrase pools for varied TTS voice prompts."""

import random

WAKE_PHRASES = [
    "Yes?",
    "How can I help?",
    "What's up?",
    "I'm listening.",
    "Go ahead.",
    "What do you need?",
    "Hmm?",
    "Ready.",
]

STARTUP_PHRASES = [
    "Home HUD is ready.",
    "I'm up and running.",
    "All systems go.",
    "Ready when you are.",
    "Hello, I'm online.",
]

DEPLOY_PHRASES = [
    "I've been updated to the latest version.",
    "New update installed and ready.",
    "I just got an upgrade.",
    "Updated and ready to go.",
]


def pick_phrase(pool: list[str]) -> str:
    """Pick a random phrase from a pool."""
    return random.choice(pool)
