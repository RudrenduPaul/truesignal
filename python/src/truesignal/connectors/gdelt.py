"""
GDELT connector -- pulls recent OSINT/security-relevant news coverage from the GDELT 2.0 DOC
API. Public API, no key required -- works with zero configuration.
Docs: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/

Direct port of src/truesignal/connectors/gdelt.ts.
"""
from __future__ import annotations

import re
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .. import http
from .._util import format_iso8601
from ..provenance.stamp import fetch_with_fallback
from ..types import Connector, FeedItem, UnstampedItem

GDELT_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

#: Default query: security/OSINT-relevant English-language coverage.
GDELT_DEFAULT_QUERY = '(cyberattack OR vulnerability OR "data breach") sourcelang:english'

GDELT_MAX_RECORDS = 25

_SEENDATE_PATTERN = re.compile(r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$")


def _parse_gdelt_date(seendate: str) -> str:
    """GDELT returns "YYYYMMDDTHHMMSSZ" -- a real compact ISO-8601 basic-format instant."""
    match = _SEENDATE_PATTERN.match(seendate)
    if not match:
        raise ValueError(f"Unrecognized GDELT seendate format: {seendate}")
    year, month, day, hour, minute, second = (int(g) for g in match.groups())
    parsed = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    return format_iso8601(parsed)


def _to_unstamped_item(article: Dict[str, Any]) -> Optional[UnstampedItem]:
    # A single article with an unrecognized seendate format is skipped rather than raised on --
    # one bad record in an otherwise-good batch must not take down every other real item
    # alongside it.
    url = article.get("url")
    title = article.get("title")
    seendate = article.get("seendate")
    if not url or not title or not seendate:
        return None
    try:
        timestamp = _parse_gdelt_date(seendate)
    except ValueError:
        return None
    domain = article.get("domain", "")
    source_country = article.get("sourcecountry")
    summary = f"{domain} ({source_country})" if source_country else domain
    return UnstampedItem(
        id=f"gdelt:{url}",
        source="gdelt",
        title=title,
        url=url,
        timestamp=timestamp,
        summary=summary,
    )


def get_json(url: str) -> Any:
    """Thin wrapper over http.get_json -- gives tests a stable module-level attribute to
    monkeypatch, mirroring the TS suite's `vi.stubGlobal('fetch', ...)`."""
    return http.get_json(url)


def _fetch_live() -> List[UnstampedItem]:
    params = {
        "query": GDELT_DEFAULT_QUERY,
        "mode": "artlist",
        "format": "json",
        "maxrecords": str(GDELT_MAX_RECORDS),
        "sort": "datedesc",
    }
    url = f"{GDELT_API_URL}?{urllib.parse.urlencode(params)}"
    data = get_json(url)
    articles = data.get("articles") if isinstance(data, dict) else None
    if not isinstance(articles, list):
        articles = []
    items = []
    for article in articles:
        item = _to_unstamped_item(article)
        if item is not None:
            items.append(item)
    return items


class GdeltConnector(Connector):
    name = "gdelt"
    label = "GDELT"
    requires_config = False
    config_env_vars: tuple = ()

    def is_configured(self) -> bool:
        return True

    def fetch_items(self) -> List[FeedItem]:
        return fetch_with_fallback("gdelt", _fetch_live)


gdelt_connector = GdeltConnector()
