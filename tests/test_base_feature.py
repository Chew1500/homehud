"""Tests for BaseFeature ABC enforcement."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from features.base import BaseFeature


def test_cannot_instantiate_without_name():
    """Omitting name should raise TypeError."""

    class MissingName(BaseFeature):
        @property
        def short_description(self):
            return "desc"

        def matches(self, text):
            return False

        def handle(self, text):
            return ""

    with pytest.raises(TypeError):
        MissingName({})


def test_cannot_instantiate_without_short_description():
    """Omitting short_description should raise TypeError."""

    class MissingShortDesc(BaseFeature):
        @property
        def name(self):
            return "Test"

        def matches(self, text):
            return False

        def handle(self, text):
            return ""

    with pytest.raises(TypeError):
        MissingShortDesc({})


def test_can_instantiate_with_all_required():
    """Providing all abstract members allows instantiation."""

    class Complete(BaseFeature):
        @property
        def name(self):
            return "Test"

        @property
        def short_description(self):
            return "A test feature"

        def matches(self, text):
            return False

        def handle(self, text):
            return ""

    feat = Complete({})
    assert feat.name == "Test"
    assert feat.short_description == "A test feature"
