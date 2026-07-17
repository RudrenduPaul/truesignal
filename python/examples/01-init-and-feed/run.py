#!/usr/bin/env python3
"""
01 -- init and feed.

The simplest possible use of the truesignal library: check which connectors are ready
(`is_configured()`), then pull a real live feed from the zero-configuration `cisa-kev` connector.
Runs standalone with no setup beyond `pip install -e .` (or `pip install truesignal`) from the
python/ directory -- CISA-KEV needs no API key.

Run:
    python3 examples/01-init-and-feed/run.py
"""
from truesignal import ALL_CONNECTORS, get_connector


def main() -> None:
    print("Connector status:")
    for connector in ALL_CONNECTORS:
        ready = not connector.requires_config or connector.is_configured()
        state = "ready" if ready else "not configured"
        print(f"  [{state}] {connector.label} ({connector.name})")

    print()
    print("Pulling the real live feed from cisa-kev (no API key required)...")
    cisa_kev = get_connector("cisa-kev")
    assert cisa_kev is not None
    items = cisa_kev.fetch_items()

    print(f"{len(items)} item(s) returned.")
    for item in items[:5]:
        print(f"  [{item.status}] {item.title}")
        print(f"      {item.url}")


if __name__ == "__main__":
    main()
