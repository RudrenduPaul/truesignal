"""
Library entry point -- import truesignal's connectors and provenance layer programmatically.

    from truesignal import ALL_CONNECTORS, get_connector

    for connector in ALL_CONNECTORS:
        for item in connector.fetch_items():
            print(item.status, item.url)

This is the Python port of the truesignal-cli npm package
(https://www.npmjs.com/package/truesignal-cli). Both distributions ship the same five source
connectors (CISA-KEV, Cloudflare Radar, Reddit, Telegram, GDELT) and the same no-fabrication
provenance guarantee; see https://github.com/RudrenduPaul/truesignal for the canonical
documentation and the original TypeScript source.
"""
from .connectors import ALL_CONNECTORS, get_connector
from .provenance import (
    fetch_with_fallback,
    get_cache_dir,
    read_cache,
    stamp_fallback,
    stamp_live,
    write_cache,
)
from .types import Connector, ConnectorNotConfiguredError, FeedItem, ItemStatus, UnstampedItem

__version__ = "0.1.0"

__all__ = [
    "Connector",
    "FeedItem",
    "ItemStatus",
    "UnstampedItem",
    "ConnectorNotConfiguredError",
    "ALL_CONNECTORS",
    "get_connector",
    "fetch_with_fallback",
    "stamp_live",
    "stamp_fallback",
    "read_cache",
    "write_cache",
    "get_cache_dir",
    "__version__",
]
