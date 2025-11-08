"""Helpers for working with guild-configured timezones and flexible date parsing."""
from __future__ import annotations

import datetime as dt
from typing import Optional, Tuple

import dateparser
import pytz

from utils.config import DEFAULT_EVENT_TIME, DEFAULT_TIMEZONE

_TIMEZONE_LOOKUP = {name.lower(): name for name in pytz.all_timezones}


def canonicalize_timezone(tz_name: Optional[str]) -> Optional[str]:
    """Return the canonical IANA timezone for the provided name, if known."""
    if not tz_name:
        return DEFAULT_TIMEZONE

    cleaned = tz_name.strip().replace(" ", "_")
    return _TIMEZONE_LOOKUP.get(cleaned.lower())


def is_valid_timezone(tz_name: Optional[str]) -> bool:
    """True when the supplied timezone string resolves to a known IANA entry."""
    return canonicalize_timezone(tz_name) is not None


def get_timezone(tz_name: Optional[str]):
    """Return a pytz timezone object, falling back to the default when necessary."""
    canonical = canonicalize_timezone(tz_name) or DEFAULT_TIMEZONE
    return pytz.timezone(canonical)


def _default_time_parts(default_time: str = DEFAULT_EVENT_TIME) -> Tuple[int, int]:
    """Parse the configured default time string into hour/minute parts."""
    try:
        parsed = dt.datetime.strptime(default_time, "%H:%M")
        return parsed.hour, parsed.minute
    except ValueError:
        # Fall back to 20:00 (8 PM) if the string becomes invalid.
        return 20, 0


def parse_event_datetime(
    date_input: Optional[str],
    time_input: Optional[str],
    timezone_name: Optional[str],
) -> Tuple[Optional[dt.datetime], Optional[str]]:
    """
    Parse the supplied date/time strings using dateparser in the given timezone.

    Returns a tuple of (datetime, error_message). When parsing fails, datetime is None
    and error_message contains a user-friendly explanation. When both inputs are empty,
    the function returns (None, None) to signal that scheduling should proceed without
    a fixed timestamp.
    """
    date_input = (date_input or "").strip()
    time_input = (time_input or "").strip()

    if not date_input and not time_input:
        return None, None

    tz = get_timezone(timezone_name)
    text = " ".join(part for part in (date_input, time_input) if part).strip()

    settings = {
        "TIMEZONE": tz.zone,
        "RETURN_AS_TIMEZONE_AWARE": True,
        "PREFER_DATES_FROM": "future",
    }

    parsed = dateparser.parse(text, settings=settings)
    if not parsed:
        return (
            None,
            "Could not understand that date/time. Try formats like "
            "'2025-06-15 20:00', 'next Saturday 8pm', or 'tomorrow at noon'.",
        )

    parsed = parsed.astimezone(tz)

    # When the user only provided a date, honor the configured default time
    # as long as dateparser didn't detect an explicit time.
    if not time_input:
        default_hour, default_minute = _default_time_parts()

        if (
            parsed.hour == 0
            and parsed.minute == 0
            and parsed.second == 0
            and parsed.microsecond == 0
        ):
            parsed = parsed.replace(
                hour=default_hour,
                minute=default_minute,
                second=0,
                microsecond=0,
            )

    return parsed, None


__all__ = [
    "canonicalize_timezone",
    "get_timezone",
    "is_valid_timezone",
    "parse_event_datetime",
]
