"""
File-based cache for the last successful live fetch per connector.

This is what makes a real "fallback" item possible: when a source is unreachable, a connector
serves the last genuinely-fetched-live data it has on disk, stamped with its real age -- never
invented data. If nothing has ever been fetched successfully, there is nothing to fall back to,
and the connector must return an empty list instead.

Direct port of src/truesignal/provenance/cache.ts.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .._util import format_iso8601
from ..types import FeedItem

CACHE_DIR_ENV_VAR = "TRUESIGNAL_CACHE_DIR"


@dataclass(frozen=True)
class CacheEntry:
    #: Real ISO-8601 timestamp of when this cache entry was written, i.e. the last live fetch.
    fetched_at: str
    #: The real live items captured at that fetch.
    items: List[FeedItem]


def get_cache_dir() -> Path:
    """
    Resolves the cache directory. Overridable via TRUESIGNAL_CACHE_DIR (used by tests, and by
    anyone who wants cache state outside their home directory) -- defaults to
    ~/.truesignal/cache.
    """
    override = os.environ.get(CACHE_DIR_ENV_VAR)
    if override:
        return Path(override)
    return Path.home() / ".truesignal" / "cache"


def _cache_file_path(source: str) -> Path:
    return get_cache_dir() / f"{source}.json"


def write_cache(source: str, items: List[FeedItem]) -> None:
    """Persists the given items as the latest known-live snapshot for `source`."""
    directory = get_cache_dir()
    directory.mkdir(parents=True, exist_ok=True)
    entry = {
        "fetchedAt": format_iso8601(datetime.now(timezone.utc)),
        "items": [item.to_dict() for item in items],
    }
    _cache_file_path(source).write_text(json.dumps(entry, indent=2), encoding="utf-8")


def read_cache(source: str) -> Optional[CacheEntry]:
    """
    Reads the last cached snapshot for `source`. Returns None if no cache exists yet, or if the
    cache file is missing/corrupt -- a connector must treat "cannot prove what was cached" the
    same as "nothing cached" rather than guessing at its contents.
    """
    try:
        raw = _cache_file_path(source).read_text(encoding="utf-8")
        parsed = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(parsed, dict):
        return None
    fetched_at = parsed.get("fetchedAt")
    raw_items = parsed.get("items")
    if not isinstance(fetched_at, str) or not isinstance(raw_items, list):
        return None

    try:
        items = [
            FeedItem(
                id=item["id"],
                source=item["source"],
                title=item["title"],
                url=item["url"],
                timestamp=item["timestamp"],
                status=item["status"],
                fallback_age_seconds=item.get("fallback_age_seconds"),
                summary=item.get("summary"),
            )
            for item in raw_items
        ]
    except (KeyError, TypeError):
        return None

    return CacheEntry(fetched_at=fetched_at, items=items)
