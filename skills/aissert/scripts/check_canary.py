#!/usr/bin/env python3
"""Runtime-agent regression check against the reviewed canary set.

The orchestrator runs each judge on frozen facts and fact-extractor on small
synthetic raw outputs, then saves every result as
<verdicts-dir>/<canary-item-id>.json. This script validates the full artifact
contracts and performs deterministic grouped comparisons.

Exit codes: 0 = canary passed, 1 = runtime-agent divergence (eval run invalid),
2 = pipeline/infra error.
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
    SUPPORTED_OUTPUT_FACTS_VERDICTS,
    EXPECTED_OUTPUT_FACTS_VERDICTS,
    PipelineError,
    SCHEMA_VERSION,
    _load_json,
    _require_str,
    validate_facts,
    validate_supported_output_facts_verdicts,
    validate_expected_output_facts_verdicts,
)

JUDGE_KINDS = {
    "precision": ("fact_id", SUPPORTED_OUTPUT_FACTS_VERDICTS),
    "recall": ("reference_fact_id", EXPECTED_OUTPUT_FACTS_VERDICTS),
}


@dataclass(frozen=True)
class CanaryItem:
    id: str
    judge: str
    borderline: bool
    expected: dict[str, str]  # verdict id -> expected verdict value
    reference_fact_ids: tuple[str, ...]
    output_fact_ids: tuple[str, ...]


@dataclass(frozen=True)
class CanaryThresholds:
    overall: float
    by_judge: dict[str, float]
    non_borderline: float
    extractor: float


@dataclass(frozen=True)
class ExpectedExtractorFact:
    id: str
    type: str
    must_contain: tuple[str, ...]
    must_not_contain: tuple[str, ...]


@dataclass(frozen=True)
class ExtractorCanaryItem:
    id: str
    raw_output: str
    expected_facts: tuple[ExpectedExtractorFact, ...]
    must_not_contain: tuple[str, ...]


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


def _validate_reference_facts(facts: object, ctx: str) -> list[str]:
    if not isinstance(facts, list) or not facts:
        raise PipelineError(f"{ctx}: 'input.reference_facts' must be a non-empty array")
    ids: list[str] = []
    for idx, fact in enumerate(facts):
        fctx = f"{ctx}: input.reference_facts[{idx}]"
        if not isinstance(fact, dict):
            raise PipelineError(f"{fctx}: must be an object")
        ids.append(_require_str(fact, "id", fctx))
        _require_str(fact, "text", fctx)
    if len(set(ids)) != len(ids):
        raise PipelineError(f"{ctx}: duplicate input reference fact ids")
    return ids


def _validate_string_list(value: object, field: str, ctx: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise PipelineError(f"{ctx}: '{field}' must be an array")
    result: list[str] = []
    for idx, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise PipelineError(f"{ctx}: '{field}[{idx}]' must be a non-empty string")
        result.append(item)
    return tuple(result)


def load_canary_item(path: Path) -> CanaryItem:
    ctx = f"canary item {path.name}"
    data = _load_json(path, ctx)
    item_id = _require_str(data, "id", ctx)
    if item_id != path.stem:
        raise PipelineError(f"{ctx}: id {item_id!r} does not match filename stem {path.stem!r}")
    judge = data.get("judge")
    if judge not in JUDGE_KINDS:
        raise PipelineError(f"{ctx}: 'judge' must be one of {sorted(JUDGE_KINDS)}, got {judge!r}")
    borderline = data.get("borderline")
    if not isinstance(borderline, bool):
        raise PipelineError(f"{ctx}: 'borderline' must be a boolean")
    if data.get("reviewed") is not True:
        raise PipelineError(
            f"{ctx}: not hand-reviewed (reviewed != true) — an unreviewed canary "
            f"only tests the judge against itself; review 'expected' and set reviewed: true"
        )
    input_block = data.get("input")
    if not isinstance(input_block, dict):
        raise PipelineError(f"{ctx}: 'input' must be an object")
    reference_fact_ids = _validate_reference_facts(input_block.get("reference_facts"), ctx)
    output_facts = input_block.get("output_facts")
    output_fact_ids = validate_facts({"facts": output_facts}, f"{ctx}: input.output_facts")

    id_key, allowed = JUDGE_KINDS[judge]
    expected_block = data.get("expected")
    if not isinstance(expected_block, dict):
        raise PipelineError(f"{ctx}: 'expected' must be an object")
    expected = _validate_expected(expected_block, id_key, allowed, ctx)
    source_ids = output_fact_ids if judge == "precision" else reference_fact_ids
    if set(expected) != set(source_ids):
        missing = sorted(set(source_ids) - set(expected))
        unknown = sorted(set(expected) - set(source_ids))
        raise PipelineError(
            f"{ctx}: expected verdict ids must match frozen {judge} input exactly; "
            f"missing={missing} unknown={unknown}"
        )
    return CanaryItem(
        id=item_id,
        judge=judge,
        borderline=borderline,
        expected=expected,
        reference_fact_ids=tuple(reference_fact_ids),
        output_fact_ids=tuple(output_fact_ids),
    )


def load_extractor_canary_item(path: Path) -> ExtractorCanaryItem:
    ctx = f"extractor canary item {path.name}"
    data = _load_json(path, ctx)
    item_id = _require_str(data, "id", ctx)
    if item_id != path.stem:
        raise PipelineError(f"{ctx}: id {item_id!r} does not match filename stem {path.stem!r}")
    if data.get("reviewed") is not True:
        raise PipelineError(f"{ctx}: not hand-reviewed (reviewed != true)")
    raw_output = _require_str(data, "raw_output", ctx)
    expected = data.get("expected")
    if not isinstance(expected, dict):
        raise PipelineError(f"{ctx}: 'expected' must be an object")
    facts = expected.get("facts")
    if not isinstance(facts, list):
        raise PipelineError(f"{ctx}: 'expected.facts' must be an array")
    expected_facts: list[ExpectedExtractorFact] = []
    for idx, fact in enumerate(facts):
        fctx = f"{ctx}: expected.facts[{idx}]"
        if not isinstance(fact, dict):
            raise PipelineError(f"{fctx}: must be an object")
        expected_facts.append(
            ExpectedExtractorFact(
                id=_require_str(fact, "id", fctx),
                type=_require_str(fact, "type", fctx),
                must_contain=_validate_string_list(
                    fact.get("must_contain"), "must_contain", fctx
                ),
                must_not_contain=_validate_string_list(
                    fact.get("must_not_contain", []), "must_not_contain", fctx
                ),
            )
        )
    expected_ids = [fact.id for fact in expected_facts]
    if expected_ids != [f"f{i}" for i in range(1, len(expected_ids) + 1)]:
        raise PipelineError(f"{ctx}: expected fact ids must be sequential f1..fN")
    return ExtractorCanaryItem(
        id=item_id,
        raw_output=raw_output,
        expected_facts=tuple(expected_facts),
        must_not_contain=_validate_string_list(
            expected.get("must_not_contain", []),
            "must_not_contain",
            f"{ctx}: expected",
        ),
    )


def _require_agreement(value: object, name: str, ctx: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not 0 < value <= 1
    ):
        raise PipelineError(f"{ctx}: {name} must be a number in (0, 1], got {value!r}")
    return float(value)


def load_canary_set(
    canary_dir: Path,
) -> tuple[CanaryThresholds, list[CanaryItem], list[ExtractorCanaryItem]]:
    manifest = _load_json(canary_dir / "manifest.json", "canary manifest")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise PipelineError(
            f"canary manifest: schema_version must be {SCHEMA_VERSION}, "
            f"got {manifest.get('schema_version')!r}"
        )
    overall = _require_agreement(
        manifest.get("min_agreement"), "min_agreement", "canary manifest"
    )
    by_judge_raw = manifest.get("min_agreement_by_judge", {})
    if not isinstance(by_judge_raw, dict):
        raise PipelineError("canary manifest: min_agreement_by_judge must be an object")
    unknown_judges = set(by_judge_raw) - set(JUDGE_KINDS)
    if unknown_judges:
        raise PipelineError(
            f"canary manifest: unknown min_agreement_by_judge keys "
            f"{sorted(unknown_judges)}"
        )
    by_judge = {
        judge: _require_agreement(
            by_judge_raw.get(judge, overall),
            f"min_agreement_by_judge.{judge}",
            "canary manifest",
        )
        for judge in JUDGE_KINDS
    }
    non_borderline = _require_agreement(
        manifest.get("min_non_borderline_agreement", 1.0),
        "min_non_borderline_agreement",
        "canary manifest",
    )
    extractor = _require_agreement(
        manifest.get("min_extractor_agreement", 1.0),
        "min_extractor_agreement",
        "canary manifest",
    )
    item_files = sorted((canary_dir / "items").glob("*.json"))
    if not item_files:
        raise PipelineError(f"canary set: no item files in {canary_dir / 'items'}")
    items = [load_canary_item(f) for f in item_files]
    if len({i.id for i in items}) != len(items):
        raise PipelineError("canary set: duplicate item ids")
    extractor_files = sorted((canary_dir / "extractor-items").glob("*.json"))
    extractor_items = [load_extractor_canary_item(f) for f in extractor_files]
    all_ids = [i.id for i in items] + [i.id for i in extractor_items]
    if len(set(all_ids)) != len(all_ids):
        raise PipelineError("canary set: duplicate ids across judge and extractor items")
    return (
        CanaryThresholds(
            overall=overall,
            by_judge=by_judge,
            non_borderline=non_borderline,
            extractor=extractor,
        ),
        items,
        extractor_items,
    )


def compare_item(item: CanaryItem, actual_data: dict) -> list[str]:
    """Return mismatch descriptions for one canary item (empty = full agreement)."""
    ctx = f"actual verdicts for {item.id}"
    if item.judge == "precision":
        validate_supported_output_facts_verdicts(actual_data, list(item.output_fact_ids), ctx)
        id_key = "fact_id"
    else:
        validate_expected_output_facts_verdicts(
            actual_data,
            list(item.reference_fact_ids),
            list(item.output_fact_ids),
            ctx,
        )
        id_key = "reference_fact_id"
    actual = {v[id_key]: v["verdict"] for v in actual_data["verdicts"]}
    return [
        f"{item.id} [{item.judge}{', borderline' if item.borderline else ''}] "
        f"{vid}: expected {item.expected[vid]}, got {actual[vid]}"
        for vid in sorted(item.expected)
        if actual[vid] != item.expected[vid]
    ]


def compare_extractor_item(
    item: ExtractorCanaryItem, actual_data: dict
) -> list[str]:
    """Return structural/content-anchor mismatches for one extractor canary item."""
    ctx = f"actual extractor facts for {item.id}"
    actual_ids = validate_facts(actual_data, ctx)
    expected_ids = [fact.id for fact in item.expected_facts]
    if actual_ids != expected_ids:
        return [
            f"{item.id} [extractor] expected fact ids {expected_ids}, got {actual_ids}"
        ]
    mismatches: list[str] = []
    actual_facts = actual_data["facts"]
    for expected, actual in zip(item.expected_facts, actual_facts, strict=True):
        if actual["type"] != expected.type:
            mismatches.append(
                f"{item.id} [extractor] {expected.id}: expected type "
                f"{expected.type!r}, got {actual['type']!r}"
            )
        folded = actual["text"].casefold()
        for required in expected.must_contain:
            if required.casefold() not in folded:
                mismatches.append(
                    f"{item.id} [extractor] {expected.id}: text lacks required "
                    f"substring {required!r}"
                )
        for forbidden in expected.must_not_contain:
            if forbidden.casefold() in folded:
                mismatches.append(
                    f"{item.id} [extractor] {expected.id}: text contains forbidden "
                    f"substring {forbidden!r}"
                )
    all_text = "\n".join(fact["text"] for fact in actual_facts).casefold()
    for forbidden in item.must_not_contain:
        if forbidden.casefold() in all_text:
            mismatches.append(
                f"{item.id} [extractor]: output contains forbidden substring "
                f"{forbidden!r}"
            )
    return mismatches


def _agreement(total: int, mismatches: int) -> float:
    return (total - mismatches) / total if total else 1.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare fresh runtime-agent outputs against the reviewed canary set."
    )
    parser.add_argument("--canary-set", required=True, type=Path, help="canary set directory")
    parser.add_argument(
        "--verdicts-dir", required=True, type=Path,
        help="directory with one <canary-item-id>.json runtime-agent output per item",
    )
    args = parser.parse_args(argv)

    try:
        thresholds, items, extractor_items = load_canary_set(args.canary_set)
        all_ids = [item.id for item in items] + [item.id for item in extractor_items]
        missing_files = [
            args.verdicts_dir / f"{item_id}.json"
            for item_id in all_ids
            if not (args.verdicts_dir / f"{item_id}.json").is_file()
        ]
        if missing_files:
            listing = "\n".join(f"  {p}" for p in missing_files)
            raise PipelineError(f"missing runtime-agent outputs for canary items:\n{listing}")
        mismatches: list[str] = []
        total = 0
        totals_by_judge = {judge: 0 for judge in JUDGE_KINDS}
        mismatches_by_judge = {judge: 0 for judge in JUDGE_KINDS}
        non_borderline_total = 0
        non_borderline_mismatches = 0
        for item in items:
            actual = _load_json(
                args.verdicts_dir / f"{item.id}.json", f"actual verdicts for {item.id}"
            )
            item_mismatches = compare_item(item, actual)
            mismatches.extend(item_mismatches)
            total += len(item.expected)
            totals_by_judge[item.judge] += len(item.expected)
            mismatches_by_judge[item.judge] += len(item_mismatches)
            if not item.borderline:
                non_borderline_total += len(item.expected)
                non_borderline_mismatches += len(item_mismatches)
        extractor_mismatched_items = 0
        for item in extractor_items:
            actual = _load_json(
                args.verdicts_dir / f"{item.id}.json",
                f"actual extractor facts for {item.id}",
            )
            item_mismatches = compare_extractor_item(item, actual)
            mismatches.extend(item_mismatches)
            if item_mismatches:
                extractor_mismatched_items += 1
    except PipelineError as e:
        print(f"check_canary: pipeline error: {e}", file=sys.stderr)
        return EXIT_PIPELINE_ERROR

    judge_mismatch_count = sum(mismatches_by_judge.values())
    agreement = _agreement(total, judge_mismatch_count)
    print(
        f"canary: {len(items)} judge items, {total} verdicts, "
        f"agreement={agreement:.4f} (min {thresholds.overall})"
    )
    gate_results = [agreement >= thresholds.overall]
    for judge in JUDGE_KINDS:
        judge_agreement = _agreement(
            totals_by_judge[judge], mismatches_by_judge[judge]
        )
        print(
            f"  {judge}: agreement={judge_agreement:.4f} "
            f"(min {thresholds.by_judge[judge]})"
        )
        gate_results.append(judge_agreement >= thresholds.by_judge[judge])
    non_borderline_agreement = _agreement(
        non_borderline_total, non_borderline_mismatches
    )
    print(
        f"  non-borderline: agreement={non_borderline_agreement:.4f} "
        f"(min {thresholds.non_borderline})"
    )
    gate_results.append(non_borderline_agreement >= thresholds.non_borderline)
    extractor_agreement = _agreement(
        len(extractor_items), extractor_mismatched_items
    )
    print(
        f"  extractor: {len(extractor_items)} items, "
        f"agreement={extractor_agreement:.4f} (min {thresholds.extractor})"
    )
    gate_results.append(extractor_agreement >= thresholds.extractor)
    for m in mismatches:
        print(f"  MISMATCH {m}")
    if not all(gate_results):
        print(
            "check_canary: DIVERGENCE — runtime agents no longer match the "
            "hand-labeled baseline; the eval run is invalid. Inspect the affected "
            "agent rubric and frozen case before changing thresholds.",
            file=sys.stderr,
        )
        return EXIT_GATE_FAILED
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
