"""Tests for deploy detection."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import utils.version as version_mod
from utils.version import is_new_deploy


def test_first_run_returns_false(tmp_path):
    """First run (no file exists) should return False."""
    commit_file = tmp_path / ".last_commit"
    with (
        patch.object(version_mod, "_LAST_COMMIT_FILE", commit_file),
        patch.object(version_mod, "get_current_commit", return_value="abc1234"),
    ):
        assert is_new_deploy() is False
        assert commit_file.read_text() == "abc1234"


def test_same_commit_returns_false(tmp_path):
    """Same commit as last run should return False."""
    commit_file = tmp_path / ".last_commit"
    commit_file.write_text("abc1234")
    with (
        patch.object(version_mod, "_LAST_COMMIT_FILE", commit_file),
        patch.object(version_mod, "get_current_commit", return_value="abc1234"),
    ):
        assert is_new_deploy() is False


def test_different_commit_returns_true(tmp_path):
    """Different commit from last run should return True."""
    commit_file = tmp_path / ".last_commit"
    commit_file.write_text("abc1234")
    with (
        patch.object(version_mod, "_LAST_COMMIT_FILE", commit_file),
        patch.object(version_mod, "get_current_commit", return_value="def5678"),
    ):
        assert is_new_deploy() is True
        assert commit_file.read_text() == "def5678"


def test_file_gets_updated_on_new_deploy(tmp_path):
    """The commit file should be updated after detecting a new deploy."""
    commit_file = tmp_path / ".last_commit"
    commit_file.write_text("old1234")
    with (
        patch.object(version_mod, "_LAST_COMMIT_FILE", commit_file),
        patch.object(version_mod, "get_current_commit", return_value="new5678"),
    ):
        is_new_deploy()
        assert commit_file.read_text() == "new5678"


def test_no_git_returns_false(tmp_path):
    """When git is unavailable, should return False."""
    commit_file = tmp_path / ".last_commit"
    with (
        patch.object(version_mod, "_LAST_COMMIT_FILE", commit_file),
        patch.object(version_mod, "get_current_commit", return_value=None),
    ):
        assert is_new_deploy() is False
