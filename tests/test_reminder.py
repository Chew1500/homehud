"""Tests for the reminder feature."""

import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from features.reminder import ReminderFeature, _normalize


def _make_feature(tmp_path, on_due=None, check_interval=15):
    """Create a ReminderFeature with a temp JSON file."""
    reminder_file = tmp_path / "reminders.json"
    config = {
        "reminder_file": str(reminder_file),
        "reminder_check_interval": check_interval,
    }
    return ReminderFeature(config, on_due=on_due), reminder_file


# -- matches() --


def test_matches_remind_me_to(tmp_path):
    feat, _ = _make_feature(tmp_path)
    assert feat.matches("remind me to take out the trash in 10 minutes")


def test_matches_prefix_form(tmp_path):
    feat, _ = _make_feature(tmp_path)
    assert feat.matches("at 3pm remind me to call mom")


def test_matches_list(tmp_path):
    feat, _ = _make_feature(tmp_path)
    assert feat.matches("what are my reminders")


def test_matches_cancel(tmp_path):
    feat, _ = _make_feature(tmp_path)
    assert feat.matches("cancel my reminder to call mom")


def test_no_match_unrelated(tmp_path):
    feat, _ = _make_feature(tmp_path)
    assert not feat.matches("what time is it")


def test_no_match_partial(tmp_path):
    feat, _ = _make_feature(tmp_path)
    assert not feat.matches("remember to buy milk")


# -- set (relative) --


def test_set_relative_minutes(tmp_path):
    feat, rf = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        result = feat.handle("remind me to take out the trash in 10 minutes")
    assert "I'll remind you to take out the trash" in result
    assert "10 minutes" in result
    items = json.loads(rf.read_text())
    assert len(items) == 1
    assert items[0]["text"] == "take out the trash"
    due = datetime.fromisoformat(items[0]["due"])
    assert due == datetime(2026, 2, 24, 14, 10, 0)


def test_set_relative_hours(tmp_path):
    feat, rf = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        result = feat.handle("remind me to stretch in 2 hours")
    assert "I'll remind you to stretch" in result
    items = json.loads(rf.read_text())
    due = datetime.fromisoformat(items[0]["due"])
    assert due == datetime(2026, 2, 24, 16, 0, 0)


def test_set_relative_seconds(tmp_path):
    feat, rf = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        feat.handle("remind me to check the oven in 30 seconds")
    items = json.loads(rf.read_text())
    due = datetime.fromisoformat(items[0]["due"])
    assert due == datetime(2026, 2, 24, 14, 0, 30)


def test_set_relative_days(tmp_path):
    feat, rf = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        feat.handle("remind me to pay rent in 3 days")
    items = json.loads(rf.read_text())
    due = datetime.fromisoformat(items[0]["due"])
    assert due == datetime(2026, 2, 27, 14, 0, 0)


def test_set_relative_singular(tmp_path):
    feat, rf = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        feat.handle("remind me to take a break in 1 minute")
    items = json.loads(rf.read_text())
    due = datetime.fromisoformat(items[0]["due"])
    assert due == datetime(2026, 2, 24, 14, 1, 0)


def test_set_relative_an_hour(tmp_path):
    feat, rf = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        feat.handle("remind me to call back in an hour")
    items = json.loads(rf.read_text())
    due = datetime.fromisoformat(items[0]["due"])
    assert due == datetime(2026, 2, 24, 15, 0, 0)


def test_set_relative_half_an_hour(tmp_path):
    feat, rf = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        feat.handle("remind me to check laundry in half an hour")
    items = json.loads(rf.read_text())
    due = datetime.fromisoformat(items[0]["due"])
    assert due == datetime(2026, 2, 24, 14, 30, 0)


def test_set_relative_time_first(tmp_path):
    """'remind me in 10 minutes to X' (time before task)."""
    feat, rf = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        result = feat.handle("remind me in 10 minutes to take out the trash")
    assert "take out the trash" in result
    items = json.loads(rf.read_text())
    due = datetime.fromisoformat(items[0]["due"])
    assert due == datetime(2026, 2, 24, 14, 10, 0)


# -- set (absolute) --


def test_set_at_time_today(tmp_path):
    feat, rf = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        result = feat.handle("remind me to call mom at 3pm")
    assert "I'll remind you to call mom" in result
    items = json.loads(rf.read_text())
    due = datetime.fromisoformat(items[0]["due"])
    assert due == datetime(2026, 2, 24, 15, 0, 0)


