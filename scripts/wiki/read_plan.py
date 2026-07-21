#!/usr/bin/env python3
"""Read-plan resolver. Ported from a sibling project's scripts/wiki/read-plan.js.

Usage:
  python3 scripts/wiki/read_plan.py                 # uses current git changes
  python3 scripts/wiki/read_plan.py <path> [<path>...]  # explicit file list
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import analyze_significant_change, get_changed_files, get_read_plan, load_wiki_pages


def main() -> int:
    args = [a.strip() for a in sys.argv[1:] if a.strip()]
    changed_files = args if args else get_changed_files()
    pages = load_wiki_pages()
    significant = analyze_significant_change(changed_files, pages)

    payload = {
        "changed_files": sorted(changed_files),
        "significant_change": significant["significant_change"],
        "pages_to_read": get_read_plan(changed_files),
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
