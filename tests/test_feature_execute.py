"""Tests for feature execute() methods — structured action dispatch."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# -- Grocery execute() --


class TestGroceryExecute:

    def _make(self, tmp_path):
        from features.grocery import GroceryFeature
        return GroceryFeature({"grocery_file": str(tmp_path / "grocery.json")})

    def test_action_schema(self, tmp_path):
        feat = self._make(tmp_path)
        schema = feat.action_schema
        assert "add" in schema
        assert "remove" in schema
        assert "list" in schema
        assert "clear" in schema

    def test_execute_add(self, tmp_path):
        feat = self._make(tmp_path)
        result = feat.execute("add", {"item": "milk"})
        assert "Added milk" in result

    def test_execute_add_duplicate(self, tmp_path):
        feat = self._make(tmp_path)
        feat.execute("add", {"item": "milk"})
        result = feat.execute("add", {"item": "milk"})
        assert "already" in result

    def test_execute_remove(self, tmp_path):
        feat = self._make(tmp_path)
        feat.execute("add", {"item": "eggs"})
        result = feat.execute("remove", {"item": "eggs"})
        assert "Removed eggs" in result

    def test_execute_list_empty(self, tmp_path):
        feat = self._make(tmp_path)
        result = feat.execute("list", {})
        assert "empty" in result

    def test_execute_list_with_items(self, tmp_path):
        feat = self._make(tmp_path)
        feat.execute("add", {"item": "milk"})
        feat.execute("add", {"item": "bread"})
        result = feat.execute("list", {})
        assert "milk" in result
        assert "bread" in result

    def test_execute_clear(self, tmp_path):
        feat = self._make(tmp_path)
        feat.execute("add", {"item": "milk"})
        result = feat.execute("clear", {})
        assert "cleared" in result

    def test_execute_unknown_action(self, tmp_path):
        feat = self._make(tmp_path)
        result = feat.execute("unknown", {})
        # Falls back to list
        assert "empty" in result


# -- Reminder execute() --


class TestReminderExecute:

    def _make(self, tmp_path):
        from features.reminder import ReminderFeature
        return ReminderFeature({"reminder_file": str(tmp_path / "reminders.json")})

    def test_action_schema(self, tmp_path):
        feat = self._make(tmp_path)
        schema = feat.action_schema
        assert "set" in schema
        assert "list" in schema
        assert "cancel" in schema
        assert "clear" in schema

    def test_execute_set_relative(self, tmp_path):
        feat = self._make(tmp_path)
        result = feat.execute("set", {"task": "buy eggs", "time": "in 5 minutes"})
        assert "remind you" in result.lower() or "buy eggs" in result

    def test_execute_set_absolute(self, tmp_path):
        feat = self._make(tmp_path)
        result = feat.execute("set", {"task": "call mom", "time": "3pm"})
        assert "call mom" in result

    def test_execute_set_tomorrow(self, tmp_path):
        feat = self._make(tmp_path)
        result = feat.execute("set", {"task": "water plants", "time": "tomorrow"})
        assert "water plants" in result

    def test_execute_set_bad_time(self, tmp_path):
        feat = self._make(tmp_path)
        result = feat.execute("set", {"task": "something", "time": "banana"})
        assert "didn't understand" in result

    def test_execute_list_empty(self, tmp_path):
        feat = self._make(tmp_path)
        result = feat.execute("list", {})
        assert "don't have any" in result

    def test_execute_set_then_list(self, tmp_path):
        feat = self._make(tmp_path)
        feat.execute("set", {"task": "buy eggs", "time": "in 5 minutes"})
        result = feat.execute("list", {})
        assert "buy eggs" in result

    def test_execute_cancel(self, tmp_path):
        feat = self._make(tmp_path)
        feat.execute("set", {"task": "buy eggs", "time": "in 10 minutes"})
        result = feat.execute("cancel", {"task": "buy eggs"})
        assert "Cancelled" in result

    def test_execute_clear(self, tmp_path):
        feat = self._make(tmp_path)
        feat.execute("set", {"task": "buy eggs", "time": "in 10 minutes"})
        result = feat.execute("clear", {})
        assert "cleared" in result

    def test_parse_time_expression_relative_no_prefix(self, tmp_path):
        """parse_time_expression should handle '5 minutes' without 'in'."""
        feat = self._make(tmp_path)
        result = feat.execute("set", {"task": "test", "time": "5 minutes"})
        assert "test" in result

    def test_parse_time_expression_tomorrow_at(self, tmp_path):
        """parse_time_expression should handle 'tomorrow at 3pm'."""
        feat = self._make(tmp_path)
        result = feat.execute("set", {"task": "meeting", "time": "tomorrow at 3pm"})
        assert "meeting" in result


# -- Media execute() --


class TestMediaExecute:

    def _make(self):
        from features.media import MediaFeature
        from media.mock_radarr import MockRadarrClient
        from media.mock_sonarr import MockSonarrClient
        config = {"media_disambiguation_ttl": 60}
        return MediaFeature(
            config,
            sonarr=MockSonarrClient(config),
            radarr=MockRadarrClient(config),
        )

    def test_action_schema(self):
        feat = self._make()
        schema = feat.action_schema
        assert "track" in schema
        assert "list" in schema
        assert "check" in schema
        assert "confirm" in schema
        assert "skip" in schema
        assert "cancel" in schema
        assert "select" in schema

    def test_execute_list_movies(self):
        feat = self._make()
        result = feat.execute("list", {"media_type": "movie"})
        assert "Inception" in result

    def test_execute_list_shows(self):
        feat = self._make()
        result = feat.execute("list", {"media_type": "show"})
        assert "Breaking Bad" in result

    def test_execute_check(self):
        feat = self._make()
        result = feat.execute("check", {"title": "Inception"})
        assert "Yes" in result

    def test_execute_check_not_found(self):
        feat = self._make()
        result = feat.execute("check", {"title": "The Matrix"})
        assert "don't see" in result

    def test_execute_track_movie(self):
        feat = self._make()
        result = feat.execute("track", {"title": "The Matrix", "media_type": "movie"})
        assert "I found" in result or "already" in result

    def test_execute_track_show(self):
        feat = self._make()
        result = feat.execute("track", {"title": "The Bear", "media_type": "show"})
        assert "I found" in result

    def test_execute_confirm_no_pending(self):
        feat = self._make()
        result = feat.execute("confirm", {})
        assert "nothing to confirm" in result.lower()

    def test_execute_confirm_with_pending(self):
        feat = self._make()
        feat.execute("track", {"title": "The Matrix", "media_type": "movie"})
        assert feat._pending is not None
        result = feat.execute("confirm", {})
        assert "Done" in result or "added" in result

    def test_execute_skip(self):
        feat = self._make()
        feat.execute("track", {"title": "The Matrix", "media_type": "movie"})
        result = feat.execute("skip", {})
        assert "I found" in result or "all the results" in result

    def test_execute_cancel(self):
        feat = self._make()
        feat.execute("track", {"title": "The Matrix", "media_type": "movie"})
        result = feat.execute("cancel", {})
        assert "cancelled" in result.lower()

    def test_execute_select(self):
        feat = self._make()
        feat.execute("track", {"title": "batman", "media_type": "any"})
        assert feat._pending is not None
        result = feat.execute("select", {"index": 2})
        assert "I found" in result or "Should I add" in result or "already" in result

    def test_execute_select_out_of_range(self):
        feat = self._make()
        feat.execute("track", {"title": "batman", "media_type": "any"})
        result = feat.execute("select", {"index": 99})
        assert "between 1 and" in result

    def test_get_llm_context_no_pending(self):
        feat = self._make()
        assert feat.get_llm_context() is None

    def test_get_llm_context_with_pending(self):
        feat = self._make()
        feat.execute("track", {"title": "batman", "media_type": "any"})
        context = feat.get_llm_context()
        assert context is not None
        assert "batman" in context.lower()
        assert "disambiguation" in context.lower()

    def test_execute_refine_year(self):
        feat = self._make()
        feat.execute("track", {"title": "batman", "media_type": "any"})
        # Force into refining phase for this test
        if feat._pending and feat._pending["phase"] == "confirming":
            feat._pending["phase"] = "refining"
        result = feat.execute("refine_year", {"year": 2022})
        assert "Batman" in result or "results" in result

    def test_execute_refine_type(self):
        feat = self._make()
        feat.execute("track", {"title": "batman", "media_type": "any"})
        if feat._pending and feat._pending["phase"] == "confirming":
            feat._pending["phase"] = "refining"
        result = feat.execute("refine_type", {"media_type": "show"})
        assert result  # Should return something meaningful


# -- Solar execute() --


class TestSolarExecute:

    def _make(self):
        from features.solar import SolarFeature
        storage = MagicMock()
        storage.get_latest.return_value = {
            "production_w": 5000,
            "consumption_w": 3000,
            "net_w": 2000,
        }
        llm = MagicMock()
        llm.respond.return_value = "Solar analysis."
        return SolarFeature({}, storage=storage, llm=llm)

    def test_action_schema(self):
        feat = self._make()
        schema = feat.action_schema
        assert "query" in schema

    def test_execute_query(self):
        feat = self._make()
        result = feat.execute("query", {"question": "how much solar am I producing"})
        assert "kilowatts" in result or "producing" in result


# -- Repeat execute() --


class TestRepeatExecute:

    def test_action_schema(self):
        from features.repeat import RepeatFeature
        feat = RepeatFeature({})
        schema = feat.action_schema
        assert "replay" in schema

    def test_execute_replay_no_history(self):
        from features.repeat import RepeatFeature
        feat = RepeatFeature({})
        result = feat.execute("replay", {})
        assert "haven't said" in result

    def test_execute_replay_with_history(self):
        from features.repeat import RepeatFeature
        feat = RepeatFeature({})
        feat.record("hello", "hi there")
        result = feat.execute("replay", {})
        assert "hi there" in result


# -- Capabilities execute() --


class TestCapabilitiesExecute:

    def _make(self):
        from features.capabilities import CapabilitiesFeature
        mock_feat = MagicMock()
        mock_feat.name = "Test Feature"
        mock_feat.short_description = "A test feature"
        mock_feat.description = "Detailed description of test feature"
        return CapabilitiesFeature({}, features=[mock_feat])

    def test_action_schema(self):
        feat = self._make()
        schema = feat.action_schema
        assert "list" in schema
        assert "describe" in schema

    def test_execute_list(self):
        feat = self._make()
        result = feat.execute("list", {})
        assert "Test Feature" in result

    def test_execute_describe(self):
        feat = self._make()
        result = feat.execute("describe", {"feature": "Test Feature"})
        assert "Detailed description" in result

    def test_execute_describe_not_found(self):
        feat = self._make()
        result = feat.execute("describe", {"feature": "nonexistent"})
        # Falls back to list_all
        assert "Test Feature" in result
