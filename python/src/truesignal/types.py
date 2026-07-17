"""
Shared types for truesignal's connector and provenance layers.

The single hardest rule in this codebase: every FeedItem this program ever emits must be
traceable to a real upstream response. ``status`` records whether the item came from a live
fetch or a cached fallback -- there is no third path where data is invented.

This is a direct port of src/truesignal/types.ts. Field names are snake_case here (Python
convention) where the TypeScript source uses camelCase -- e.g. ``fallback_age_seconds`` vs
``fallbackAgeSeconds`` -- documented in docs/getting-started.md.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

#: Whether a feed item came from a live upstream fetch or a cached fallback.
ItemStatus = str  # "live" | "fallback" -- kept as str (not an Enum) so it JSON-serializes plainly.


@dataclass(frozen=True)
class FeedItem:
    """A single item surfaced by a connector, stamped with real provenance."""

    #: Stable id, unique within a source: "{source}:{source_native_id}".
    id: str
    #: The connector name that produced this item, e.g. "cisa-kev".
    source: str
    #: Human-readable title.
    title: str
    #: Real, dereferenceable URL to the upstream item. Never a fabricated or placeholder link.
    url: str
    #: Real ISO-8601 timestamp from the upstream source describing when the underlying event or
    #: publication occurred. Never rewritten to "now" -- for a fallback item this is the original
    #: event time, not the time the fallback was served.
    timestamp: str
    #: "live" if fetched from the upstream source just now, "fallback" if served from cache.
    status: ItemStatus
    #: Present only when status is "fallback": how many seconds old the cached data being shown
    #: is, measured from when it was originally fetched live to now. Required whenever status is
    #: "fallback" so a caller can never mistake stale data for current.
    fallback_age_seconds: Optional[int] = None
    #: Optional short human-readable summary.
    summary: Optional[str] = None

    def to_dict(self) -> dict:
        """JSON-serializable dict, omitting unset optional fields (mirrors the TS JSON shape,
        with snake_case keys per this port's Python-idiomatic field names)."""
        data = {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "url": self.url,
            "timestamp": self.timestamp,
            "status": self.status,
        }
        if self.fallback_age_seconds is not None:
            data["fallback_age_seconds"] = self.fallback_age_seconds
        if self.summary is not None:
            data["summary"] = self.summary
        return data


@dataclass(frozen=True)
class UnstampedItem:
    """The shape a connector's raw fetch produces, before the provenance layer adds a status."""

    id: str
    source: str
    title: str
    url: str
    timestamp: str
    summary: Optional[str] = None


class ConnectorNotConfiguredError(Exception):
    """Raised when a connector's config is missing and code calls fetch_items() anyway."""

    def __init__(self, connector_name: str) -> None:
        self.connector_name = connector_name
        super().__init__(
            f'Connector "{connector_name}" requires configuration that is not present. '
            f'Run "truesignal init" to see what is missing.'
        )


class Connector(abc.ABC):
    """
    A source connector. Every connector in truesignal/connectors/ implements this interface so
    connectors are swappable plugins behind one common contract -- adding a new source (NVD,
    Shodan, VirusTotal, ...) is a new module implementing this interface, never a change to the
    CLI or provenance layer.
    """

    #: Stable machine-readable name, e.g. "cisa-kev". Used as the --source flag value.
    name: str
    #: Human-readable label, e.g. "CISA Known Exploited Vulnerabilities".
    label: str
    #: True if this connector needs BYO credentials (an API key, token, or app registration).
    requires_config: bool
    #: The environment variable names this connector reads credentials from, if any.
    config_env_vars: Sequence[str] = field(default_factory=tuple)

    @abc.abstractmethod
    def is_configured(self) -> bool:
        """Returns True if every required env var this connector needs is present and non-empty."""

    @abc.abstractmethod
    def fetch_items(self) -> List[FeedItem]:
        """
        Fetches the current items from this source.

        Contract: on success, returns real status="live" items with real timestamps and URLs. On
        upstream failure, returns real cached items stamped status="fallback" with an accurate
        fallback_age_seconds, or an empty list if no cache exists. Never returns synthetic,
        randomized, or silently-relabeled-as-current data. Raises ConnectorNotConfiguredError if
        called while requires_config is True and is_configured() is False.
        """
