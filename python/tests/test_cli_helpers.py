"""Port of src/truesignal/cli-helpers.test.ts."""
from datetime import datetime, timezone

from truesignal.cli_helpers import (
    ExitCode,
    format_feed_item_human,
    format_init_report,
    get_connector_statuses,
    parse_item_id,
    run_feed,
    run_verify,
    select_connectors,
)
from truesignal.types import Connector, FeedItem


class _FakeConnector(Connector):
    def __init__(self, name, *, label=None, requires_config=False, config_env_vars=(), configured=True, items=None, raises=None):
        self.name = name
        self.label = label or name
        self.requires_config = requires_config
        self.config_env_vars = config_env_vars
        self._configured = configured
        self._items = items if items is not None else []
        self._raises = raises

    def is_configured(self):
        return self._configured

    def fetch_items(self):
        if self._raises is not None:
            raise self._raises
        return self._items


LIVE_ITEM = FeedItem(
    id="cisa-kev:CVE-2026-00001",
    source="cisa-kev",
    title="Sample CVE",
    url="https://nvd.nist.gov/vuln/detail/CVE-2026-00001",
    timestamp="2026-07-01T00:00:00.000Z",
    status="live",
)

FALLBACK_ITEM = FeedItem(
    id="gdelt:https://example.com/a",
    source="gdelt",
    title=LIVE_ITEM.title,
    url=LIVE_ITEM.url,
    timestamp=LIVE_ITEM.timestamp,
    status="fallback",
    fallback_age_seconds=3661,
)


def test_exit_code_assigns_each_meaning_a_distinct_code():
    values = [code.value for code in ExitCode]
    assert len(set(values)) == len(values)


def test_reports_zero_config_connectors_as_ready_with_no_missing_env_vars():
    connector = _FakeConnector("cisa-kev", requires_config=False)
    [status] = get_connector_statuses([connector])
    assert status.name == "cisa-kev"
    assert status.requires_config is False
    assert status.configured is True
    assert status.missing_env_vars == []


def test_reports_an_unconfigured_connector_with_its_missing_env_vars():
    connector = _FakeConnector(
        "reddit",
        requires_config=True,
        config_env_vars=("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"),
        configured=False,
    )
    [status] = get_connector_statuses([connector])
    assert status.missing_env_vars == ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"]


def test_format_init_report_lists_every_connector_and_a_ready_count_summary():
    ready = _FakeConnector("cisa-kev")
    not_ready = _FakeConnector("telegram", requires_config=True, config_env_vars=("TELEGRAM_BOT_TOKEN",), configured=False)
    report = format_init_report(get_connector_statuses([ready, not_ready]))
    assert "cisa-kev" in report
    assert "telegram" in report
    assert "TELEGRAM_BOT_TOKEN" in report
    assert "1/2 connectors ready." in report


def test_format_init_report_warns_when_nothing_at_all_is_ready():
    not_ready = _FakeConnector("telegram", requires_config=True, config_env_vars=("TELEGRAM_BOT_TOKEN",), configured=False)
    report = format_init_report(get_connector_statuses([not_ready]))
    assert "No connectors are usable" in report


def test_select_connectors_with_no_filter_queries_ready_and_skips_unconfigured():
    ready = _FakeConnector("cisa-kev")
    configured = _FakeConnector("cloudflare-radar", requires_config=True, configured=True)
    not_configured = _FakeConnector("telegram", requires_config=True, configured=False)
    selection = select_connectors([ready, configured, not_configured])
    assert [c.name for c in selection.to_query] == ["cisa-kev", "cloudflare-radar"]
    assert [c.name for c in selection.skipped] == ["telegram"]
    assert selection.unknown_source is None


def test_select_connectors_with_a_valid_source_filter_narrows_to_just_that_connector():
    ready = _FakeConnector("cisa-kev")
    other = _FakeConnector("gdelt")
    selection = select_connectors([ready, other], "cisa-kev")
    assert [c.name for c in selection.to_query] == ["cisa-kev"]
    assert selection.skipped == []


def test_select_connectors_with_an_unknown_source_filter_reports_unknown_source():
    selection = select_connectors([_FakeConnector("cisa-kev")], "not-a-real-source")
    assert selection.unknown_source == "not-a-real-source"
    assert selection.to_query == []


def test_select_connectors_with_source_naming_an_unconfigured_connector_skips_it():
    not_configured = _FakeConnector("telegram", requires_config=True, configured=False)
    selection = select_connectors([not_configured], "telegram")
    assert selection.to_query == []
    assert [c.name for c in selection.skipped] == ["telegram"]


