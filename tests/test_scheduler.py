"""Tests for the shared wall-clock scheduler."""

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.scheduler import Scheduler


def test_fires_near_due_time():
    sched = Scheduler()
    fired = threading.Event()
    payloads = []
    try:
        def on_fire(payload):
            payloads.append(payload)
            fired.set()

        sched.add(time.time() + 0.1, {"x": 1}, on_fire)
        assert fired.wait(timeout=1.0)
        assert payloads == [{"x": 1}]
    finally:
        sched.close()


def test_fires_in_due_order():
    sched = Scheduler()
    order = []
    done = threading.Event()
    try:
        def make_cb(label):
            def _cb(_payload):
                order.append(label)
                if len(order) == 3:
                    done.set()
            return _cb

        now = time.time()
        sched.add(now + 0.3, {}, make_cb("c"))
        sched.add(now + 0.1, {}, make_cb("a"))
        sched.add(now + 0.2, {}, make_cb("b"))
        assert done.wait(timeout=2.0)
        assert order == ["a", "b", "c"]
    finally:
        sched.close()


def test_past_due_fires_immediately():
    sched = Scheduler()
    fired = threading.Event()
    try:
        sched.add(time.time() - 5, {}, lambda _: fired.set())
        assert fired.wait(timeout=0.5)
    finally:
        sched.close()


def test_cancel_prevents_fire():
    sched = Scheduler()
    fired = []
    try:
        entry_id = sched.add(time.time() + 0.2, {}, lambda p: fired.append(p))
        assert sched.cancel(entry_id) is True
        # Wait past the original due time
        time.sleep(0.4)
        assert fired == []
        # Cancelling again returns False
        assert sched.cancel(entry_id) is False
    finally:
        sched.close()


def test_cancel_wakes_loop():
    """Cancelling the earliest entry should let a later one re-establish
    its own sleep horizon without the loop sleeping until the cancelled time."""
    sched = Scheduler()
    later_fired = threading.Event()
    try:
        far = sched.add(time.time() + 10.0, {}, lambda _: None)
        sched.add(time.time() + 0.1, {}, lambda _: later_fired.set())
        sched.cancel(far)
        assert later_fired.wait(timeout=1.0)
    finally:
        sched.close()


def test_list_snapshot():
    sched = Scheduler()
    try:
        now = time.time()
        e1 = sched.add(now + 60, {"n": 1}, lambda _: None)
        e2 = sched.add(now + 30, {"n": 2}, lambda _: None)
        entries = sched.list()
        assert [e["id"] for e in entries] == [e2, e1]
        assert [e["payload"]["n"] for e in entries] == [2, 1]
    finally:
        sched.close()


def test_close_joins_thread():
    sched = Scheduler()
    t = sched._thread
    assert t.is_alive()
    sched.close()
    t.join(timeout=5)
    assert not t.is_alive()


def test_callback_exception_does_not_kill_loop():
    sched = Scheduler()
    second_fired = threading.Event()
    try:
        def bad(_):
            raise RuntimeError("boom")

        sched.add(time.time() + 0.05, {}, bad)
        sched.add(time.time() + 0.15, {}, lambda _: second_fired.set())
        assert second_fired.wait(timeout=1.0)
    finally:
        sched.close()
