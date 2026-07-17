"""Port of src/truesignal/provenance/stamp.test.ts."""
from datetime import datetime, timezone

import pytest

from truesignal.provenance.cache import read_cache
from truesignal.provenance.stamp import fetch_with_fallback, stamp_fallback, stamp_live
from truesignal.types import FeedItem, UnstampedItem

UNSTAMPED = UnstampedItem(
    id="gdelt:https://example.com/a",
    source="gdelt",
    title="Example article",
    url="https://example.com/a",
    timestamp="2026-07-01T00:00:00.000Z",
)


def test_stamp_live_marks_every_item_status_live_and_preserves_real_upstream_fields():
    [result] = stamp_live([UNSTAMPED])
    assert result.status == "live"
    assert result.id == UNSTAMPED.id
    assert result.url == UNSTAMPED.url
    assert result.timestamp == UNSTAMPED.timestamp


def test_stamp_live_never_adds_a_fallback_age_seconds_field_to_a_live_item():
    [result] = stamp_live([UNSTAMPED])
    assert result.fallback_age_seconds is None


def test_stamp_fallback_computes_a_real_non_negative_age_in_seconds_from_fetched_at_to_now():
    fetched_at = "2026-07-01T00:00:00.000Z"
    now = datetime(2026, 7, 1, 0, 10, 0, tzinfo=timezone.utc)
    live = FeedItem(**{**UNSTAMPED.__dict__, "status": "live"})

    [result] = stamp_fallback([live], fetched_at, now)
    assert result.status == "fallback"
    assert result.fallback_age_seconds == 600


def test_stamp_fallback_preserves_the_original_event_timestamp_never_rewrites_it_to_now():
    fetched_at = "2026-07-01T00:00:00.000Z"
    now = datetime(2026, 7, 5, tzinfo=timezone.utc)
    live = FeedItem(
        **{**UNSTAMPED.__dict__, "status": "live", "timestamp": "2026-06-15T12:00:00.000Z"}
    )

    [result] = stamp_fallback([live], fetched_at, now)
    assert result.timestamp == "2026-06-15T12:00:00.000Z"


def test_stamp_fallback_clamps_age_to_zero_rather_than_going_negative_under_clock_skew():
    fetched_at = "2026-07-01T00:10:00.000Z"
    now = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)  # "now" before fetched_at
    live = FeedItem(**{**UNSTAMPED.__dict__, "status": "live"})

    [result] = stamp_fallback([live], fetched_at, now)
    assert result.fallback_age_seconds == 0


def test_fetch_with_fallback_returns_live_items_and_caches_them_on_a_successful_fetch(cache_dir):
    items = fetch_with_fallback("gdelt", lambda: [UNSTAMPED])

    assert items == [FeedItem(**{**UNSTAMPED.__dict__, "status": "live"})]
    cached = read_cache("gdelt")
    assert cached.items == [FeedItem(**{**UNSTAMPED.__dict__, "status": "live"})]


def test_fetch_with_fallback_falls_back_to_the_real_cache_stamped_fallback_on_failure(cache_dir):
    fetch_with_fallback("gdelt", lambda: [UNSTAMPED])  # seed a real cache entry

    def failing_fetch():
        raise RuntimeError("upstream unreachable")

    items = fetch_with_fallback("gdelt", failing_fetch)

    assert len(items) == 1
    assert items[0].status == "fallback"
    assert items[0].url == UNSTAMPED.url
    assert isinstance(items[0].fallback_age_seconds, int)
    assert items[0].fallback_age_seconds >= 0


def test_fetch_with_fallback_returns_empty_never_fabricated_when_fetch_fails_and_no_cache(cache_dir):
    def failing_fetch():
        raise RuntimeError("upstream unreachable")

    assert fetch_with_fallback("gdelt", failing_fetch) == []


def test_fetch_with_fallback_still_returns_live_data_when_the_local_cache_write_fails(cache_dir, tmp_path, monkeypatch):
    # Force write_cache's mkdir(parents=True) to fail regardless of the OS user's privileges (a
    # chmod-based permission test is unreliable when tests run as root, e.g. in a container, since
    # root bypasses filesystem permission checks): make a path segment of the cache directory a
    # regular file instead of a directory.
    blocker_path = tmp_path / "blocked-by-a-file"
    blocker_path.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("TRUESIGNAL_CACHE_DIR", str(blocker_path / "cache"))

    items = fetch_with_fallback("gdelt", lambda: [UNSTAMPED])

    # The upstream fetch genuinely succeeded -- a local disk error persisting it to cache must
    # never downgrade real live data into a mislabeled fallback, or silently drop it.
    assert items == [FeedItem(**{**UNSTAMPED.__dict__, "status": "live"})]
