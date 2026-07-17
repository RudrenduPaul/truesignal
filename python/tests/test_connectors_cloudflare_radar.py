"""Port of src/truesignal/connectors/cloudflare-radar.test.ts."""
import pytest

from truesignal.connectors.cloudflare_radar import cloudflare_radar_connector
from truesignal.types import ConnectorNotConfiguredError


def test_is_unconfigured_with_no_token_and_raises_rather_than_fetching(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_RADAR_API_TOKEN", raising=False)
    assert cloudflare_radar_connector.is_configured() is False
    with pytest.raises(ConnectorNotConfiguredError):
        cloudflare_radar_connector.fetch_items()


def test_maps_traffic_anomalies_to_real_verifiable_feed_items(monkeypatch, cache_dir):
    monkeypatch.setenv("CLOUDFLARE_RADAR_API_TOKEN", "fake-token")
    monkeypatch.setattr(
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

    [item] = cloudflare_radar_connector.fetch_items()
    assert item.id == "cloudflare-radar:anomaly-1"
    assert item.url == "https://radar.cloudflare.com/anomalies/anomaly-1"
    assert item.title == "Example Net: outage"
    assert item.summary == "AS64500"


def test_falls_back_to_location_name_when_no_asn_details_present(monkeypatch, cache_dir):
    monkeypatch.setenv("CLOUDFLARE_RADAR_API_TOKEN", "fake-token")
    monkeypatch.setattr(
        "truesignal.connectors.cloudflare_radar.get_json",
        lambda url, headers=None: {
            "success": True,
            "result": {
                "trafficAnomalies": [
                    {
                        "uuid": "anomaly-2",
                        "startDate": "2026-01-01T00:00:00Z",
                        "type": "outage",
                        "locationDetails": {"name": "Germany"},
                    }
                ]
            },
        },
    )

    [item] = cloudflare_radar_connector.fetch_items()
    assert item.title == "Germany: outage"
    assert item.summary is None


def test_falls_back_rather_than_fabricating_when_the_api_reports_success_false(monkeypatch, cache_dir):
    monkeypatch.setenv("CLOUDFLARE_RADAR_API_TOKEN", "fake-token")
    monkeypatch.setattr(
        "truesignal.connectors.cloudflare_radar.get_json",
        lambda url, headers=None: {"success": False},
    )
    assert cloudflare_radar_connector.fetch_items() == []


def test_skips_a_single_anomaly_with_a_malformed_start_date(monkeypatch, cache_dir):
    monkeypatch.setenv("CLOUDFLARE_RADAR_API_TOKEN", "fake-token")
    monkeypatch.setattr(
        "truesignal.connectors.cloudflare_radar.get_json",
        lambda url, headers=None: {
            "success": True,
            "result": {
                "trafficAnomalies": [
                    {"uuid": "good", "startDate": "2026-01-01T00:00:00Z", "type": "outage"},
                    {"uuid": "bad", "startDate": "not-a-real-date", "type": "outage"},
                ]
            },
        },
    )

    items = cloudflare_radar_connector.fetch_items()
    assert len(items) == 1
    assert items[0].id == "cloudflare-radar:good"