def test_format_feed_item_human_formats_a_live_item_with_a_real_url_and_relative_age():
    now = datetime(2026, 7, 1, 0, 5, 0, tzinfo=timezone.utc)
    line = format_feed_item_human(LIVE_ITEM, now)
    assert "[live]" in line
    assert LIVE_ITEM.url in line
    assert "5m ago" in line


def test_format_feed_item_human_formats_a_fallback_item_with_its_honest_cached_age():
    now = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
    line = format_feed_item_human(FALLBACK_ITEM, now)
    assert "[fallback," in line
    assert "1h old" in line


def test_parse_item_id_splits_a_simple_id_on_the_first_colon():
    assert parse_item_id("cisa-kev:CVE-2026-00001") == ("cisa-kev", "CVE-2026-00001")


def test_parse_item_id_preserves_colons_inside_the_native_id():
    assert parse_item_id("gdelt:https://example.com/a") == ("gdelt", "https://example.com/a")
    assert parse_item_id("telegram:111:5") == ("telegram", "111:5")


def test_parse_item_id_returns_none_for_a_malformed_id():
    assert parse_item_id("no-colon-here") is None
    assert parse_item_id(":missing-source") is None
    assert parse_item_id("missing-native-id:") is None
    assert parse_item_id("") is None


def test_run_feed_aggregates_items_across_every_configured_connector():
    a = _FakeConnector("a", items=[LIVE_ITEM])
    b = _FakeConnector("b", items=[FALLBACK_ITEM])
    result = run_feed([a, b])
    assert result.items == [LIVE_ITEM, FALLBACK_ITEM]
    assert result.failures == []


def test_run_feed_reports_a_failing_connector_without_dropping_items_from_the_others():
    good = _FakeConnector("good", items=[LIVE_ITEM])
    bad = _FakeConnector("bad", raises=RuntimeError("boom"))
    result = run_feed([good, bad])
    assert result.items == [LIVE_ITEM]
    assert len(result.failures) == 1
    assert result.failures[0].source == "bad"
    assert result.failures[0].error == "boom"


def test_run_feed_propagates_an_unknown_source_without_calling_any_connector():
    called = {"value": False}

    class _TrackingConnector(_FakeConnector):
        def fetch_items(self):
            called["value"] = True
            return []

    a = _TrackingConnector("a")
    result = run_feed([a], "nonexistent")
    assert result.unknown_source == "nonexistent"
    assert called["value"] is False


def test_run_verify_reports_invalid_id_for_a_malformed_item_id():
    result = run_verify([], "not-valid")
    assert result.error_kind == "invalid-id"
    assert result.found is False


def test_run_verify_reports_unknown_source_when_no_connector_matches_the_id_prefix():
    result = run_verify([_FakeConnector("cisa-kev")], "unknown-source:123")
    assert result.error_kind == "unknown-source"


def test_run_verify_reports_not_configured_when_the_matching_connector_lacks_config():
    connector = _FakeConnector("reddit", requires_config=True, configured=False)
    result = run_verify([connector], "reddit:abc123")
    assert result.error_kind == "not-configured"


def test_run_verify_reports_network_error_when_fetch_items_raises():
    connector = _FakeConnector("cisa-kev", raises=RuntimeError("upstream down"))
    result = run_verify([connector], "cisa-kev:CVE-2026-00001")
    assert result.error_kind == "network-error"
    assert "upstream down" in result.error_message


def test_run_verify_reports_found_false_when_the_item_is_no_longer_in_the_feed():
    connector = _FakeConnector("cisa-kev", items=[])
    result = run_verify([connector], "cisa-kev:CVE-2026-99999")
    assert result.found is False
    assert result.error_kind is None


def test_run_verify_reports_full_provenance_details_when_the_item_is_found_live():
    connector = _FakeConnector("cisa-kev", items=[LIVE_ITEM])
    result = run_verify([connector], LIVE_ITEM.id)
    assert result.found is True
    assert result.status == "live"
    assert result.url == LIVE_ITEM.url
    assert result.timestamp == LIVE_ITEM.timestamp


def test_run_verify_reports_fallback_age_seconds_when_the_item_is_found_as_a_fallback():
    connector = _FakeConnector("gdelt", items=[FALLBACK_ITEM])
    result = run_verify([connector], FALLBACK_ITEM.id)
    assert result.found is True
    assert result.status == "fallback"
    assert result.fallback_age_seconds == 3661
