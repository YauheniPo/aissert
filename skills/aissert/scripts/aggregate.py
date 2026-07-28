#!/usr/bin/env python3
"""Deterministic aggregation for aissert eval runs.

Reads fact-extractor and judge outputs from an eval-run directory, computes
precision (m1) and recall (m2) per run, aggregates across iterations, applies
the min_supported_to_total_output_facts_ratio/min_covered_to_total_reference_facts_ratio gates and writes results.json plus report.md.

All scoring math, aggregation and verdicts live here — never in an LLM.

Contracts: skills/aissert/references/golden-set-schema.md and
skills/aissert/references/results-schema.md.

Exit codes: 0 = gate passed, 1 = gate failed, 2 = pipeline/infra error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = 4

EXIT_PASS = 0
EXIT_GATE_FAILED = 1
EXIT_PIPELINE_ERROR = 2

WEIGHT_SUM_TOLERANCE = 1e-9
SANITY_MEDIAN_FACTOR = 3  # a run with count*3 < item median is a pipeline failure

M1_VERDICTS = {"supported", "unsupported"}
M2_VERDICTS = {"covered", "missing"}


class PipelineError(Exception):
    """Contract violation or infra failure — exit 2, numbers not trustworthy."""


@dataclass(frozen=True)
class GoldenItem:
    id: str
    snapshot: str
    reference_fact_ids: tuple[str, ...]
    weights: dict[str, float]


@dataclass(frozen=True)
class GoldenSet:
    path: Path
    target_skill: str
    set_version: str
    owner: str
    defaults_min_supported_to_total_output_facts_ratio: float
    defaults_min_covered_to_total_reference_facts_ratio: float
    items: tuple[GoldenItem, ...]
    hash: str


@dataclass(frozen=True)
class RunMetrics:
    item_id: str
    iteration: int
    supported: int
    unsupported: int
    total_output_facts: int
    covered: int
    missing: int
    total_reference_facts: int
    m1: float
    m2: float
    verbosity_ratio: float


# ---------------------------------------------------------------- loading


def _load_json(path: Path, ctx: str) -> dict:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        raise PipelineError(f"{ctx}: cannot read {path}: {e}") from e
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise PipelineError(f"{ctx}: invalid JSON in {path}: {e}") from e
    if not isinstance(data, dict):
        raise PipelineError(
            f"{ctx}: expected a JSON object in {path}, got {type(data).__name__}"
        )
    return data


def _require_str(data: dict, key: str, ctx: str, *, non_empty: bool = True) -> str:
    value = data.get(key)
    if not isinstance(value, str) or (non_empty and not value.strip()):
        raise PipelineError(f"{ctx}: field '{key}' must be a non-empty string")
    return value


def _require_threshold(value: object, name: str, ctx: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise PipelineError(f"{ctx}: {name} must be a number, got {value!r}")
    if not 0.0 <= value <= 1.0:
        raise PipelineError(f"{ctx}: {name} must be in [0, 1], got {value}")
    return float(value)


def golden_set_hash(golden_dir: Path) -> str:
    """SHA-256 over manifest.json + sorted items/*.json (see golden-set-schema.md)."""
    files = [golden_dir / "manifest.json"]
    files += sorted((golden_dir / "items").glob("*.json"))
    h = hashlib.sha256()
    for f in files:
        h.update(f.relative_to(golden_dir).as_posix().encode("utf-8"))
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return "sha256:" + h.hexdigest()


def _validate_golden_item(data: dict, path: Path) -> GoldenItem:
    ctx = f"golden item {path.name}"
    item_id = _require_str(data, "id", ctx)
    if item_id != path.stem:
        raise PipelineError(f"{ctx}: id {item_id!r} does not match filename stem {path.stem!r}")

    input_block = data.get("input")
    if not isinstance(input_block, dict):
        raise PipelineError(f"{ctx}: 'input' must be an object")
    _require_str(input_block, "type", f"{ctx}: input")
    snapshot = _require_str(input_block, "snapshot", f"{ctx}: input")

    reference = data.get("reference")
    if not isinstance(reference, dict):
        raise PipelineError(f"{ctx}: 'reference' must be an object")
    reference_facts = reference.get("reference_facts")
    if not isinstance(reference_facts, list) or not reference_facts:
        raise PipelineError(f"{ctx}: 'reference.reference_facts' must be a non-empty array")

    fact_ids: list[str] = []
    for idx, fact in enumerate(reference_facts):
        fctx = f"{ctx}: reference_facts[{idx}]"
        if not isinstance(fact, dict):
            raise PipelineError(f"{fctx}: must be an object")
        fact_ids.append(_require_str(fact, "id", fctx))
        _require_str(fact, "text", fctx)
    if len(set(fact_ids)) != len(fact_ids):
        raise PipelineError(f"{ctx}: duplicate reference fact ids")

    weights_raw = data.get("weights")
    if not isinstance(weights_raw, dict):
        raise PipelineError(f"{ctx}: 'weights' must be an object (use {{}} for uniform)")
    weights: dict[str, float] = {}
    if weights_raw:
        if set(weights_raw) != set(fact_ids):
            raise PipelineError(
                f"{ctx}: non-empty weights keys must be exactly the reference fact ids"
            )
        for gid, w in weights_raw.items():
            if not isinstance(w, (int, float)) or isinstance(w, bool) or not 0 < w <= 1:
                raise PipelineError(f"{ctx}: weight for {gid!r} must be a number in (0, 1]")
            weights[gid] = float(w)
        total = sum(weights.values())
        if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
            raise PipelineError(f"{ctx}: weights must sum to 1.0, got {total}")

    return GoldenItem(
        id=item_id, snapshot=snapshot, reference_fact_ids=tuple(fact_ids), weights=weights
    )


def load_golden_set(golden_dir: Path) -> GoldenSet:
    manifest = _load_json(golden_dir / "manifest.json", "golden set manifest")
    ctx = "golden set manifest"
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise PipelineError(
            f"{ctx}: schema_version must be {SCHEMA_VERSION}, "
            f"got {manifest.get('schema_version')!r}"
        )
    target_skill = _require_str(manifest, "target_skill", ctx)
    set_version = _require_str(manifest, "set_version", ctx)
    owner = _require_str(manifest, "owner", ctx)
    defaults = manifest.get("defaults")
    if not isinstance(defaults, dict):
        raise PipelineError(
            f"{ctx}: 'defaults' must be an object with min_supported_to_total_output_facts_ratio/min_covered_to_total_reference_facts_ratio"
        )
    min_supported_to_total_output_facts_ratio = _require_threshold(
        defaults.get("min_supported_to_total_output_facts_ratio"), "defaults.min_supported_to_total_output_facts_ratio", ctx
    )
    min_covered_to_total_reference_facts_ratio = _require_threshold(defaults.get("min_covered_to_total_reference_facts_ratio"), "defaults.min_covered_to_total_reference_facts_ratio", ctx)

    items_dir = golden_dir / "items"
    item_files = sorted(items_dir.glob("*.json"))
    if not item_files:
        raise PipelineError(f"golden set: no item files in {items_dir}")

    items: list[GoldenItem] = []
    seen: set[str] = set()
    for f in item_files:
        item = _validate_golden_item(_load_json(f, f"golden item {f.name}"), f)
        if item.id in seen:
            raise PipelineError(f"golden set: duplicate item id {item.id!r}")
        seen.add(item.id)
        items.append(item)

    return GoldenSet(
        path=golden_dir,
        target_skill=target_skill,
        set_version=set_version,
        owner=owner,
        defaults_min_supported_to_total_output_facts_ratio=min_supported_to_total_output_facts_ratio,
        defaults_min_covered_to_total_reference_facts_ratio=min_covered_to_total_reference_facts_ratio,
        items=tuple(items),
        hash=golden_set_hash(golden_dir),
    )


# ---------------------------------------------------- artifact validation


def validate_facts(data: dict, ctx: str) -> list[str]:
    """Validate a facts.json payload; return output fact ids (may be empty)."""
    facts = data.get("facts")
    if not isinstance(facts, list):
        raise PipelineError(f"{ctx}: 'facts' must be an array")
    ids: list[str] = []
    for idx, fact in enumerate(facts):
        fctx = f"{ctx}: facts[{idx}]"
        if not isinstance(fact, dict):
            raise PipelineError(f"{fctx}: must be an object")
        ids.append(_require_str(fact, "id", fctx))
        _require_str(fact, "type", fctx)
        _require_str(fact, "text", fctx)
    if len(set(ids)) != len(ids):
        raise PipelineError(f"{ctx}: duplicate fact ids")
    return ids


def _validate_verdict_list(
    data: dict, id_key: str, expected_ids: list[str], allowed: set[str], ctx: str
) -> dict[str, dict]:
    """Common shell: verdicts must cover expected_ids exactly, verdict in allowed."""
    verdicts = data.get("verdicts")
    if not isinstance(verdicts, list):
        raise PipelineError(f"{ctx}: 'verdicts' must be an array")
    by_id: dict[str, dict] = {}
    for idx, v in enumerate(verdicts):
        vctx = f"{ctx}: verdicts[{idx}]"
        if not isinstance(v, dict):
            raise PipelineError(f"{vctx}: must be an object")
        vid = _require_str(v, id_key, vctx)
        if vid in by_id:
            raise PipelineError(f"{ctx}: duplicate verdict for {id_key} {vid!r}")
        verdict = v.get("verdict")
        if verdict not in allowed:
            raise PipelineError(
                f"{vctx}: verdict must be one of {sorted(allowed)}, got {verdict!r}"
            )
        by_id[vid] = v
    expected = set(expected_ids)
    if set(by_id) != expected:
        missing = sorted(expected - set(by_id))
        unknown = sorted(set(by_id) - expected)
        raise PipelineError(
            f"{ctx}: verdict ids must match exactly; missing={missing} unknown={unknown}"
        )
    return by_id


def validate_verdicts_m1(data: dict, fact_ids: list[str], ctx: str) -> int:
    """Validate judge-supported-output-facts output; return the supported count."""
    by_id = _validate_verdict_list(data, "fact_id", fact_ids, M1_VERDICTS, ctx)
    for vid, v in by_id.items():
        _require_str(v, "evidence", f"{ctx}: verdict for {vid!r}")
    return sum(1 for v in by_id.values() if v["verdict"] == "supported")


def validate_verdicts_m2(
    data: dict, reference_ids: list[str], fact_ids: list[str], ctx: str
) -> set[str]:
    """Validate judge-expected-output-facts output; return covered reference fact ids."""
    by_id = _validate_verdict_list(data, "reference_fact_id", reference_ids, M2_VERDICTS, ctx)
    known_facts = set(fact_ids)
    covered: set[str] = set()
    for gid, v in by_id.items():
        covered_by = v.get("covered_by")
        if v["verdict"] == "covered":
            if not isinstance(covered_by, str) or covered_by not in known_facts:
                raise PipelineError(
                    f"{ctx}: covered reference fact {gid!r} must reference an output "
                    f"fact id via 'covered_by', got {covered_by!r}"
                )
            covered.add(gid)
        elif covered_by is not None:
            raise PipelineError(
                f"{ctx}: missing reference fact {gid!r} must not set 'covered_by'"
            )
    return covered


# ------------------------------------------------------------ computation


def extraction_sanity_check(fact_counts: dict[tuple[str, int], int]) -> list[str]:
    """Return problems: runs with 0 facts or count*3 < item median (DESIGN.md §4)."""
    by_item: dict[str, dict[int, int]] = {}
    for (item_id, iteration), count in fact_counts.items():
        by_item.setdefault(item_id, {})[iteration] = count
    problems: list[str] = []
    for item_id in sorted(by_item):
        counts = by_item[item_id]
        median = statistics.median(counts.values())
        for iteration in sorted(counts):
            count = counts[iteration]
            if count == 0:
                problems.append(f"{item_id}/{iteration}: 0 output facts")
            elif count * SANITY_MEDIAN_FACTOR < median:
                problems.append(
                    f"{item_id}/{iteration}: {count} output facts is below 1/3 "
                    f"of the item median ({median})"
                )
    return problems


def compute_run_metrics(
    item: GoldenItem,
    iteration: int,
    total_output_facts: int,
    supported: int,
    covered_ids: set[str],
) -> RunMetrics:
    if total_output_facts <= 0:
        raise PipelineError(
            f"{item.id}/{iteration}: cannot compute m1 with 0 output facts"
        )
    total_reference_facts = len(item.reference_fact_ids)
    if total_reference_facts <= 0:
        raise PipelineError(f"{item.id}/{iteration}: golden item has no reference facts")
    if item.weights:
        m2 = sum(item.weights[gid] for gid in covered_ids)
    else:
        m2 = len(covered_ids) / total_reference_facts
    return RunMetrics(
        item_id=item.id,
        iteration=iteration,
        supported=supported,
        unsupported=total_output_facts - supported,
        total_output_facts=total_output_facts,
        covered=len(covered_ids),
        missing=total_reference_facts - len(covered_ids),
        total_reference_facts=total_reference_facts,
        m1=supported / total_output_facts,
        m2=m2,
        verbosity_ratio=total_output_facts / total_reference_facts,
    )


def summarize(runs: list[RunMetrics], min_supported_to_total_output_facts_ratio: float, min_covered_to_total_reference_facts_ratio: float) -> dict:
    if not runs:
        raise PipelineError("no runs to aggregate")

    def stats(values: list[float]) -> dict:
        return {
            "mean": statistics.fmean(values),
            "stddev": statistics.stdev(values) if len(values) >= 2 else 0.0,
        }

    m1_stats = stats([r.m1 for r in runs])
    m2_stats = stats([r.m2 for r in runs])
    gates = {
        "m1": {
            "mean": m1_stats["mean"],
            "threshold": min_supported_to_total_output_facts_ratio,
            "pass": m1_stats["mean"] >= min_supported_to_total_output_facts_ratio,
        },
        "m2": {
            "mean": m2_stats["mean"],
            "threshold": min_covered_to_total_reference_facts_ratio,
            "pass": m2_stats["mean"] >= min_covered_to_total_reference_facts_ratio,
        },
    }
    return {
        "summary": {
            "m1": m1_stats,
            "m2": m2_stats,
            "verbosity_ratio_mean": statistics.fmean(r.verbosity_ratio for r in runs),
        },
        "gates": gates,
        "verdict": "pass" if gates["m1"]["pass"] and gates["m2"]["pass"] else "fail",
    }


# ---------------------------------------------------------------- pipeline


def _artifact_paths(run_dir: Path, item_id: str, iteration: int) -> tuple[Path, Path, Path]:
    return (
        run_dir / "facts" / item_id / f"{iteration}.json",
        run_dir / "verdicts" / item_id / f"{iteration}-m1.json",
        run_dir / "verdicts" / item_id / f"{iteration}-m2.json",
    )


def collect_runs(run_dir: Path, golden: GoldenSet, iterations: int) -> list[RunMetrics]:
    expected: list[tuple[GoldenItem, int]] = [
        (item, i) for item in golden.items for i in range(1, iterations + 1)
    ]
    missing = [
        p
        for item, i in expected
        for p in _artifact_paths(run_dir, item.id, i)
        if not p.is_file()
    ]
    if missing:
        listing = "\n".join(f"  {p}" for p in missing)
        raise PipelineError(
            f"missing run artifacts (resume: re-run only these, then re-aggregate):\n{listing}"
        )

    # Pass 1: facts + sanity check before touching any verdicts — garbage
    # extraction is a pipeline failure, not a skill failure.
    fact_ids_by_run: dict[tuple[str, int], list[str]] = {}
    for item, i in expected:
        facts_path, _, _ = _artifact_paths(run_dir, item.id, i)
        ctx = f"facts {item.id}/{i}"
        fact_ids_by_run[(item.id, i)] = validate_facts(_load_json(facts_path, ctx), ctx)

    problems = extraction_sanity_check(
        {key: len(ids) for key, ids in fact_ids_by_run.items()}
    )
    if problems:
        listing = "\n".join(f"  {p}" for p in problems)
        raise PipelineError(f"extraction sanity check failed:\n{listing}")

    # Pass 2: verdicts + metrics.
    runs: list[RunMetrics] = []
    for item, i in expected:
        _, m1_path, m2_path = _artifact_paths(run_dir, item.id, i)
        fact_ids = fact_ids_by_run[(item.id, i)]
        m1_ctx = f"verdicts {item.id}/{i}-m1"
        m2_ctx = f"verdicts {item.id}/{i}-m2"
        supported = validate_verdicts_m1(_load_json(m1_path, m1_ctx), fact_ids, m1_ctx)
        covered = validate_verdicts_m2(
            _load_json(m2_path, m2_ctx), list(item.reference_fact_ids), fact_ids, m2_ctx
        )
        runs.append(compute_run_metrics(item, i, len(fact_ids), supported, covered))
    runs.sort(key=lambda r: (r.item_id, r.iteration))
    return runs


def resolve_thresholds(
    cli_min_supported_to_total_output_facts_ratio: float | None, cli_min_covered_to_total_reference_facts_ratio: float | None, golden: GoldenSet
) -> tuple[float, float, dict[str, str]]:
    min_supported_to_total_output_facts_ratio = (
        golden.defaults_min_supported_to_total_output_facts_ratio
        if cli_min_supported_to_total_output_facts_ratio is None
        else _require_threshold(cli_min_supported_to_total_output_facts_ratio, "min_supported_to_total_output_facts_ratio", "cli")
    )
    min_covered_to_total_reference_facts_ratio = (
        golden.defaults_min_covered_to_total_reference_facts_ratio
        if cli_min_covered_to_total_reference_facts_ratio is None
        else _require_threshold(cli_min_covered_to_total_reference_facts_ratio, "min_covered_to_total_reference_facts_ratio", "cli")
    )
    source = {
        "min_supported_to_total_output_facts_ratio": "manifest" if cli_min_supported_to_total_output_facts_ratio is None else "cli",
        "min_covered_to_total_reference_facts_ratio": "manifest" if cli_min_covered_to_total_reference_facts_ratio is None else "cli",
    }
    return min_supported_to_total_output_facts_ratio, min_covered_to_total_reference_facts_ratio, source


def build_results(
    golden: GoldenSet,
    runs: list[RunMetrics],
    min_supported_to_total_output_facts_ratio: float,
    min_covered_to_total_reference_facts_ratio: float,
    threshold_source: dict[str, str],
    iterations: int,
    model_id: str | None,
) -> dict:
    aggregate = summarize(runs, min_supported_to_total_output_facts_ratio, min_covered_to_total_reference_facts_ratio)
    return {
        "schema_version": SCHEMA_VERSION,
        "target_skill": golden.target_skill,
        "golden_set": {
            "path": str(golden.path),
            "hash": golden.hash,
            "set_version": golden.set_version,
            "owner": golden.owner,
        },
        "model_id": model_id,
        "iterations": iterations,
        "thresholds": {
            "min_supported_to_total_output_facts_ratio": min_supported_to_total_output_facts_ratio,
            "min_covered_to_total_reference_facts_ratio": min_covered_to_total_reference_facts_ratio,
            "source": threshold_source,
        },
        "runs": [
            {
                "item_id": r.item_id,
                "iteration": r.iteration,
                "m1": {
                    "supported": r.supported,
                    "unsupported": r.unsupported,
                    "total_output_facts": r.total_output_facts,
                    "value": r.m1,
                },
                "m2": {
                    "covered": r.covered,
                    "missing": r.missing,
                    "total_reference_facts": r.total_reference_facts,
                    "value": r.m2,
                },
                "verbosity_ratio": r.verbosity_ratio,
            }
            for r in runs
        ],
        **aggregate,
    }


def build_report(results: dict) -> str:
    """Build a compact Markdown summary for humans; results.json remains canonical."""
    lines = [
        "# aissert evaluation report",
        "",
        f"Verdict: **{results['verdict'].upper()}**",
        f"Target skill: `{results['target_skill']}`",
        f"Golden set: `{results['golden_set']['path']}`",
        f"Golden hash: `{results['golden_set']['hash']}`",
        f"Owner: `{results['golden_set']['owner']}`",
        f"Iterations: {results['iterations']}",
        "",
        "## Gates",
        "",
        "| Metric | Mean | Stddev | Threshold | Result |",
        "|---|---:|---:|---:|---|",
    ]
    for metric in ("m1", "m2"):
        gate = results["gates"][metric]
        stats = results["summary"][metric]
        status = "pass" if gate["pass"] else "fail"
        lines.append(
            f"| {metric} | {gate['mean']:.4f} | {stats['stddev']:.4f} | "
            f"{gate['threshold']:.4f} | {status} |"
        )
    lines.extend(
        [
            "",
            f"Verbosity ratio mean: {results['summary']['verbosity_ratio_mean']:.4f}",
            "",
            "## Runs",
            "",
            "| Item | Iteration | m1 | m2 | Output Facts | Reference Facts | Verbosity |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for run in results["runs"]:
        lines.append(
            f"| {run['item_id']} | {run['iteration']} | "
            f"{run['m1']['value']:.4f} | {run['m2']['value']:.4f} | "
            f"{run['m1']['total_output_facts']} | {run['m2']['total_reference_facts']} | "
            f"{run['verbosity_ratio']:.4f} |"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate aissert eval-run artifacts into results.json and a gate exit code."
    )
    parser.add_argument("--run-dir", required=True, type=Path, help="eval-run directory")
    parser.add_argument("--golden-set", required=True, type=Path, help="golden set directory")
    parser.add_argument("--iterations", required=True, type=int, help="iterations per item (1-based files)")
    parser.add_argument("--min-supported-to-total-output-facts-ratio", type=float, default=None, help="min mean precision; overrides manifest")
    parser.add_argument("--min-covered-to-total-reference-facts-ratio", type=float, default=None, help="min mean recall; overrides manifest")
    parser.add_argument("--model-id", default=None, help="target-skill model id, recorded in results.json")
    args = parser.parse_args(argv)

    try:
        if args.iterations < 1:
            raise PipelineError(f"--iterations must be >= 1, got {args.iterations}")
        golden = load_golden_set(args.golden_set)
        min_supported_to_total_output_facts_ratio, min_covered_to_total_reference_facts_ratio, source = resolve_thresholds(
            args.min_supported_to_total_output_facts_ratio, args.min_covered_to_total_reference_facts_ratio, golden
        )
        runs = collect_runs(args.run_dir, golden, args.iterations)
        results = build_results(
            golden, runs, min_supported_to_total_output_facts_ratio, min_covered_to_total_reference_facts_ratio, source, args.iterations, args.model_id
        )
        results_path = args.run_dir / "results.json"
        results_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        report_path = args.run_dir / "report.md"
        report_path.write_text(build_report(results), encoding="utf-8")
    except PipelineError as e:
        print(f"aggregate: pipeline error: {e}", file=sys.stderr)
        return EXIT_PIPELINE_ERROR

    print(f"verdict: {results['verdict'].upper()}")
    for metric in ("m1", "m2"):
        gate = results["gates"][metric]
        stats = results["summary"][metric]
        print(
            f"{metric}: mean={gate['mean']:.4f} stddev={stats['stddev']:.4f} "
            f"threshold={gate['threshold']:.2f} -> {'ok' if gate['pass'] else 'FAIL'}"
        )
    print(f"results: {results_path}")
    print(f"report: {report_path}")
    return EXIT_PASS if results["verdict"] == "pass" else EXIT_GATE_FAILED


if __name__ == "__main__":
    sys.exit(main())
