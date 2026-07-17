"""
Every connector this build ships, in a fixed order. Adding a new source is: implement Connector
(truesignal/types.py) in a new module in this package, then add it to ALL_CONNECTORS below --
nothing else in the CLI or provenance layer needs to change. See CONTRIBUTING.md.

Direct port of src/truesignal/connectors/index.ts.
"""
from __future__ import annotations

from typing import List, Optional, Sequence

from ..types import Connector
from .cisa_kev import CisaKevConnector, cisa_kev_connector
from .cloudflare_radar import CloudflareRadarConnector, cloudflare_radar_connector
from .gdelt import GdeltConnector, gdelt_connector
from .reddit import RedditConnector, reddit_connector
from .telegram import TelegramConnector, telegram_connector

ALL_CONNECTORS: Sequence[Connector] = (
    cisa_kev_connector,
    cloudflare_radar_connector,
    reddit_connector,
    telegram_connector,
    gdelt_connector,
)


def get_connector(name: str) -> Optional[Connector]:
    for connector in ALL_CONNECTORS:
        if connector.name == name:
            return connector
    return None


__all__ = [
    "ALL_CONNECTORS",
    "get_connector",
    "CisaKevConnector",
    "cisa_kev_connector",
    "CloudflareRadarConnector",
    "cloudflare_radar_connector",
    "RedditConnector",
    "reddit_connector",
    "TelegramConnector",
    "telegram_connector",
    "GdeltConnector",
    "gdelt_connector",
]