def test_set_at_time_auto_bumps_when_past(tmp_path):
    """If the time is past today, bump to tomorrow."""
    feat, rf = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 16, 0, 0)  # 4pm
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        feat.handle("remind me to call mom at 3pm")
    items = json.loads(rf.read_text())
    due = datetime.fromisoformat(items[0]["due"])
    assert due.date() == datetime(2026, 2, 25).date()  # tomorrow
    assert due.hour == 15


def test_set_at_time_tomorrow(tmp_path):
    feat, rf = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        result = feat.handle("remind me to call mom at 3pm tomorrow")
    assert "tomorrow" in result
    items = json.loads(rf.read_text())
    due = datetime.fromisoformat(items[0]["due"])
    assert due == datetime(2026, 2, 25, 15, 0, 0)


def test_set_at_time_with_colon(tmp_path):
    feat, rf = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        feat.handle("remind me to call mom at 3:30pm")
    items = json.loads(rf.read_text())
    due = datetime.fromisoformat(items[0]["due"])
    assert due == datetime(2026, 2, 24, 15, 30, 0)


def test_set_prefix_at_form(tmp_path):
    """'at 3pm remind me to X' prefix form."""
    feat, rf = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        result = feat.handle("at 3pm remind me to call mom")
    assert "call mom" in result
    items = json.loads(rf.read_text())
    due = datetime.fromisoformat(items[0]["due"])
    assert due == datetime(2026, 2, 24, 15, 0, 0)


def test_set_tomorrow_no_time(tmp_path):
    """'remind me to X tomorrow' defaults to 9am."""
    feat, rf = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        feat.handle("remind me to take vitamins tomorrow")
    items = json.loads(rf.read_text())
    due = datetime.fromisoformat(items[0]["due"])
    assert due == datetime(2026, 2, 25, 9, 0, 0)


def test_set_no_ampm_infers_pm_for_low_hours(tmp_path):
    """'at 3' with no AM/PM should infer PM for hours 1-6."""
    feat, rf = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 10, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        feat.handle("remind me to call mom at 3")
    items = json.loads(rf.read_text())
    due = datetime.fromisoformat(items[0]["due"])
    assert due.hour == 15  # 3 PM


# -- persistence --


def test_persistence_across_instances(tmp_path):
    """Reminders persist across feature instances."""
    feat1, rf = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        feat1.handle("remind me to stretch in 10 minutes")

    config = {"reminder_file": str(rf), "reminder_check_interval": 15}
    feat2 = ReminderFeature(config)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        result = feat2.handle("what are my reminders")
    assert "stretch" in result


def test_missing_file(tmp_path):
    """Listing with no file should report empty."""
    feat, _ = _make_feature(tmp_path)
    result = feat.handle("what are my reminders")
    assert "don't have any" in result


def test_corrupted_json(tmp_path):
    """Corrupted JSON should be treated as empty."""
    feat, rf = _make_feature(tmp_path)
    rf.parent.mkdir(parents=True, exist_ok=True)
    rf.write_text("not valid json{{{")
    result = feat.handle("what are my reminders")
    assert "don't have any" in result


# -- list --


def test_list_empty(tmp_path):
    feat, _ = _make_feature(tmp_path)
    result = feat.handle("what are my reminders")
    assert "don't have any" in result


def test_list_one(tmp_path):
    feat, _ = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        feat.handle("remind me to stretch in 10 minutes")
        result = feat.handle("what are my reminders")
    assert "one reminder" in result
    assert "stretch" in result


def test_list_multiple(tmp_path):
    feat, _ = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        feat.handle("remind me to stretch in 10 minutes")
        feat.handle("remind me to call mom in 2 hours")
        result = feat.handle("what are my reminders")
    assert "2 reminders" in result
    assert "stretch" in result
    assert "call mom" in result


# -- cancel --


def test_cancel_exact_match(tmp_path):
    feat, _ = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        feat.handle("remind me to call mom in 10 minutes")
        result = feat.handle("cancel my reminder to call mom")
    assert "Cancelled" in result
    assert "call mom" in result


def test_cancel_substring_match(tmp_path):
    feat, _ = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        feat.handle("remind me to call mom back about dinner in 10 minutes")
        result = feat.handle("cancel my reminder to call mom")
    assert "Cancelled" in result


