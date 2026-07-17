"""
The single most important test file in this repo.

It proves, for every connector this product ships, that a failed upstream fetch never results
in fabricated, randomized, or silently-relabeled-as-current data -- only a real cached
`fallback` item with an honest age, or nothing at all. This is the entire product claim; if any
of these tests fail, truesignal is shipping the exact bug it exists to not repeat.

Direct port of src/truesignal/provenance/no-fabrication.test.ts.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Dict

import pytest

from truesignal._util import parse_iso8601
from truesignal.connectors import ALL_CONNECTORS
from truesignal.connectors.cisa_kev import cisa_kev_connector
from truesignal.connectors.cloudflare_radar import cloudflare_radar_connector
from truesignal.connectors.gdelt import gdelt_connector
from truesignal.connectors.reddit import reddit_connector
from truesignal.connectors.telegram import telegram_connector
from truesignal.types import Connector, ConnectorNotConfiguredError


def _raise_network_error(*_args: Any, **_kwargs: Any) -> Any:
    raise RuntimeError("network unreachable")


class FixtureCase:
    def __init__(
        self,
        connector: Connector,
        env: Dict[str, str],
        mock_success: Callable[[pytest.MonkeyPatch], None],
        mock_failure: Callable[[pytest.MonkeyPatch], None],
    ) -> None:
        self.connector = connector
        self.env = env
        self.mock_success = mock_success
        self.mock_failure = mock_failure

    def __repr__(self) -> str:  # pytest test id
        return self.connector.name


def _cisa_kev_success(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(
        "truesignal.connectors.cisa_kev.get_json",
        lambda url: {
            "vulnerabilities": [
                {
                    "cveID": "CVE-2026-00001",
                    "vendorProject": "Acme",
                    "product": "Widget",
                    "vulnerabilityName": "Sample RCE",
                    "dateAdded": "2026-01-01",
                    "shortDescription": "A sample description.",
                }
            ]
        },
    )


def _gdelt_success(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(
        "truesignal.connectors.gdelt.get_json",
        lambda url: {
            "articles": [
                {
                    "url": "https://example.com/article-a",
                    "title": "Sample security article",
                    "seendate": "20260101T000000Z",
                    "domain": "example.com",
                }
            ]
        },
    )


def _cloudflare_radar_success(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(
        "truesignal.connectors.cloudflare_radar.get_json",
        lambda url, headers=None: {
            "success": True,
            "result": {
                "trafficAnomalies": [
                    {
                        "uuid": "anomaly-1",
                        "startDate": "2026-01-01T00:00:00Z",
                        "type": "outage",
                        "asnDetails": {"asn": 64500, "name": "Example Net"},
                    }
                ]
            },
        },
    )


def _reddit_success(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(
        "truesignal.connectors.reddit.post_form_json",
        lambda url, form_data, headers=None: {
            "access_token": "fake-access-token",
            "token_type": "bearer",
            "expires_in": 3600,
        },
    )
    mp.setattr(
        "truesignal.connectors.reddit.get_json",
        lambda url, headers=None: {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "abc123",
                            "title": "Sample post",
                            "permalink": "/r/netsec/comments/abc123/sample_post/",
                            "created_utc": 1750000000,
                            "subreddit": "netsec",
                        }
                    }
                ]
            }
        },
    )


def _telegram_success(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(
        "truesignal.connectors.telegram.get_json",
        lambda url: {
            "ok": True,
            "result": [
                {
                    "update_id": 1,
                    "channel_post": {
                        "message_id": 5,
                        "date": 1750000000,
                        "chat": {"id": 111, "title": "Example Channel", "username": "examplechan"},
                        "text": "Sample channel post",
                    },
                }
            ],
        },
    )


CASES = [
    FixtureCase(
        cisa_kev_connector,
        {},
        _cisa_kev_success,
        lambda mp: mp.setattr("truesignal.connectors.cisa_kev.get_json", _raise_network_error),
    ),
    FixtureCase(
        gdelt_connector,
        {},
        _gdelt_success,
        lambda mp: mp.setattr("truesignal.connectors.gdelt.get_json", _raise_network_error),
    ),
    FixtureCase(
        cloudflare_radar_connector,
        {"CLOUDFLARE_RADAR_API_TOKEN": "fake-token-for-tests"},
        _cloudflare_radar_success,
        lambda mp: mp.setattr("truesignal.connectors.cloudflare_radar.get_json", _raise_network_error),
    ),
    FixtureCase(
        reddit_connector,
        {"REDDIT_CLIENT_ID": "fake-id", "REDDIT_CLIENT_SECRET": "fake-secret"},
        _reddit_success,
        lambda mp: (
            mp.setattr("truesignal.connectors.reddit.post_form_json", _raise_network_error),
            mp.setattr("truesignal.connectors.reddit.get_json", _raise_network_error),
        ),
    ),
    FixtureCase(
        telegram_connector,
        {"TELEGRAM_BOT_TOKEN": "fake-bot-token"},
        _telegram_success,
        lambda mp: mp.setattr("truesignal.connectors.telegram.get_json", _raise_network_error),
    ),
]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.connector.name)
class TestNoFabricationGuarantee:
    def test_returns_real_live_items_on_a_successful_fetch_each_stamped_status_live(
        self, case: FixtureCase, monkeypatch: pytest.MonkeyPatch, cache_dir
    ) -> None:
        for key, value in case.env.items():
            monkeypatch.setenv(key, value)
        case.mock_success(monkeypatch)

        items = case.connector.fetch_items()
        assert len(items) > 0
        for item in items:
            assert item.status == "live"
            assert item.fallback_age_seconds is None
            assert item.url.startswith("https://")
            parse_iso8601(item.timestamp)  # raises ValueError if not a real, parseable instant

    def test_returns_an_empty_list_never_fabricated_data_when_the_source_fails_and_no_cache_exists(
        self, case: FixtureCase, monkeypatch: pytest.MonkeyPatch, cache_dir
    ) -> None:
        for key, value in case.env.items():
            monkeypatch.setenv(key, value)
        case.mock_failure(monkeypatch)

        assert case.connector.fetch_items() == []

    def test_falls_back_to_real_cached_data_honestly_flagged_when_the_source_fails_after_a_prior_success(
        self, case: FixtureCase, monkeypatch: pytest.MonkeyPatch, cache_dir
    ) -> None:
        for key, value in case.env.items():
            monkeypatch.setenv(key, value)
        case.mock_success(monkeypatch)
        live_items = case.connector.fetch_items()
        assert len(live_items) > 0

        case.mock_failure(monkeypatch)
        fallback_items = case.connector.fetch_items()

        assert len(fallback_items) == len(live_items)
        for fallback_item, live_item in zip(fallback_items, live_items):
            assert fallback_item.status == "fallback"
            # The real event URL and timestamp must be identical to what was really fetched
            # live -- never rewritten, never replaced with a synthetic value.
            assert fallback_item.url == live_item.url
            assert fallback_item.timestamp == live_item.timestamp
            assert fallback_item.id == live_item.id
            assert isinstance(fallback_item.fallback_age_seconds, int)
            assert fallback_item.fallback_age_seconds >= 0


CONFIGURED_CASES = [case for case in CASES if case.connector.requires_config]


@pytest.mark.parametrize("case", CONFIGURED_CASES, ids=lambda c: c.connector.name)
def test_reports_is_configured_false_with_no_env_vars_set(case: FixtureCase, monkeypatch: pytest.MonkeyPatch) -> None:
    for env_var in case.connector.config_env_vars:
        monkeypatch.delenv(env_var, raising=False)
    assert case.connector.is_configured() is False


@pytest.mark.parametrize("case", CONFIGURED_CASES, ids=lambda c: c.connector.name)
def test_raises_connector_not_configured_error_rather_than_fabricating_data_when_unconfigured(
    case: FixtureCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    for env_var in case.connector.config_env_vars:
        monkeypatch.delenv(env_var, raising=False)
    # No HTTP mock installed at all -- if the connector tried to invent data instead of checking
    # configuration first, this test would fail on a real network call in CI.
    with pytest.raises(ConnectorNotConfiguredError):
        case.connector.fetch_items()


def test_no_connector_source_file_contains_a_synthetic_randomized_data_path() -> None:
    connectors_dir = Path(__file__).resolve().parents[1] / "src" / "truesignal" / "connectors"
    files = [f for f in connectors_dir.glob("*.py") if f.name != "__init__.py"]
    assert len(files) >= len(ALL_CONNECTORS)

    forbidden_patterns = [
        re.compile(r"random\.random\s*\("),
        re.compile(r"\bfaker\b", re.IGNORECASE),
        re.compile(r"datetime\.now\(\)"),
        re.compile(r"datetime\.utcnow\(\)"),
    ]
    for file in files:
        source = file.read_text(encoding="utf-8")
        for pattern in forbidden_patterns:
            assert not pattern.search(source), f"{file.name} must not match {pattern.pattern}"
