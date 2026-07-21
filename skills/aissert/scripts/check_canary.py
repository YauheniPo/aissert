#!/usr/bin/env python3
"""Judge regression check: compare fresh judge verdicts against the canary set.

The orchestrator runs both judges on every canary item's frozen input and saves
each judge output as <verdicts-dir>/<canary-item-id>.json; this script does the
deterministic comparison (contract: references/canary-schema.md).

Exit codes: 0 = canary passed, 1 = divergence (judges drifted, eval run is
invalid — fix the rubric, not the thresholds), 2 = pipeline/infra error.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from aggregate import (
    EXIT_GATE_FAILED,
    EXIT_PASS,
    EXIT_PIPELINE_ERROR,
    M1_VERDICTS,
    M2_VERDICTS,
    PipelineError,
    _load_json,
    _require_str,
)

JUDGE_KINDS = {
    "precision": ("fact_id", M1_VERDICTS),
    "recall": ("golden_fact_id", M2_VERDICTS),
}


@dataclass(frozen=True)
class CanaryItem:
    id: str
    judge: str
    borderline: bool
    expected: dict[str, str]  # verdict id -> expected verdict value


def _validate_expected(data: dict, id_key: str, allowed: set[str], ctx: str) -> dict[str, str]:
    verdicts = data.get("verdicts")
    if not isinstance(verdicts, list) or not verdicts:
        raise PipelineError(f"{ctx}: 'expected.verdicts' must be a non-empty array")
    expected: dict[str, str] = {}
    for idx, v in enumerate(verdicts):
        vctx = f"{ctx}: expected.verdicts[{idx}]"
        if not isinstance(v, dict):
            raise PipelineError(f"{vctx}: must be an object")
        vid = _require_str(v, id_key, vctx)
        if vid in expected:
            raise PipelineError(f"{ctx}: duplicate expected verdict for {vid!r}")
        verdict = v.get("verdict")
        if verdict not in allowed:
            raise PipelineError(
                f"{vctx}: verdict must be one of {sorted(allowed)}, got {verdict!r}"
            )
        expected[vid] = verdict
    return expected


def load_canary_item(path: Path) -> CanaryItem:
    ctx = f"canary item {path.name}"
    data = _load_json(path, ctx)
    item_id = _require_str(data, "id", ctx)
    if item_id != path.stem:
        raise PipelineError(f"{ctx}: id {item_id!r} does not match filename stem {path.stem!r}")
    judge = data.get("judge")
    if judge not in JUDGE_KINDS:
        raise PipelineError(f"{ctx}: 'judge' must be one of {sorted(JUDGE_KINDS)}, got {judge!r}")
    if data.get("reviewed") is not True:
        raise PipelineError(
            f"{ctx}: not hand-reviewed (reviewed != true) — an unreviewed canary "
            f"only tests the judge against itself; review 'expected' and set reviewed: true"
        )
    id_key, allowed = JUDGE_KINDS[judge]
    expected_block = data.get("expected")
    if not isinstance(expected_block, dict):
        raise PipelineError(f"{ctx}: 'expected' must be an object")
    expected = _validate_expected(expected_block, id_key, allowed, ctx)
    return CanaryItem(
        id=item_id, judge=judge, borderline=bool(data.get("borderline")), expected=expected
    )


def load_canary_set(canary_dir: Path) -> tuple[float, list[CanaryItem]]:
    manifest = _load_json(canary_dir / "manifest.json", "canary manifest")
    min_agreement = manifest.get("min_agreement")
    if not isinstance(min_agreement, (int, float)) or isinstance(min_agreement, bool) \
            or not 0 < min_agreement <= 1:
        raise PipelineError(
            f"canary manifest: min_agreement must be a number in (0, 1], got {min_agreement!r}"
        )
    item_files = sorted((canary_dir / "items").glob("*.json"))
    if not item_files:
        raise PipelineError(f"canary set: no item files in {canary_dir / 'items'}")
    items = [load_canary_item(f) for f in item_files]
    if len({i.id for i in items}) != len(items):
        raise PipelineError("canary set: duplicate item ids")
    return float(min_agreement), items


def compare_item(item: CanaryItem, actual_data: dict) -> list[str]:
    """Return mismatch descriptions for one canary item (empty = full agreement)."""
    id_key, allowed = JUDGE_KINDS[item.judge]
    ctx = f"actual verdicts for {item.id}"
    verdicts = actual_data.get("verdicts")
    if not isinstance(verdicts, list):
        raise PipelineError(f"{ctx}: 'verdicts' must be an array")
    actual: dict[str, str] = {}
    for idx, v in enumerate(verdicts):
        vctx = f"{ctx}: verdicts[{idx}]"
        if not isinstance(v, dict):
            raise PipelineError(f"{vctx}: must be an object")
        vid = _require_str(v, id_key, vctx)
        if vid in actual:
            raise PipelineError(f"{ctx}: duplicate verdict for {vid!r}")
        verdict = v.get("verdict")
        if verdict not in allowed:
            raise PipelineError(
                f"{vctx}: verdict must be one of {sorted(allowed)}, got {verdict!r}"
            )
        actual[vid] = verdict
    if set(actual) != set(item.expected):
        missing = sorted(set(item.expected) - set(actual))
        unknown = sorted(set(actual) - set(item.expected))
        raise PipelineError(
            f"{ctx}: verdict ids must match expected exactly; missing={missing} unknown={unknown}"
        )
    return [
        f"{item.id} [{item.judge}{', borderline' if item.borderline else ''}] "
        f"{vid}: expected {item.expected[vid]}, got {actual[vid]}"
        for vid in sorted(item.expected)
        if actual[vid] != item.expected[vid]
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare fresh judge verdicts against the hand-labeled canary set."
    )
    parser.add_argument("--canary-set", required=True, type=Path, help="canary set directory")
    parser.add_argument(
        "--verdicts-dir", required=True, type=Path,
        help="directory with one <canary-item-id>.json judge output per item",
    )
    args = parser.parse_args(argv)

    try:
        min_agreement, items = load_canary_set(args.canary_set)
        missing_files = [
            args.verdicts_dir / f"{item.id}.json"
            for item in items
            if not (args.verdicts_dir / f"{item.id}.json").is_file()
        ]
        if missing_files:
            listing = "\n".join(f"  {p}" for p in missing_files)
            raise PipelineError(f"missing judge outputs for canary items:\n{listing}")
        mismatches: list[str] = []
        total = 0
        for item in items:
            actual = _load_json(
                args.verdicts_dir / f"{item.id}.json", f"actual verdicts for {item.id}"
            )
            mismatches.extend(compare_item(item, actual))
            total += len(item.expected)
    except PipelineError as e:
        print(f"check_canary: pipeline error: {e}", file=sys.stderr)
        return EXIT_PIPELINE_ERROR

    agreement = (total - len(mismatches)) / total
    print(f"canary: {len(items)} items, {total} verdicts, "
          f"agreement={agreement:.4f} (min {min_agreement})")
    for m in mismatches:
        print(f"  MISMATCH {m}")
    if agreement < min_agreement:
        print(
            "check_canary: DIVERGENCE — judges no longer match the hand-labeled "
            "baseline; the eval run is invalid. Fix the rubric, not the thresholds.",
            file=sys.stderr,
        )
        return EXIT_GATE_FAILED
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
