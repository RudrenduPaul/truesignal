"""
Testable logic behind the CLI. cli.py wires this up to argparse and sys.exit(); every function
here is pure enough to unit test without spawning a real process.

Direct port of src/truesignal/cli-helpers.ts. Field/function names are snake_case here (Python
convention) where the TypeScript source uses camelCase.
"""
from __future__ import annotations

import concurrent.futures
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Dict, List, Optional, Sequence, Tuple

from ._util import parse_iso8601
from .types import Connector, FeedItem, ItemStatus


class ExitCode(IntEnum):
    """Exit codes this CLI uses. Documented here and in the per-subcommand --help text."""

    #: Command completed successfully.
    SUCCESS = 0
    #: Unexpected/uncategorized error.
    GENERAL_ERROR = 1
    #: The requested connector(s) exist but none are configured -- nothing could run.
    NO_CONNECTORS_CONFIGURED = 2
    #: A configured connector's upstream fetch failed and produced no fallback data either.
    NETWORK_ERROR = 3
    #: `verify <item-id>` was given an id that doesn't parse or names an unknown source.
    INVALID_ITEM_ID = 4


@dataclass(frozen=True)
class ConnectorStatus:
    name: str
    label: str
    requires_config: bool
    configured: bool
    missing_env_vars: List[str] = field(default_factory=list)


def get_connector_statuses(connectors: Sequence[Connector]) -> List[ConnectorStatus]:
    """Computes the configuration status of every connector, for `truesignal init`."""
    statuses = []
    for connector in connectors:
        configured = connector.is_configured()
        missing = list(connector.config_env_vars) if connector.requires_config and not configured else []
        statuses.append(
            ConnectorStatus(
                name=connector.name,
                label=connector.label,
                requires_config=connector.requires_config,
                configured=configured,
                missing_env_vars=missing,
            )
        )
    return statuses


def format_init_report(statuses: Sequence[ConnectorStatus]) -> str:
    """Human-readable report for `truesignal init`."""
    lines = ["truesignal connector status:", ""]
    for status in statuses:
        if not status.requires_config:
            lines.append(f"  [ready]        {status.label} ({status.name}) -- no configuration needed")
        elif status.configured:
            lines.append(f"  [ready]        {status.label} ({status.name}) -- configured")
        else:
            lines.append(
                f"  [not configured] {status.label} ({status.name}) -- set {', '.join(status.missing_env_vars)}"
            )
    ready_count = sum(1 for s in statuses if not s.requires_config or s.configured)
    lines.append("")
    lines.append(f"{ready_count}/{len(statuses)} connectors ready.")
    if ready_count == 0:
        lines.append(
            "No connectors are usable. This should not happen -- CISA-KEV and GDELT need no configuration."
        )
    else:
        if ready_count < len(statuses):
            lines.append("Set the missing environment variables above to enable the rest. See .env.example.")
        lines.append('Next: run "truesignal feed" to see your feed now.')
    return "\n".join(lines)


@dataclass(frozen=True)
class ConnectorSelection:
    #: Connectors to actually query.
    to_query: List[Connector]
    #: Connectors that exist but are not configured, skipped rather than failed on.
    skipped: List[Connector]
    #: Set if --source named a connector that does not exist.
    unknown_source: Optional[str] = None


def select_connectors(
    all_connectors: Sequence[Connector],
    source_filter: Optional[str] = None,
) -> ConnectorSelection:
    """
    Resolves which connectors `truesignal feed` should query, given an optional --source filter.
    Unconfigured connectors are skipped (reported, never crashed on); an unknown --source name is
    reported back as an error rather than silently ignored.
    """
    candidates = list(all_connectors)
    if source_filter:
        match = next((c for c in all_connectors if c.name == source_filter), None)
        if not match:
            return ConnectorSelection(to_query=[], skipped=[], unknown_source=source_filter)
        candidates = [match]
    to_query = [c for c in candidates if not c.requires_config or c.is_configured()]
    skipped = [c for c in candidates if c.requires_config and not c.is_configured()]
    return ConnectorSelection(to_query=to_query, skipped=skipped)


def _relative_age(timestamp: str, now: datetime) -> str:
    ms = (now - parse_iso8601(timestamp)).total_seconds() * 1000
    seconds = max(0, round(ms / 1000))
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"{minutes}m ago"
    hours = round(minutes / 60)
    if hours < 24:
        return f"{hours}h ago"
    days = round(hours / 24)
    return f"{days}d ago"


def _format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"{minutes}m"
    hours = round(minutes / 60)
    if hours < 24:
        return f"{hours}h"
    days = round(hours / 24)
    return f"{days}d"


_CONTROL_CHAR_PATTERN = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def _sanitize_for_terminal(text: str) -> str:
    """
    Strips control characters (C0/C1, DEL) from untrusted upstream text before it reaches a
    terminal. Reddit and Telegram content is attacker-controlled -- a crafted post title or
    message could otherwise carry ANSI/OSC escape sequences (cursor manipulation, terminal-title
    spoofing, an OSC-8 hyperlink escape that visually disguises the printed URL) straight into
    the user's terminal via `print`.
    """
    return _CONTROL_CHAR_PATTERN.sub("", text)


