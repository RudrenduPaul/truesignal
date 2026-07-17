#!/usr/bin/env python3
"""
truesignal CLI entry point. This module is deliberately thin -- it wires argparse's argument
parsing to the testable logic in cli_helpers.py and returns process exit codes. See ExitCode in
cli_helpers.py for what each code means.

Ported from src/truesignal/cli.ts (which uses `commander`); this port uses the stdlib `argparse`
to avoid a CLI-framework dependency. Console entry point: `truesignal <command> [options]`,
installed via the `truesignal` console-script defined in python/pyproject.toml.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from .cli_helpers import (
    ExitCode,
    format_feed_item_human,
    format_init_report,
    get_connector_statuses,
    run_feed,
    run_verify,
)
from .connectors import ALL_CONNECTORS

_VERSION = "0.1.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="truesignal",
        description=(
            "A provenance-first OSINT/security intelligence feed. Every item carries a real "
            "source URL, a real timestamp, and an explicit live/fallback flag -- never a "
            "fabricated or silently-replayed data point."
        ),
    )
    parser.add_argument("--version", "-V", action="version", version=f"truesignal-cli {_VERSION}")

    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser(
        "init",
        help=(
            "Check which connectors are ready to use right now and which environment variables "
            "are still needed for the rest. CISA-KEV and GDELT need no configuration -- "
            "truesignal works with zero setup for those two sources."
        ),
    )
    init_parser.add_argument(
        "--json", action="store_true", help="print machine-readable JSON instead of a human-readable report"
    )

    feed_parser = subparsers.add_parser(
        "feed",
        help=(
            "Pull the current feed from every configured connector, or one connector with "
            "--source. Prints human-readable output by default; use --json for a stable, "
            "agent-parseable schema."
        ),
    )
    feed_parser.add_argument("--source", default=None, help="only pull from this connector, e.g. cisa-kev, gdelt")
    feed_parser.add_argument("--json", action="store_true", help="print machine-readable JSON instead of human-readable text")

    verify_parser = subparsers.add_parser(
        "verify",
        help=(
            "Re-fetch the source connector named in <item-id> and confirm whether that item "
            "still resolves to real, live provenance, has fallen back to cached data, or can no "
            "longer be found."
        ),
    )
    verify_parser.add_argument("item_id", help="a feed item id from `truesignal feed`, e.g. cisa-kev:CVE-2026-12345")
    verify_parser.add_argument("--json", action="store_true", help="print machine-readable JSON instead of human-readable text")

    return parser


def run_cli(argv: List[str]) -> int:
    """
    `argv` follows the sys.argv convention: argv[0] is the program name, the real arguments start
    at argv[1]. Returns the process exit code.
    """
    parser = build_parser()
    args = parser.parse_args(argv[1:])

    if args.command == "init":
        return _run_init(json_output=args.json)
    if args.command == "feed":
        return _run_feed(source=args.source, json_output=args.json)
    if args.command == "verify":
        return _run_verify(item_id=args.item_id, json_output=args.json)

    parser.print_help()
    return ExitCode.SUCCESS


def _run_init(json_output: bool) -> int:
    statuses = get_connector_statuses(ALL_CONNECTORS)
    if json_output:
        print(
            json.dumps(
                {
                    "connectors": [
                        {
                            "name": s.name,
                            "label": s.label,
                            "requires_config": s.requires_config,
                            "configured": s.configured,
                            "missing_env_vars": s.missing_env_vars,
                        }
                        for s in statuses
                    ]
                },
                indent=2,
            )
        )
    else:
        print(format_init_report(statuses))
    ready_count = sum(1 for s in statuses if not s.requires_config or s.configured)
    return ExitCode.SUCCESS if ready_count > 0 else ExitCode.NO_CONNECTORS_CONFIGURED


def _run_feed(source: Optional[str], json_output: bool) -> int:
    result = run_feed(ALL_CONNECTORS, source)

    if result.unknown_source:
        known = ", ".join(c.name for c in ALL_CONNECTORS)
        sys.stderr.write(f'Unknown source "{result.unknown_source}". Known sources: {known}\n')
        return ExitCode.GENERAL_ERROR

    if not result.items and result.skipped and not result.failures:
        if json_output:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            sys.stderr.write(
                f"No connectors are configured to run. Missing: {', '.join(result.skipped)}. "
                f'Run "truesignal init" to see what\'s needed.\n'
            )
        return ExitCode.NO_CONNECTORS_CONFIGURED

    if json_output:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        if result.skipped:
            print(f"Skipped (not configured): {', '.join(result.skipped)}")
        if not result.items:
            print("No items returned.")
        for item in result.items:
            print(format_feed_item_human(item))
        for failure in result.failures:
            sys.stderr.write(f"{failure.source}: {failure.error}\n")

    if not result.items and result.failures:
        return ExitCode.NETWORK_ERROR
    return ExitCode.SUCCESS


def _run_verify(item_id: str, json_output: bool) -> int:
    result = run_verify(ALL_CONNECTORS, item_id)

    if json_output:
        print(json.dumps(result.to_dict(), indent=2))
    elif result.error_message:
        sys.stderr.write(f"{result.error_message}\n")
    elif result.found:
        if result.status == "live":
            provenance = "LIVE"
        else:
            provenance = f"FALLBACK ({result.fallback_age_seconds or 0}s old cached data)"
        print(f"{item_id}: {provenance} -- {result.url} -- {result.timestamp}")
    else:
        print(f"{item_id}: not found in the current feed (it may have rolled off, or never existed).")

    if result.error_kind in ("invalid-id", "unknown-source"):
        return ExitCode.INVALID_ITEM_ID
    if result.error_kind == "not-configured":
        return ExitCode.NO_CONNECTORS_CONFIGURED
    if result.error_kind == "network-error":
        return ExitCode.NETWORK_ERROR
    if not result.found:
        return ExitCode.GENERAL_ERROR
    return ExitCode.SUCCESS


def main() -> None:
    try:
        code = run_cli(sys.argv)
    except SystemExit:
        raise
    except Exception as error:  # noqa: BLE001 -- top-level crash guard, mirrors src/cli.ts's catch-all
        sys.stderr.write(f"{error}\n")
        sys.exit(ExitCode.GENERAL_ERROR)
    else:
        sys.exit(code)


if __name__ == "__main__":
    main()
