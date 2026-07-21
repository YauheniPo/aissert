#!/usr/bin/env python3
"""Validate a golden set directory and print its hash.

Fail-fast gate before any eval run (SKILL.md step 1). Reuses the loader from
aggregate.py so validation and aggregation can never disagree on the contract
(skills/aissert/references/golden-set-schema.md).

Exit codes: 0 = valid, 2 = invalid or unreadable.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aggregate import EXIT_PASS, EXIT_PIPELINE_ERROR, PipelineError, load_golden_set


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a golden set directory against golden-set-schema.md."
    )
    parser.add_argument("golden_set", type=Path, help="golden set directory")
    args = parser.parse_args(argv)

    try:
        golden = load_golden_set(args.golden_set)
    except PipelineError as e:
        print(f"validate_golden: invalid golden set: {e}", file=sys.stderr)
        return EXIT_PIPELINE_ERROR

    total_facts = sum(len(item.golden_fact_ids) for item in golden.items)
    print(f"golden set: {args.golden_set}")
    print(f"target_skill: {golden.target_skill}")
    print(f"set_version: {golden.set_version}")
    print(f"items: {len(golden.items)}, golden facts: {total_facts}")
    print(f"defaults: k1={golden.defaults_k1} k2={golden.defaults_k2}")
    print(f"hash: {golden.hash}")
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
