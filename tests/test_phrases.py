"""Tests for phrase pools and pick_phrase helper."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.phrases import (
    DEPLOY_PHRASES,
    STARTUP_PHRASES,
    WAKE_PHRASES,
    pick_phrase,
)


def test_wake_phrases_non_empty():
    assert len(WAKE_PHRASES) > 0


def test_startup_phrases_non_empty():
    assert len(STARTUP_PHRASES) > 0


def test_deploy_phrases_non_empty():
    assert len(DEPLOY_PHRASES) > 0


def test_pick_returns_element_from_pool():
    for _ in range(20):
        assert pick_phrase(WAKE_PHRASES) in WAKE_PHRASES


def test_pick_varies():
    """pick_phrase should return more than one unique phrase over many calls."""
    results = {pick_phrase(WAKE_PHRASES) for _ in range(50)}
    assert len(results) > 1
