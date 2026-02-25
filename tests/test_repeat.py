"""Tests for the RepeatFeature."""

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from features.repeat import RepeatFeature


def _make_feature():
    return RepeatFeature({})


# -- matches() --


def test_matches_what_did_you_say():
    f = _make_feature()
    assert f.matches("what did you say")


def test_matches_what_did_you_just_say():
    f = _make_feature()
    assert f.matches("what did you just say")


def test_matches_what_was_that():
    f = _make_feature()
    assert f.matches("what was that")


def test_matches_repeat_that():
    f = _make_feature()
    assert f.matches("repeat that")


def test_matches_say_that_again():
    f = _make_feature()
    assert f.matches("say that again")


def test_matches_say_it_again():
    f = _make_feature()
    assert f.matches("say it again")


def test_matches_come_again():
    f = _make_feature()
    assert f.matches("come again")


def test_matches_can_you_repeat_that():
    f = _make_feature()
    assert f.matches("can you repeat that")


def test_matches_what_did_you_tell_me():
    f = _make_feature()
    assert f.matches("what did you tell me")


def test_matches_i_didnt_catch_that():
    f = _make_feature()
    assert f.matches("I didn't catch that")


def test_matches_i_didnt_hear_that():
    f = _make_feature()
    assert f.matches("i didn't hear that")


def test_matches_pardon():
    f = _make_feature()
    assert f.matches("pardon")


def test_matches_case_insensitive():
    f = _make_feature()
    assert f.matches("WHAT DID YOU SAY")
    assert f.matches("Repeat That")


def test_matches_embedded_in_sentence():
    f = _make_feature()
    assert f.matches("sorry what did you say just now")
    assert f.matches("hey can you repeat that please")


# -- matches() negatives --


def test_no_match_unrelated():
    f = _make_feature()
    assert not f.matches("add milk to the grocery list")
    assert not f.matches("what time is it")
    assert not f.matches("hello")


def test_no_match_partial():
    f = _make_feature()
    assert not f.matches("repeat")
    assert not f.matches("say again")


# -- handle() --


def test_handle_no_history():
    f = _make_feature()
    assert f.handle("what did you say") == "I haven't said anything yet this session."


def test_record_then_handle():
    f = _make_feature()
    f.record("what time is it", "It is 3pm.")
    result = f.handle("what did you say")
    assert "what time is it" in result
    assert "It is 3pm." in result


def test_record_overwrites_previous():
    f = _make_feature()
    f.record("first question", "first answer")
    f.record("second question", "second answer")
    result = f.handle("what did you say")
    assert "second question" in result
    assert "second answer" in result
    assert "first" not in result


def test_record_skips_repeat_trigger():
    f = _make_feature()
    f.record("what time is it", "It is 3pm.")
    f.record("what did you say", "I heard: what time is it. And I responded: It is 3pm.")
    # Should still return the original, not the meta-response
    result = f.handle("repeat that")
    assert "what time is it" in result
    assert "It is 3pm." in result


def test_record_captures_reminder():
    f = _make_feature()
    f.record("(reminder)", "Reminder: Take out the trash.")
    result = f.handle("what did you say")
    assert "reminder fired" in result.lower()
    assert "Take out the trash" in result


# -- thread safety --


def test_thread_safety():
    f = _make_feature()
    errors = []

    def writer():
        for i in range(100):
            f.record(f"q{i}", f"r{i}")

    def reader():
        for _ in range(100):
            try:
                f.handle("what did you say")
            except Exception as e:
                errors.append(e)

    threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
