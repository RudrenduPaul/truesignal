"""
The provenance-stamping layer -- the single most important module in this codebase.

Every connector calls ``fetch_with_fallback`` instead of hitting the network directly. It
enforces the product's core guarantee in code, not just in documentation:

    1. A successful upstream fetch is stamped "live" and cached for future fallback use.
    2. A failed upstream fetch falls back to the last real cached snapshot, stamped "fallback"
       with an accurate age -- never silently presented as current.
    3. If there is no cache to fall back to, the connector returns nothing. It never invents,
       randomizes, or relabels stale data as live.

Direct port of src/truesignal/provenance/stamp.ts.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, List, Optional, Sequence

from .._util import parse_iso8601
from ..types import FeedItem, UnstampedItem
from .cache import read_cache, write_cache


def stamp_live(items: Sequence[UnstampedItem]) -> List[FeedItem]:
    """Stamps raw upstream items as live and returns them, provenance-complete."""
    return [
        FeedItem(
            id=item.id,
            source=item.source,
            title=item.title,
            url=item.url,
            timestamp=item.timestamp,
            status="live",
            summary=item.summary,
        )
        for item in items
    ]


def stamp_fallback(
    items: Sequence[FeedItem],
    fetched_at: str,
    now: Optional[datetime] = None,
) -> List[FeedItem]:
    """
    Stamps cached items as fallback, computing a real age in seconds from when they were cached
    (fetched_at) to now. Age is clamped to a minimum of 0 to guard against clock skew.
    """
    now = now or datetime.now(timezone.utc)
    fetched_at_dt = parse_iso8601(fetched_at)
    age_seconds = max(0, round((now - fetched_at_dt).total_seconds()))
    return [
        FeedItem(
            id=item.id,
            source=item.source,
            title=item.title,
            url=item.url,
            timestamp=item.timestamp,
            status="fallback",
            fallback_age_seconds=age_seconds,
            summary=item.summary,
        )
        for item in items
    ]


def fetch_with_fallback(
    source: str,
    fetch_live: Callable[[], List[UnstampedItem]],
) -> List[FeedItem]:
    """
    Runs `fetch_live` against the real upstream source. On success, stamps and caches the result.
    On failure, falls back to the last real cache entry for `source`, or returns an empty list if
    none exists. This function is what every connector's failure path is tested against -- see
    test_no_fabrication.py.

    A local cache-write failure (disk full, read-only filesystem, permissions) is deliberately
    kept out of the fallback path below: it has nothing to do with whether the upstream fetch
    succeeded, and treating it the same as a network failure would mislabel data that was
    genuinely just fetched live as a stale fallback -- the opposite of an honest provenance stamp.
    """
    try:
        raw = fetch_live()
    except Exception:
        cached = read_cache(source)
        if not cached or len(cached.items) == 0:
            return []
        return stamp_fallback(cached.items, cached.fetched_at)

    live = stamp_live(raw)
    try:
        write_cache(source, live)
    except OSError:
        # The fetch genuinely succeeded; a failure to persist it for future fallback use must not
        # turn this real live data into a mislabeled fallback or drop it.
        pass
    return live
