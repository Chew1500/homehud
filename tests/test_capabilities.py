"""Tests for the capabilities feature."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from features.base import BaseFeature
from features.capabilities import CapabilitiesFeature


class StubFeature(BaseFeature):
    """Minimal BaseFeature subclass for testing."""

    def __init__(self, name: str, short_desc: str, desc: str = ""):
        super().__init__({})
        self._name = name
        self._short_desc = short_desc
        self._desc = desc

    @property
    def name(self) -> str:
        return self._name

    @property
    def short_description(self) -> str:
        return self._short_desc

    @property
    def description(self) -> str:
        return self._desc

    def matches(self, text: str) -> bool:
        return False

    def handle(self, text: str) -> str:
        return ""


def _make_caps():
    """Create a CapabilitiesFeature with two stub features."""
    f1 = StubFeature("Grocery List", "Manage your grocery lists", "Detailed grocery desc")
    f2 = StubFeature("Reminders", "Set timed reminders", "Detailed reminder desc")
    features = [f1, f2]
    caps = CapabilitiesFeature({}, features)
    features.append(caps)
    return caps, f1, f2


# -- matches(): list-all triggers --


def test_matches_what_can_you_do():
    caps, _, _ = _make_caps()
    assert caps.matches("what can you do")


def test_matches_what_are_your_features():
    caps, _, _ = _make_caps()
    assert caps.matches("what are your features")


def test_matches_help_me():
    caps, _, _ = _make_caps()
    assert caps.matches("help me")


def test_matches_list_your_skills():
    caps, _, _ = _make_caps()
    assert caps.matches("list your skills")


def test_matches_what_do_you_know_how_to_do():
    caps, _, _ = _make_caps()
    assert caps.matches("what do you know how to do")


def test_matches_what_are_your_capabilities():
    caps, _, _ = _make_caps()
    assert caps.matches("what are your capabilities")


def test_matches_what_are_you_capable_of():
    caps, _, _ = _make_caps()
    assert caps.matches("what are you capable of")


def test_no_match_unrelated():
    caps, _, _ = _make_caps()
    assert not caps.matches("what time is it")


def test_no_match_random():
    caps, _, _ = _make_caps()
    assert not caps.matches("add milk to the grocery list")


# -- matches(): describe-one triggers --


def test_matches_tell_me_about_known_feature():
    caps, _, _ = _make_caps()
    assert caps.matches("tell me about Grocery List")


def test_matches_describe_known_feature():
    caps, _, _ = _make_caps()
    assert caps.matches("describe Reminders")


def test_matches_what_is_known_feature():
    caps, _, _ = _make_caps()
    assert caps.matches("what is Grocery List")


def test_matches_case_insensitive():
    caps, _, _ = _make_caps()
    assert caps.matches("tell me about grocery list")


def test_no_match_unknown_feature():
    caps, _, _ = _make_caps()
    assert not caps.matches("tell me about the weather")


def test_no_match_describe_unknown():
    caps, _, _ = _make_caps()
    assert not caps.matches("describe the sunset")


# -- handle(): list-all --


def test_handle_list_all_contains_names():
    caps, _, _ = _make_caps()
    result = caps.handle("what can you do")
    assert "Grocery List" in result
    assert "Reminders" in result


def test_handle_list_all_contains_short_descriptions():
    caps, _, _ = _make_caps()
    result = caps.handle("what can you do")
    assert "Manage your grocery lists" in result
    assert "Set timed reminders" in result


def test_handle_list_all_contains_count():
    caps, _, _ = _make_caps()
    result = caps.handle("what can you do")
    assert "2 things" in result


def test_handle_list_all_contains_hint():
    caps, _, _ = _make_caps()
    result = caps.handle("what can you do")
    assert "tell me about" in result


# -- handle(): describe-one --


def test_handle_describe_one():
    caps, _, _ = _make_caps()
    result = caps.handle("tell me about Grocery List")
    assert "Grocery List" in result
    assert "Detailed grocery desc" in result


def test_handle_describe_one_case_insensitive():
    caps, _, _ = _make_caps()
    result = caps.handle("tell me about reminders")
    assert "Reminders" in result
    assert "Detailed reminder desc" in result


def test_handle_describe_one_falls_back_to_short_description():
    """If description is empty, short_description is used."""
    f1 = StubFeature("Widget", "A handy widget", "")
    features = [f1]
    caps = CapabilitiesFeature({}, features)
    features.append(caps)
    result = caps.handle("tell me about Widget")
    assert "A handy widget" in result


# -- self-exclusion --


def test_self_excluded_from_listing():
    caps, _, _ = _make_caps()
    result = caps.handle("what can you do")
    # "Help" is the capabilities feature's own name — should not appear in listing
    assert "Help:" not in result


def test_self_not_findable():
    caps, _, _ = _make_caps()
    assert not caps.matches("tell me about Help")


# -- own metadata --


def test_own_name():
    caps, _, _ = _make_caps()
    assert caps.name == "Help"


def test_own_short_description():
    caps, _, _ = _make_caps()
    assert caps.short_description == "Learn what I can help you with"


# -- single feature count --


def test_single_feature_says_thing():
    f1 = StubFeature("Only One", "The only feature")
    features = [f1]
    caps = CapabilitiesFeature({}, features)
    features.append(caps)
    result = caps.handle("what can you do")
    assert "1 thing" in result
