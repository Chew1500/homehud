"""Timer feature: short-duration kitchen/exercise countdowns with alarm tone.

Distinct from Reminder (which handles dated tasks and speaks a TTS message):
timers live in seconds-to-hours, fire an audible alarm instead of TTS, and
have a different affordance ("set a timer for 7 minutes" vs. "remind me at
9am to call mom").
"""

from features.timer.feature import TimerFeature

__all__ = ["TimerFeature"]
