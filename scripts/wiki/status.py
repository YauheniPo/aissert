#!/usr/bin/env python3
"""Wiki health summary. Ported from a sibling project's scripts/wiki/status.js.

Usage: python3 scripts/wiki/status.py [--fail-on-stale-critical]
Exit codes: 0 always, unless --fail-on-stale-critical and a critical page is stale (1).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import collect_wiki_health, get_changed_files, summarize_health

# Pages whose drift breaks something operational (calibration, CI, gates) —
# not just narration. Mirrors the source project's hand-picked hotspot list.
CRITICAL_PAGES = {
    "knowledge/hotspots/aggregate-py.md",
    "knowledge/hotspots/judges-and-canary.md",
    "knowledge/repo/build-test-and-ci.md",
}


def main() -> int:
    fail_on_stale_critical = "--fail-on-stale-critical" in sys.argv[1:]

    health = collect_wiki_health()
    summary = summarize_health(health)
    changed_files = get_changed_files()
    critical_stale_pages = sorted(
        {item["page"] for item in health["issues"]["stale_pages"] if item["page"] in CRITICAL_PAGES}
    )

    payload = {
        "summary": summary,
        "critical_stale_pages": critical_stale_pages,
        "changed_files_count": len(changed_files),
    }
    print(json.dumps(payload))

    if fail_on_stale_critical and critical_stale_pages:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