def test_cancel_case_insensitive(tmp_path):
    feat, _ = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        feat.handle("remind me to Call Mom in 10 minutes")
        result = feat.handle("cancel my reminder to call mom")
    assert "Cancelled" in result


def test_cancel_nonexistent(tmp_path):
    feat, _ = _make_feature(tmp_path)
    result = feat.handle("cancel my reminder to fly to mars")
    assert "don't see" in result


# -- clear --


def test_clear_all(tmp_path):
    feat, rf = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        feat.handle("remind me to stretch in 10 minutes")
        feat.handle("remind me to call mom in 2 hours")
    result = feat.handle("clear all my reminders")
    assert "cleared" in result
    assert json.loads(rf.read_text()) == []


# -- checker thread --


def test_checker_fires_due_reminder(tmp_path):
    """Checker thread should fire callback for due reminders."""
    fired = []
    feat, rf = _make_feature(tmp_path, on_due=lambda t: fired.append(t),
                             check_interval=0.1)
    try:
        # Write a reminder that's already due
        past = (datetime.now() - timedelta(minutes=1)).replace(microsecond=0)
        items = [{"text": "stretch", "due": past.isoformat(),
                  "created": past.isoformat()}]
        rf.parent.mkdir(parents=True, exist_ok=True)
        rf.write_text(json.dumps(items))

        # Wait for checker to fire
        deadline = time.time() + 3
        while not fired and time.time() < deadline:
            time.sleep(0.05)

        assert "stretch" in fired
        # Reminder should be removed from file
        remaining = json.loads(rf.read_text())
        assert len(remaining) == 0
    finally:
        feat.close()


def test_checker_fires_missed_reminders(tmp_path):
    """Past-due reminders (service was down) should fire immediately."""
    fired = []
    feat, rf = _make_feature(tmp_path, on_due=lambda t: fired.append(t),
                             check_interval=0.1)
    try:
        long_ago = (datetime.now() - timedelta(hours=2)).replace(microsecond=0)
        items = [{"text": "old task", "due": long_ago.isoformat(),
                  "created": long_ago.isoformat()}]
        rf.parent.mkdir(parents=True, exist_ok=True)
        rf.write_text(json.dumps(items))

        deadline = time.time() + 3
        while not fired and time.time() < deadline:
            time.sleep(0.05)

        assert "old task" in fired
    finally:
        feat.close()


def test_close_stops_checker(tmp_path):
    """close() should stop the checker thread."""
    feat, _ = _make_feature(tmp_path, on_due=lambda t: None,
                            check_interval=0.1)
    assert feat._checker_thread is not None
    assert feat._checker_thread.is_alive()
    feat.close()
    assert not feat._checker_thread.is_alive()


# -- fallback --


def test_fallback_lists_reminders(tmp_path):
    """Mentioning 'remind' without matching a pattern falls back to list."""
    feat, _ = _make_feature(tmp_path)
    result = feat.handle("tell me about my reminders")
    assert "don't have any" in result


# -- _normalize() --


def test_normalize_strips_trailing_period():
    assert _normalize("remind me to clean up.") == "remind me to clean up"


def test_normalize_strips_trailing_question_mark():
    assert _normalize("remind me to clean up?") == "remind me to clean up"


def test_normalize_preserves_ampm_dots():
    result = _normalize("remind me at 4 p.m. to clean up.")
    assert "p.m." in result


def test_normalize_strips_can_you():
    assert _normalize("Can you remind me to clean up") == "remind me to clean up"


def test_normalize_strips_could_you_please():
    result = _normalize("Could you please remind me to clean up")
    assert result == "remind me to clean up"


def test_normalize_strips_would_you():
    result = _normalize("Would you remind me to clean up")
    assert result == "remind me to clean up"


def test_normalize_strips_please():
    result = _normalize("Please remind me to clean up")
    assert result == "remind me to clean up"


def test_normalize_rewrites_create_reminder_to():
    result = _normalize("create a reminder to take out the trash")
    assert result == "remind me to take out the trash"


def test_normalize_rewrites_set_reminder_for():
    result = _normalize("set a reminder for 4pm to clean up")
    assert result == "remind me at 4pm to clean up"


def test_normalize_rewrites_create_reminder_for_tomorrow_at():
    result = _normalize("create a reminder for tomorrow at 3pm to call mom")
    assert result == "tomorrow at 3pm remind me to call mom"


