#!/usr/bin/env python3
"""
02 -- CI gate.

Using truesignal's library API as a CI gate: pulls the real live feed from the zero-configuration
`gdelt` connector and exits non-zero if the fetch produced neither live nor fallback data (i.e.
the upstream fetch failed and there was nothing to fall back to). Suitable to drop into a CI
script directly -- see docs/integrations/ci.md for a full GitHub Actions example.

Note: GDELT's public API enforces a documented rate limit (roughly one request per 5 seconds per
client) -- if this script is run in tight succession with other GDELT calls, the connector will
honestly report the failure via its no-fabrication fallback behavior rather than invent data.

Run:
    python3 examples/02-ci-gate/gate.py
"""
import sys

from truesignal import get_connector


def main() -> int:
    gdelt = get_connector("gdelt")
    assert gdelt is not None
    items = gdelt.fetch_items()

    if not items:
        print("GATE FAILED: gdelt returned no items (upstream fetch failed, no fallback data).", file=sys.stderr)
        return 1

    live_count = sum(1 for item in items if item.status == "live")
    fallback_count = len(items) - live_count
    print(f"GATE PASSED: {len(items)} item(s) ({live_count} live, {fallback_count} fallback).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
