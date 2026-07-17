"""Port of src/truesignal/connectors/gdelt.test.ts."""
from truesignal.connectors.gdelt import gdelt_connector


def test_requires_no_configuration():
    assert gdelt_connector.requires_config is False
    assert gdelt_connector.is_configured() is True


def test_maps_gdelt_articles_to_real_verifiable_feed_items(monkeypatch, cache_dir):
    monkeypatch.setattr(
        "truesignal.connectors.gdelt.get_json",
        lambda url: {
            "articles": [
                {
                    "url": "https://example.com/article-a",
                    "title": "Sample security article",
                    "seendate": "20260315T120000Z",
                    "domain": "example.com",
                    "sourcecountry": "United States",
                }
            ]
        },
    )

    [item] = gdelt_connector.fetch_items()
    assert item.id == "gdelt:https://example.com/article-a"
    assert item.url == "https://example.com/article-a"
    assert item.timestamp == "2026-03-15T12:00:00.000Z"
    assert item.status == "live"
    assert item.summary == "example.com (United States)"


def test_falls_back_rather_than_fabricating_when_the_upstream_fetch_fails(monkeypatch, cache_dir):
    def _raise(url):
        raise RuntimeError("network unreachable")

    monkeypatch.setattr("truesignal.connectors.gdelt.get_json", _raise)
    assert gdelt_connector.fetch_items() == []


def test_skips_a_single_article_with_an_unrecognized_seendate_format(monkeypatch, cache_dir):
    monkeypatch.setattr(
        "truesignal.connectors.gdelt.get_json",
        lambda url: {
            "articles": [
                {
                    "url": "https://example.com/good",
                    "title": "Good article",
                    "seendate": "20260315T120000Z",
                    "domain": "example.com",
                },
                {
                    "url": "https://example.com/bad",
                    "title": "Bad article",
                    "seendate": "not-a-real-date",
                    "domain": "example.com",
                },
            ]
        },
    )

    items = gdelt_connector.fetch_items()
    assert len(items) == 1
    assert items[0].url == "https://example.com/good"


def test_omits_summary_country_suffix_when_sourcecountry_is_absent(monkeypatch, cache_dir):
    monkeypatch.setattr(
        "truesignal.connectors.gdelt.get_json",
        lambda url: {
            "articles": [
                {
                    "url": "https://example.com/article-b",
                    "title": "No country field",
                    "seendate": "20260315T120000Z",
                    "domain": "example.com",
                }
            ]
        },
    )

    [item] = gdelt_connector.fetch_items()
    assert item.summary == "example.com"
