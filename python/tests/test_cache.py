"""Port of src/truesignal/provenance/cache.test.ts."""
from datetime import datetime, timezone

from truesignal.provenance.cache import get_cache_dir, read_cache, write_cache
from truesignal.types import FeedItem

SAMPLE_ITEM = FeedItem(
    id="cisa-kev:CVE-2026-00001",
    source="cisa-kev",
    title="Example vulnerability",
    url="https://nvd.nist.gov/vuln/detail/CVE-2026-00001",
    timestamp="2026-07-01T00:00:00.000Z",
    status="live",
)


def test_honors_truesignal_cache_dir(cache_dir):
    assert str(get_cache_dir()) == str(cache_dir)


def test_falls_back_to_home_truesignal_cache_when_unset(monkeypatch):
    monkeypatch.delenv("TRUESIGNAL_CACHE_DIR", raising=False)
    resolved = str(get_cache_dir())
    assert ".truesignal" in resolved
    assert "cache" in resolved


def test_returns_none_when_nothing_has_ever_been_cached(cache_dir):
    assert read_cache("cisa-kev") is None


def test_round_trips_real_items_with_a_real_fetched_at_timestamp(cache_dir):
    # write_cache's fetchedAt is floored to millisecond precision (format_iso8601), while
    # datetime.now() carries microsecond precision -- floor `before` the same way so a write that
    # lands in the same millisecond as `before` (but a later microsecond) can't flakily compare as
    # "earlier". Flooring is monotonic, so before_floored <= fetched_at is still a valid bound.
    before = datetime.now(timezone.utc)
    before_floored = before.replace(microsecond=(before.microsecond // 1000) * 1000)
    write_cache("cisa-kev", [SAMPLE_ITEM])
    after = datetime.now(timezone.utc)

    entry = read_cache("cisa-kev")
    assert entry is not None
    assert entry.items == [SAMPLE_ITEM]
    fetched_at = datetime.fromisoformat(entry.fetched_at.replace("Z", "+00:00"))
    assert before_floored <= fetched_at <= after


def test_keeps_caches_for_different_sources_independent(cache_dir):
    write_cache("cisa-kev", [SAMPLE_ITEM])
    write_cache("gdelt", [])

    kev = read_cache("cisa-kev")
    gdelt = read_cache("gdelt")
    assert len(kev.items) == 1
    assert len(gdelt.items) == 0


def test_overwrites_the_previous_snapshot_on_the_next_successful_write(cache_dir):
    write_cache("cisa-kev", [SAMPLE_ITEM])
    second = FeedItem(**{**SAMPLE_ITEM.__dict__, "id": "cisa-kev:CVE-2026-00002"})
    write_cache("cisa-kev", [second])

    entry = read_cache("cisa-kev")
    assert entry.items == [second]


def test_treats_a_corrupt_cache_file_as_no_cache_never_as_fabricated_content(cache_dir):
    (cache_dir / "cisa-kev.json").write_text("{ not valid json", encoding="utf-8")
    assert read_cache("cisa-kev") is None


def test_treats_a_well_formed_but_wrong_shaped_cache_file_as_no_cache(cache_dir):
    (cache_dir / "cisa-kev.json").write_text('{"unexpected": true}', encoding="utf-8")
    assert read_cache("cisa-kev") is None
