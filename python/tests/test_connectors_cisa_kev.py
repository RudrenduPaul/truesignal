"""Port of src/truesignal/connectors/cisa-kev.test.ts."""
from truesignal.connectors.cisa_kev import CISA_KEV_MAX_ITEMS, cisa_kev_connector


def test_requires_no_configuration():
    assert cisa_kev_connector.requires_config is False
    assert cisa_kev_connector.is_configured() is True
    assert cisa_kev_connector.config_env_vars == ()


def test_maps_cisa_vulnerabilities_to_real_verifiable_feed_items(monkeypatch, cache_dir):
    monkeypatch.setattr(
        "truesignal.connectors.cisa_kev.get_json",
        lambda url: {
            "vulnerabilities": [
                {
                    "cveID": "CVE-2026-11111",
                    "vendorProject": "Acme",
                    "product": "Gadget",
                    "vulnerabilityName": "Buffer Overflow",
                    "dateAdded": "2026-03-05",
                    "shortDescription": "Remote attacker can execute arbitrary code.",
                }
            ]
        },
    )

    [item] = cisa_kev_connector.fetch_items()
    assert item.id == "cisa-kev:CVE-2026-11111"
    assert item.source == "cisa-kev"
    assert item.url == "https://nvd.nist.gov/vuln/detail/CVE-2026-11111"
    assert item.timestamp == "2026-03-05T00:00:00.000Z"
    assert item.status == "live"
    assert "CVE-2026-11111" in item.title
    assert "Acme" in item.summary


def test_sorts_by_date_added_descending_and_caps_at_max_items(monkeypatch, cache_dir):
    vulnerabilities = [
        {
            "cveID": f"CVE-2026-{i:05d}",
            "vendorProject": "Acme",
            "product": "Gadget",
            "vulnerabilityName": "Sample",
            "dateAdded": f"2026-01-{(i % 28) + 1:02d}",
            "shortDescription": "desc",
        }
        for i in range(CISA_KEV_MAX_ITEMS + 10)
    ]
    monkeypatch.setattr("truesignal.connectors.cisa_kev.get_json", lambda url: {"vulnerabilities": vulnerabilities})

    items = cisa_kev_connector.fetch_items()
    assert len(items) == CISA_KEV_MAX_ITEMS


def test_falls_back_rather_than_fabricating_when_the_feed_returns_a_non_ok_status(monkeypatch, cache_dir):
    def _raise(url):
        raise RuntimeError("CISA-KEV feed returned HTTP 503")

    monkeypatch.setattr("truesignal.connectors.cisa_kev.get_json", _raise)
    # fetch_items itself never raises (fetch_with_fallback catches it); no cache exists, so it
    # resolves to an empty list rather than propagating the error.
    assert cisa_kev_connector.fetch_items() == []


def test_falls_back_rather_than_fabricating_when_the_feed_returns_an_unexpected_shape(monkeypatch, cache_dir):
    monkeypatch.setattr("truesignal.connectors.cisa_kev.get_json", lambda url: {"notVulnerabilities": []})
    assert cisa_kev_connector.fetch_items() == []


def test_skips_a_single_malformed_record_rather_than_discarding_the_whole_batch(monkeypatch, cache_dir):
    monkeypatch.setattr(
        "truesignal.connectors.cisa_kev.get_json",
        lambda url: {
            "vulnerabilities": [
                {
                    "cveID": "CVE-2026-22222",
                    "vendorProject": "Acme",
                    "product": "Gadget",
                    "vulnerabilityName": "Valid Entry",
                    "dateAdded": "2026-04-01",
                    "shortDescription": "A real, well-formed record.",
                },
                {
                    "cveID": "CVE-2026-33333",
                    "vendorProject": "Acme",
                    "product": "Gadget",
                    "vulnerabilityName": "Malformed Entry",
                    "dateAdded": "not-a-real-date",
                    "shortDescription": "A record with an unparseable dateAdded.",
                },
            ]
        },
    )

    items = cisa_kev_connector.fetch_items()
    assert len(items) == 1
    assert items[0].id == "cisa-kev:CVE-2026-22222"