def format_feed_item_human(item: FeedItem, now: Optional[datetime] = None) -> str:
    """Formats one feed item as a single human-readable line."""
    now = now or datetime.now(timezone.utc)
    if item.status == "live":
        tag = "[live]"
    else:
        tag = f"[fallback, {_format_duration(item.fallback_age_seconds or 0)} old]"
    title = _sanitize_for_terminal(item.title)
    url = _sanitize_for_terminal(item.url)
    return f"{tag} {item.source}: {title} -- {url} -- {_relative_age(item.timestamp, now)}"


def parse_item_id(item_id: str) -> Optional[Tuple[str, str]]:
    """Splits a feed item id (`{source}:{native_id}`) into its source and native-id parts."""
    separator_index = item_id.find(":")
    if separator_index <= 0 or separator_index == len(item_id) - 1:
        return None
    return item_id[:separator_index], item_id[separator_index + 1 :]


@dataclass(frozen=True)
class ConnectorFailure:
    source: str
    error: str


@dataclass(frozen=True)
class FeedRunResult:
    items: List[FeedItem]
    skipped: List[str]
    failures: List[ConnectorFailure]
    unknown_source: Optional[str] = None

    def to_dict(self) -> Dict:
        data: Dict = {
            "items": [item.to_dict() for item in self.items],
            "skipped": self.skipped,
            "failures": [{"source": f.source, "error": f.error} for f in self.failures],
        }
        if self.unknown_source is not None:
            data["unknown_source"] = self.unknown_source
        return data


def run_feed(connectors: Sequence[Connector], source_filter: Optional[str] = None) -> FeedRunResult:
    """
    Runs `truesignal feed` end to end against real connectors: resolves which to query, fetches
    them concurrently, and never lets one connector's failure take down the others.
    """
    selection = select_connectors(connectors, source_filter)
    if selection.unknown_source:
        return FeedRunResult(items=[], skipped=[], failures=[], unknown_source=selection.unknown_source)

    items: List[FeedItem] = []
    failures: List[ConnectorFailure] = []

    if selection.to_query:
        # Preserve connector order in the aggregated output, same as Promise.allSettled's
        # index-ordered results in the TypeScript source.
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(selection.to_query)) as executor:
            futures = [executor.submit(connector.fetch_items) for connector in selection.to_query]
            for connector, future in zip(selection.to_query, futures):
                try:
                    items.extend(future.result())
                except Exception as error:  # noqa: BLE001 -- one connector's failure must not sink the others
                    failures.append(ConnectorFailure(source=connector.name, error=str(error)))

    return FeedRunResult(items=items, skipped=[c.name for c in selection.skipped], failures=failures)


VerifyErrorKind = str  # "invalid-id" | "unknown-source" | "not-configured" | "network-error"


@dataclass(frozen=True)
class VerifyResult:
    item_id: str
    found: bool
    status: Optional[ItemStatus] = None
    url: Optional[str] = None
    timestamp: Optional[str] = None
    fallback_age_seconds: Optional[int] = None
    error_kind: Optional[VerifyErrorKind] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict:
        data: Dict = {"item_id": self.item_id, "found": self.found}
        for key, value in (
            ("status", self.status),
            ("url", self.url),
            ("timestamp", self.timestamp),
            ("fallback_age_seconds", self.fallback_age_seconds),
            ("error_kind", self.error_kind),
            ("error_message", self.error_message),
        ):
            if value is not None:
                data[key] = value
        return data


def run_verify(connectors: Sequence[Connector], item_id: str) -> VerifyResult:
    """Re-fetches the named connector and confirms whether `item_id` still resolves to real data."""
    parsed = parse_item_id(item_id)
    if not parsed:
        return VerifyResult(
            item_id=item_id,
            found=False,
            error_kind="invalid-id",
            error_message=(
                f'Could not parse item id "{item_id}". Expected format: <source>:<native-id>, '
                f"e.g. cisa-kev:CVE-2026-12345"
            ),
        )
    source, _native_id = parsed

    connector = next((c for c in connectors if c.name == source), None)
    if not connector:
        known = ", ".join(c.name for c in connectors)
        return VerifyResult(
            item_id=item_id,
            found=False,
            error_kind="unknown-source",
            error_message=f'Unknown source "{source}" in item id "{item_id}". Known sources: {known}',
        )

    if connector.requires_config and not connector.is_configured():
        return VerifyResult(
            item_id=item_id,
            found=False,
            error_kind="not-configured",
            error_message=f'Connector "{connector.name}" is not configured. Run "truesignal init" to see what is needed.',
        )

    try:
        items = connector.fetch_items()
    except Exception as error:  # noqa: BLE001 -- mirrors src/cli-helpers.ts's catch-all around fetchItems()
        return VerifyResult(
            item_id=item_id,
            found=False,
            error_kind="network-error",
            error_message=f"Failed to verify: {error}",
        )

    found_item = next((item for item in items if item.id == item_id), None)
    if not found_item:
        return VerifyResult(item_id=item_id, found=False)

    return VerifyResult(
        item_id=item_id,
        found=True,
        status=found_item.status,
        url=found_item.url,
        timestamp=found_item.timestamp,
        fallback_age_seconds=found_item.fallback_age_seconds,
    )
