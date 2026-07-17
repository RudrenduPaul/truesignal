"""Small internal helpers shared across connectors and the provenance layer. Not part of the
public API (hence the leading underscore) -- see truesignal/__init__.py for the public surface."""
from __future__ import annotations

from datetime import datetime, timezone


def format_iso8601(dt: datetime) -> str:
    """
    Formats a datetime as a JavaScript-``Date.prototype.toISOString()``-equivalent string:
    always UTC, always exactly 3 millisecond digits, always a trailing "Z". Naive datetimes are
    assumed to already be UTC (every caller in this codebase constructs them that way).
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    milliseconds = dt.microsecond // 1000
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{milliseconds:03d}Z"


def parse_iso8601(value: str) -> datetime:
    """Parses a real upstream ISO-8601 timestamp (with or without a trailing 'Z') into an aware
    UTC datetime. Raises ValueError on anything that isn't a real, parseable instant."""
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