def test_normalize_rewrites_set_reminder_for_tomorrow_to():
    result = _normalize("set a reminder for tomorrow to buy milk")
    assert result == "remind me to buy milk tomorrow"


def test_normalize_combined_prefix_and_punctuation():
    result = _normalize("Can you remind me at 4 p.m. to clean up?")
    assert result == "remind me at 4 p.m. to clean up"


# -- _SET_AT_REVERSE pattern (remind me at TIME to TASK) --


def test_set_at_reverse_basic(tmp_path):
    """'remind me at 4pm to clean up' should create a reminder."""
    feat, rf = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        result = feat.handle("remind me at 4pm to clean up")
    assert "I'll remind you to clean up" in result
    items = json.loads(rf.read_text())
    assert len(items) == 1
    due = datetime.fromisoformat(items[0]["due"])
    assert due == datetime(2026, 2, 24, 16, 0, 0)


def test_set_at_reverse_with_ampm_dots(tmp_path):
    """'remind me at 4 p.m. to clean up' should create a reminder."""
    feat, rf = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        result = feat.handle("remind me at 4 p.m. to clean up")
    assert "I'll remind you to clean up" in result
    items = json.loads(rf.read_text())
    due = datetime.fromisoformat(items[0]["due"])
    assert due == datetime(2026, 2, 24, 16, 0, 0)


def test_set_at_reverse_tomorrow(tmp_path):
    """'remind me at 3pm tomorrow to call mom' should set for tomorrow."""
    feat, rf = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        result = feat.handle("remind me at 3pm tomorrow to call mom")
    assert "call mom" in result
    items = json.loads(rf.read_text())
    due = datetime.fromisoformat(items[0]["due"])
    assert due == datetime(2026, 2, 25, 15, 0, 0)


# -- End-to-end: natural voice phrasing --


def test_e2e_can_you_remind_me_at_time(tmp_path):
    """'Can you remind me at 4 p.m. to clean up?' — the original bug report."""
    feat, rf = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        result = feat.handle("Can you remind me at 4 p.m. to clean up?")
    assert "I'll remind you to clean up" in result
    items = json.loads(rf.read_text())
    assert len(items) == 1


def test_e2e_create_reminder_for_time(tmp_path):
    """'Create a reminder for 4 p.m. to clean up.' — the other bug report."""
    feat, rf = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        result = feat.handle("Create a reminder for 4 p.m. to clean up.")
    assert "I'll remind you to clean up" in result
    items = json.loads(rf.read_text())
    assert len(items) == 1


def test_e2e_please_remind_me_relative(tmp_path):
    """'Please remind me in 10 minutes to check the oven.'"""
    feat, rf = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        result = feat.handle("Please remind me in 10 minutes to check the oven.")
    assert "check the oven" in result
    items = json.loads(rf.read_text())
    due = datetime.fromisoformat(items[0]["due"])
    assert due == datetime(2026, 2, 24, 14, 10, 0)


def test_e2e_could_you_set_reminder_tomorrow(tmp_path):
    """'Could you set a reminder for tomorrow at 9am to call the dentist?'"""
    feat, rf = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        result = feat.handle(
            "Could you set a reminder for tomorrow at 9am to call the dentist?"
        )
    assert "call the dentist" in result
    items = json.loads(rf.read_text())
    due = datetime.fromisoformat(items[0]["due"])
    assert due == datetime(2026, 2, 25, 9, 0, 0)


def test_e2e_set_reminder_to_task(tmp_path):
    """'Set a reminder to buy groceries in 2 hours.'"""
    feat, rf = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        result = feat.handle("Set a reminder to buy groceries in 2 hours.")
    assert "buy groceries" in result
    items = json.loads(rf.read_text())
    due = datetime.fromisoformat(items[0]["due"])
    assert due == datetime(2026, 2, 24, 16, 0, 0)


def test_e2e_trailing_punctuation_at_time(tmp_path):
    """Trailing period doesn't break absolute time matching."""
    feat, rf = _make_feature(tmp_path)
    now = datetime(2026, 2, 24, 14, 0, 0)
    with patch("features.reminder.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        result = feat.handle("remind me to call mom at 3pm.")
    assert "call mom" in result
    items = json.loads(rf.read_text())
    assert len(items) == 1
