"""Tests for the Timer feature."""

import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from features.timer.feature import TimerFeature, parse_duration
from utils.scheduler import Scheduler

# -- parse_duration --

def test_parse_duration_minutes():
    assert parse_duration("5 minutes") == 300
    assert parse_duration("5 min") == 300


def test_parse_duration_seconds():
    assert parse_duration("30 seconds") == 30


def test_parse_duration_hours():
    assert parse_duration("2 hours") == 7200


def test_parse_duration_words():
    assert parse_duration("five minutes") == 300
    assert parse_duration("seven minutes") == 420
    assert parse_duration("fifteen minutes") == 900


def test_parse_duration_combined():
    assert parse_duration("1 hour 30 minutes") == 5400
    assert parse_duration("1 minute and 30 seconds") == 90


def test_parse_duration_empty():
    assert parse_duration("") is None
    assert parse_duration("no duration here") is None


# -- Feature behavior --

def _make(tmp_path, on_fire=None, scheduler=None):
    return TimerFeature(
        {"timer_file": str(tmp_path / "timers.json")},
        scheduler=scheduler,
        on_fire=on_fire,
    )


def test_start_persists_to_disk(tmp_path):
    t = _make(tmp_path)
    try:
        result = t.execute("start", {"duration": "5 minutes"})
        assert "5 minutes" in result
        stored = json.loads((tmp_path / "timers.json").read_text())
        assert len(stored) == 1
        assert stored[0]["duration_sec"] == 300
    finally:
        t.close()


def test_start_with_label(tmp_path):
    t = _make(tmp_path)
    try:
        result = t.execute("start", {"duration": "10 minutes", "label": "pasta"})
        assert "pasta" in result
        stored = json.loads((tmp_path / "timers.json").read_text())
        assert stored[0]["label"] == "pasta"
    finally:
        t.close()


def test_start_bad_duration(tmp_path):
    t = _make(tmp_path)
    try:
        result = t.execute("start", {"duration": ""})
        assert "didn" in result.lower()  # "I didn't catch..."
    finally:
        t.close()


def test_list_empty(tmp_path):
    t = _make(tmp_path)
    try:
        assert "don't have" in t.execute("list", {}).lower()
    finally:
        t.close()


def test_list_multiple(tmp_path):
    t = _make(tmp_path)
    try:
        t.execute("start", {"duration": "5 minutes", "label": "pasta"})
        t.execute("start", {"duration": "10 minutes", "label": "bread"})
        result = t.execute("list", {})
        assert "pasta" in result and "bread" in result
    finally:
        t.close()


def test_cancel_by_label(tmp_path):
    t = _make(tmp_path)
    try:
        t.execute("start", {"duration": "5 minutes", "label": "pasta"})
        t.execute("start", {"duration": "10 minutes", "label": "bread"})
        t.execute("cancel", {"label": "pasta"})
        stored = json.loads((tmp_path / "timers.json").read_text())
        assert len(stored) == 1
        assert stored[0]["label"] == "bread"
    finally:
        t.close()


def test_cancel_all_when_no_label(tmp_path):
    t = _make(tmp_path)
    try:
        t.execute("start", {"duration": "5 minutes"})
        t.execute("start", {"duration": "10 minutes"})
        t.execute("cancel", {})
        stored = json.loads((tmp_path / "timers.json").read_text())
        assert stored == []
    finally:
        t.close()


def test_extend_single(tmp_path):
    t = _make(tmp_path)
    try:
        t.execute("start", {"duration": "5 minutes"})
        result = t.execute("extend", {"duration": "2 minutes"})
        assert "2 minutes" in result
        stored = json.loads((tmp_path / "timers.json").read_text())
        assert stored[0]["duration_sec"] == 420  # 5 + 2 minutes
    finally:
        t.close()


def test_fire_calls_callback(tmp_path):
    sched = Scheduler()
    fired = threading.Event()
    heard = []

    def on_fire(item):
        heard.append(item)
        fired.set()

    t = TimerFeature(
        {"timer_file": str(tmp_path / "timers.json")},
        scheduler=sched, on_fire=on_fire,
    )
    try:
        # Short "2 second" timer — parse_duration requires a unit phrase.
        t.execute("start", {"duration": "2 seconds", "label": "quick"})
        assert fired.wait(timeout=4.0)
        assert heard[0]["label"] == "quick"
        # Storage cleaned up.
        stored = json.loads((tmp_path / "timers.json").read_text())
        assert stored == []
    finally:
        t.close()
        sched.close()


def test_overdue_timer_fires_on_startup(tmp_path):
    """If the service restarts, any already-past timers fire immediately."""
    timer_file = tmp_path / "timers.json"
    items = [{
        "id": "abc123",
        "label": "old",
        "duration_sec": 10,
        "started_at": int(time.time() - 100),
        "due_at": int(time.time() - 5),
    }]
    timer_file.parent.mkdir(parents=True, exist_ok=True)
    timer_file.write_text(json.dumps(items))

    sched = Scheduler()
    fired = threading.Event()
    t = TimerFeature(
        {"timer_file": str(timer_file)},
        scheduler=sched, on_fire=lambda item: fired.set(),
    )
    try:
        assert fired.wait(timeout=2.0)
    finally:
        t.close()
        sched.close()


def test_close_scheduler_when_owned(tmp_path):
    t = _make(tmp_path, on_fire=lambda i: None)
    thread = t._scheduler._thread
    assert thread.is_alive()
    t.close()
    thread.join(timeout=5)
    assert not thread.is_alive()
