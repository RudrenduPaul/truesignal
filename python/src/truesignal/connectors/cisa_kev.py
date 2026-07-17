"""
CISA Known Exploited Vulnerabilities (KEV) catalog connector.

Public JSON feed, no API key required -- works with zero configuration. Source:
https://www.cisa.gov/known-exploited-vulnerabilities-catalog

Direct port of src/truesignal/connectors/cisa-kev.ts.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .. import http
from .._util import format_iso8601
from ..provenance.stamp import fetch_with_fallback
from ..types import Connector, FeedItem, UnstampedItem

CISA_KEV_FEED_URL = (
    "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
)

#: Cap on how many of the most recently added vulnerabilities a single feed pull returns.
CISA_KEV_MAX_ITEMS = 25


def _to_unstamped_item(vuln: Dict[str, Any]) -> Optional[UnstampedItem]:
    # dateAdded from CISA is a bare date ("2026-07-10"); treat it as midnight UTC so it is a real,
    # parseable ISO-8601 instant rather than a fabricated time-of-day. A single record with a
    # missing or malformed dateAdded is skipped rather than raised on -- one bad record in an
    # otherwise-good batch must not take down every other real item alongside it.
    date_added = vuln.get("dateAdded")
    cve_id = vuln.get("cveID")
    if not date_added or not cve_id:
        return None
    try:
        parsed = datetime.strptime(date_added, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return UnstampedItem(
        id=f"cisa-kev:{cve_id}",
        source="cisa-kev",
        title=f"{cve_id}: {vuln.get('vulnerabilityName', '')}",
        url=f"https://nvd.nist.gov/vuln/detail/{cve_id}",
        timestamp=format_iso8601(parsed),
        summary=f"{vuln.get('vendorProject', '')} {vuln.get('product', '')} -- "
        f"{vuln.get('shortDescription', '')}",
    )


def get_json(url: str) -> Any:
    """Thin wrapper over http.get_json -- gives tests a stable module-level attribute to
    monkeypatch, mirroring the TS suite's `vi.stubGlobal('fetch', ...)`."""
    return http.get_json(url)


def _fetch_live() -> List[UnstampedItem]:
    data = get_json(CISA_KEV_FEED_URL)
    vulnerabilities = data.get("vulnerabilities") if isinstance(data, dict) else None
    if not isinstance(vulnerabilities, list):
        raise ValueError("CISA-KEV feed returned an unexpected shape")

    sorted_vulns = sorted(
        vulnerabilities, key=lambda v: v.get("dateAdded", ""), reverse=True
    )[:CISA_KEV_MAX_ITEMS]
    items = []
    for vuln in sorted_vulns:
        item = _to_unstamped_item(vuln)
        if item is not None:
            items.append(item)
    return items


class CisaKevConnector(Connector):
    name = "cisa-kev"
    label = "CISA Known Exploited Vulnerabilities"
    requires_config = False
    config_env_vars: tuple = ()

    def is_configured(self) -> bool:
        return True

    def fetch_items(self) -> List[FeedItem]:
        return fetch_with_fallback("cisa-kev", _fetch_live)


cisa_kev_connector = CisaKevConnector()
