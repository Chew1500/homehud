"""Deploy detection via git commit comparison."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger("home-hud.version")

# Store the last-seen commit in data/ (already gitignored)
_LAST_COMMIT_FILE = Path(__file__).parent.parent.parent / "data" / ".last_commit"


def get_current_commit() -> str | None:
    """Return the short git commit hash, or None if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        log.debug("Could not determine git commit", exc_info=True)
    return None


def is_new_deploy() -> bool:
    """Check if the current commit differs from the last recorded one.

    Returns False on first-ever run (no file yet) and False if commit unchanged.
    Returns True only when the commit differs from the stored one.
    Always writes the current commit to the tracking file.
    """
    current = get_current_commit()
    if current is None:
        return False

    previous = None
    try:
        if _LAST_COMMIT_FILE.exists():
            previous = _LAST_COMMIT_FILE.read_text().strip()
    except Exception:
        log.debug("Could not read last commit file", exc_info=True)

    # Write current commit
    try:
        _LAST_COMMIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LAST_COMMIT_FILE.write_text(current)
    except Exception:
        log.warning("Could not write last commit file", exc_info=True)

    # First run (no previous file) → not a deploy
    if previous is None:
        return False

    return current != previous
