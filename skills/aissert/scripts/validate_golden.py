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
    parser.add_argument(
        "--target-skill",
        default=None,
        help="expected manifest target_skill; catches passing a set for the wrong skill",
    )
    args = parser.parse_args(argv)

    try:
        golden = load_golden_set(args.golden_set)
        if args.target_skill is not None and golden.target_skill != args.target_skill:
            raise PipelineError(
                f"target_skill mismatch: manifest has {golden.target_skill!r}, "
                f"command requested {args.target_skill!r}"
            )
    except PipelineError as e:
        print(f"validate_golden: invalid golden set: {e}", file=sys.stderr)
        return EXIT_PIPELINE_ERROR

    total_facts = sum(len(item.reference_fact_ids) for item in golden.items)
    print(f"golden set: {args.golden_set}")
    print(f"target_skill: {golden.target_skill}")
    print(f"set_version: {golden.set_version}")
    print(f"items: {len(golden.items)}, reference facts: {total_facts}")
    print(
        f"defaults: min_supported_to_total_output_facts_ratio={golden.defaults_min_supported_to_total_output_facts_ratio} "
        f"min_covered_to_total_reference_facts_ratio={golden.defaults_min_covered_to_total_reference_facts_ratio}"
    )
    print(f"hash: {golden.hash}")
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
