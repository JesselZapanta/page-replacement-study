"""Shared helpers for the experiment scripts."""

from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
