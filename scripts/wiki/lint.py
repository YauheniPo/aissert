#!/usr/bin/env python3
"""Wiki structural lint. Ported from a sibling project's scripts/wiki/lint.js.

Usage: python3 scripts/wiki/lint.py
Exit codes: 0 = no structural issues, 1 = at least one issue (see payload.issues).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import collect_wiki_health, summarize_health


def main() -> int:
    health = collect_wiki_health()
    summary = summarize_health(health)

    ok = (
        summary["frontmatter_errors"] == 0
        and not summary["stale_pages"]
        and summary["invalid_validated_commits"] == 0
        and summary["broken_source_paths"] == 0
        and summary["broken_links"] == 0
        and summary["missing_index_entries"] == 0
        and summary["orphan_pages"] == 0
    )

    payload = {"ok": ok, "summary": summary, "issues": health["issues"]}
    print(json.dumps(payload, indent=2))

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
