#!/usr/bin/env python3
"""Significant-change detector. Ported from a sibling project's scripts/wiki/changed.js.

Usage: python3 scripts/wiki/changed.py
Always exits 0 — this is a report, not a gate; read `significant_change` in
the JSON payload.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import analyze_significant_change, get_changed_files, load_wiki_pages


def main() -> int:
    changed_files = get_changed_files()
    pages = load_wiki_pages()
    result = analyze_significant_change(changed_files, pages)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
