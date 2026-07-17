#!/usr/bin/env python3
"""
03 -- agent-native JSON.

The agent-native use case: call truesignal fully in-process (no CLI subprocess), serialize
structured FeedItems to JSON the way an agent framework would consume them, then use
run_verify() to re-confirm a specific item's provenance by item id. Runs standalone with no
setup beyond `pip install -e .` -- CISA-KEV needs no API key.

Run:
    python3 examples/03-agent-native-json/agent_report.py
"""
import json

from truesignal import get_connector
from truesignal.cli_helpers import run_verify


def main() -> None:
    cisa_kev = get_connector("cisa-kev")
    assert cisa_kev is not None
    items = cisa_kev.fetch_items()

    report = {"source": "cisa-kev", "item_count": len(items), "items": [item.to_dict() for item in items[:3]]}
    print(json.dumps(report, indent=2))

    if items:
        target_id = items[0].id
        print()
        print(f"Re-verifying {target_id} via run_verify() ...")
        result = run_verify([cisa_kev], target_id)
        print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
