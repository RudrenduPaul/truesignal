"""
Cloudflare Radar connector -- pulls recent global traffic anomalies from the official Radar
API. Requires a free Cloudflare API token (radar read scope) via the CLOUDFLARE_RADAR_API_TOKEN
environment variable. Docs: https://developers.cloudflare.com/radar/

Direct port of src/truesignal/connectors/cloudflare-radar.ts.
"""
from __future__ import annotations

import os
import urllib.parse
from typing import Any, Dict, List, Optional

from .. import http
from .._util import format_iso8601, parse_iso8601
from ..provenance.stamp import fetch_with_fallback
from ..types import Connector, ConnectorNotConfiguredError, FeedItem, UnstampedItem

CLOUDFLARE_RADAR_API_URL = "https://api.cloudflare.com/client/v4/radar/traffic_anomalies"
CLOUDFLARE_RADAR_MAX_ITEMS = 25

_TOKEN_ENV_VAR = "CLOUDFLARE_RADAR_API_TOKEN"


def _is_configured() -> bool:
    return bool(os.environ.get(_TOKEN_ENV_VAR, "").strip())


def _to_unstamped_item(anomaly: Dict[str, Any]) -> Optional[UnstampedItem]:
    # startDate from Radar is expected to be a real ISO-8601 instant. A single anomaly with a
    # missing or malformed startDate is skipped rather than raised on -- one bad record in an
    # otherwise-good batch must not take down every other real item alongside it.
    uuid = anomaly.get("uuid")
    start_date = anomaly.get("startDate")
    if not uuid or not start_date:
        return None
    try:
        parsed = parse_iso8601(start_date)
    except ValueError:
        return None
    asn_details = anomaly.get("asnDetails") or {}
    location_details = anomaly.get("locationDetails") or {}
    subject = asn_details.get("name") or location_details.get("name") or "Unknown network"
    anomaly_type = anomaly.get("type") or "traffic anomaly"
    asn = asn_details.get("asn")
    return UnstampedItem(
        id=f"cloudflare-radar:{uuid}",
        source="cloudflare-radar",
        title=f"{subject}: {anomaly_type}",
        url=f"https://radar.cloudflare.com/anomalies/{uuid}",
        timestamp=format_iso8601(parsed),
        summary=f"AS{asn}" if asn else None,
    )


def get_json(url: str, headers: Optional[Dict[str, str]] = None) -> Any:
    """Thin wrapper over http.get_json -- gives tests a stable module-level attribute to
    monkeypatch, mirroring the TS suite's `vi.stubGlobal('fetch', ...)`."""
    return http.get_json(url, headers=headers)


def _fetch_live() -> List[UnstampedItem]:
    token = os.environ.get(_TOKEN_ENV_VAR)
    if not token:
        raise ConnectorNotConfiguredError("cloudflare-radar")

    params = {"limit": str(CLOUDFLARE_RADAR_MAX_ITEMS)}
    url = f"{CLOUDFLARE_RADAR_API_URL}?{urllib.parse.urlencode(params)}"
    data = get_json(url, headers={"Authorization": f"Bearer {token}"})
    if not isinstance(data, dict) or not data.get("success"):
        raise ValueError("Cloudflare Radar API reported success: false")
    anomalies = (data.get("result") or {}).get("trafficAnomalies") or []
    items = []
    for anomaly in anomalies:
        item = _to_unstamped_item(anomaly)
        if item is not None:
            items.append(item)
    return items


class CloudflareRadarConnector(Connector):
    name = "cloudflare-radar"
    label = "Cloudflare Radar"
    requires_config = True
    config_env_vars = (_TOKEN_ENV_VAR,)

    def is_configured(self) -> bool:
        return _is_configured()

    def fetch_items(self) -> List[FeedItem]:
        if not _is_configured():
            raise ConnectorNotConfiguredError("cloudflare-radar")
        return fetch_with_fallback("cloudflare-radar", _fetch_live)


cloudflare_radar_connector = CloudflareRadarConnector()
