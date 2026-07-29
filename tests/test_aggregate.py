"""Unit tests for aggregate.py — verdict logic, validation, sanity checks, exit codes.

All fixtures are synthetic (data boundary rule: no corporate data in this repo).
"""
import json

import pytest

import aggregate
from aggregate import (
    EXIT_GATE_FAILED,
    EXIT_PASS,
    EXIT_PIPELINE_ERROR,
    GoldenItem,
    PipelineError,
    compute_run_metrics,
    extraction_sanity_check,
    golden_set_hash,
    load_golden_set,
    summarize,
    validate_facts,
    validate_supported_output_facts_verdicts,
    validate_expected_output_facts_verdicts,
)

# ---------------------------------------------------------------- helpers


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def golden_item_payload(item_id, n_facts, weights=None):
    return {
        "id": item_id,
        "input": {"type": "text", "snapshot": "synthetic input"},
        "reference": {
            "reference_facts": [
                {"id": f"gf{k}", "text": f"golden fact {k}"}
                for k in range(1, n_facts + 1)
            ]
        },
        "weights": weights or {},
    }


def make_golden(tmp_path, items, min_supported_to_total_output_facts_ratio=0.8, min_covered_to_total_reference_facts_ratio=0.7):
    gdir = tmp_path / "golden"
    write_json(
        gdir / "manifest.json",
        {
            "schema_version": aggregate.SCHEMA_VERSION,
            "target_skill": "demo-skill",
            "set_version": "1.0.0",
            "owner": "test",
            "defaults": {"min_supported_to_total_output_facts_ratio": min_supported_to_total_output_facts_ratio, "min_covered_to_total_reference_facts_ratio": min_covered_to_total_reference_facts_ratio},
        },
    )
    for item in items:
        write_json(gdir / "items" / f"{item['id']}.json", item)
    return gdir


def facts_payload(n_facts):
    return {
        "facts": [
            {"id": f"f{k}", "type": "claim", "text": f"extracted fact {k}"}
            for k in range(1, n_facts + 1)
        ]
    }


def supported_output_facts_payload(n_facts, n_supported):
    return {
        "verdicts": [
            {
                "fact_id": f"f{k}",
                "verdict": "supported" if k <= n_supported else "unsupported",
                "evidence": f"evidence {k}",
            }
            for k in range(1, n_facts + 1)
        ]
    }


def expected_output_facts_payload(n_golden, covered_ids, covered_by="f1"):
    verdicts = []
    for k in range(1, n_golden + 1):
        gid = f"gf{k}"
        if gid in covered_ids:
            verdicts.append(
                {
                    "reference_fact_id": gid,
                    "verdict": "covered",
                    "covered_by": covered_by,
                    "evidence": f"{covered_by} covers {gid}",
                }
            )
        else:
            verdicts.append(
                {
                    "reference_fact_id": gid,
                    "verdict": "missing",
                    "evidence": f"no output fact covers {gid}",
                }
            )
    return {"verdicts": verdicts}


def write_run(run_dir, item_id, iteration, n_facts, n_supported, n_golden, covered_ids):
    raw_path = run_dir / "runs" / item_id / f"{iteration}.md"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text("synthetic raw output", encoding="utf-8")
    write_json(run_dir / "facts" / item_id / f"{iteration}.json", facts_payload(n_facts))
    write_json(
        run_dir / "verdicts" / item_id / f"{iteration}-supported-output-facts.json",
        supported_output_facts_payload(n_facts, n_supported),
    )
    write_json(
        run_dir / "verdicts" / item_id / f"{iteration}-expected-output-facts.json",
        expected_output_facts_payload(n_golden, covered_ids),
    )


def item(n_golden=4, weights=None, item_id="gs-001"):
    return GoldenItem(
        id=item_id,
        snapshot="synthetic input",
        reference_fact_ids=tuple(f"gf{k}" for k in range(1, n_golden + 1)),
        weights=weights or {},
    )


# ---------------------------------------------------- compute_run_metrics


def test_supported_and_covered_ratios_computation():
    r = compute_run_metrics(item(n_golden=4), 1, total_output_facts=10, supported=8,
                            covered_ids={"gf1", "gf2", "gf3"})
    assert r.supported_to_total_output_facts_ratio == 0.8
    assert r.covered_to_total_reference_facts_ratio == 0.75
    assert r.unsupported == 2
    assert r.missing == 1
    assert r.verbosity_ratio == 2.5


def test_weighted_covered_to_total_reference_facts_ratio():
    weights = {"gf1": 0.7, "gf2": 0.1, "gf3": 0.1, "gf4": 0.1}
    r = compute_run_metrics(item(weights=weights), 1, total_output_facts=5, supported=5,
                            covered_ids={"gf1"})
    assert r.covered_to_total_reference_facts_ratio == pytest.approx(0.7)
    assert r.covered == 1
    assert r.missing == 3


def test_zero_output_facts_is_pipeline_error():
    with pytest.raises(PipelineError, match="0 output facts"):
        compute_run_metrics(item(), 1, total_output_facts=0, supported=0, covered_ids=set())


def test_zero_reference_facts_is_pipeline_error():
    empty = GoldenItem(id="gs-x", snapshot="s", reference_fact_ids=(), weights={})
    with pytest.raises(PipelineError, match="no reference facts"):
        compute_run_metrics(empty, 1, total_output_facts=5, supported=5, covered_ids=set())


# --------------------------------------------------------------- summarize


def test_verdict_pass_at_exact_thresholds():
    runs = [compute_run_metrics(item(n_golden=10), 1, 10, 8, {f"gf{k}" for k in range(1, 8)})]
    result = summarize(runs, min_supported_to_total_output_facts_ratio=0.8, min_covered_to_total_reference_facts_ratio=0.7)
    assert result["verdict"] == "pass"
    assert result["gates"]["supported_to_total_output_facts_ratio"]["pass"] and result["gates"]["covered_to_total_reference_facts_ratio"]["pass"]


def test_verdict_fail_on_supported_to_total_output_facts_ratio_only():
    runs = [compute_run_metrics(item(n_golden=10), 1, 10, 7, {f"gf{k}" for k in range(1, 11)})]
    result = summarize(runs, min_supported_to_total_output_facts_ratio=0.8, min_covered_to_total_reference_facts_ratio=0.7)
    assert result["verdict"] == "fail"
    assert not result["gates"]["supported_to_total_output_facts_ratio"]["pass"]
    assert result["gates"]["covered_to_total_reference_facts_ratio"]["pass"]


def test_verdict_fail_on_covered_to_total_reference_facts_ratio_only():
    runs = [compute_run_metrics(item(n_golden=10), 1, 10, 10, {"gf1", "gf2"})]
    result = summarize(runs, min_supported_to_total_output_facts_ratio=0.8, min_covered_to_total_reference_facts_ratio=0.7)
    assert result["verdict"] == "fail"
    assert result["gates"]["supported_to_total_output_facts_ratio"]["pass"]
    assert not result["gates"]["covered_to_total_reference_facts_ratio"]["pass"]


def test_mean_and_stddev_across_runs():
    it = item(n_golden=4)
    runs = [
        compute_run_metrics(it, 1, 10, 6, {"gf1", "gf2"}),   # supported_to_total_output_facts_ratio=0.6 covered_to_total_reference_facts_ratio=0.5
        compute_run_metrics(it, 2, 10, 10, {"gf1", "gf2", "gf3", "gf4"}),  # supported_to_total_output_facts_ratio=1.0 covered_to_total_reference_facts_ratio=1.0
    ]
    result = summarize(runs, min_supported_to_total_output_facts_ratio=0.8, min_covered_to_total_reference_facts_ratio=0.7)
    assert result["summary"]["supported_to_total_output_facts_ratio"]["mean"] == pytest.approx(0.8)
    assert result["summary"]["covered_to_total_reference_facts_ratio"]["mean"] == pytest.approx(0.75)
    assert result["summary"]["supported_to_total_output_facts_ratio"]["stddev"] == pytest.approx(0.2828, abs=1e-4)
    assert result["verdict"] == "pass"  # gate is on the mean, inclusive


def test_stddev_zero_for_single_run():
    runs = [compute_run_metrics(item(), 1, 5, 5, {"gf1"})]
    result = summarize(runs, min_supported_to_total_output_facts_ratio=0.5, min_covered_to_total_reference_facts_ratio=0.1)
    assert result["summary"]["supported_to_total_output_facts_ratio"]["stddev"] == 0.0
    assert result["summary"]["covered_to_total_reference_facts_ratio"]["stddev"] == 0.0


def test_within_item_stability_does_not_confuse_item_difficulty_with_drift():
    easy = item(n_golden=2, item_id="easy")
    hard = item(n_golden=2, item_id="hard")
    runs = [
        compute_run_metrics(easy, 1, 2, 2, {"gf1", "gf2"}),
        compute_run_metrics(easy, 2, 2, 2, {"gf1", "gf2"}),
        compute_run_metrics(hard, 1, 2, 1, {"gf1"}),
        compute_run_metrics(hard, 2, 2, 1, {"gf1"}),
    ]
    result = summarize(
        runs,
        min_supported_to_total_output_facts_ratio=0.5,
        min_covered_to_total_reference_facts_ratio=0.5,
    )
    assert result["summary"]["supported_to_total_output_facts_ratio"]["stddev"] > 0
    assert result["summary"]["covered_to_total_reference_facts_ratio"]["stddev"] > 0
    assert result["summary"]["within_item_stability"]["supported_to_total_output_facts_ratio"]["stddev_max"] == 0
    assert result["summary"]["within_item_stability"]["covered_to_total_reference_facts_ratio"]["stddev_max"] == 0


def test_summarize_empty_runs_is_pipeline_error():
    with pytest.raises(PipelineError, match="no runs"):
        summarize([], min_supported_to_total_output_facts_ratio=0.8, min_covered_to_total_reference_facts_ratio=0.7)


# ------------------------------------------------- extraction sanity check


def test_sanity_flags_zero_facts():
    problems = extraction_sanity_check({("gs-001", 1): 0, ("gs-001", 2): 9})
    assert problems == ["gs-001/1: 0 output facts"]


def test_sanity_flags_below_third_of_median():
    problems = extraction_sanity_check(
        {("gs-001", 1): 9, ("gs-001", 2): 9, ("gs-001", 3): 2}
    )
    assert len(problems) == 1
    assert "gs-001/3" in problems[0]


def test_sanity_boundary_exactly_third_of_median_passes():
    # median 6, count 2 -> 2*3 == 6, not strictly below -> ok
    problems = extraction_sanity_check(
        {("gs-001", 1): 6, ("gs-001", 2): 6, ("gs-001", 3): 2}
    )
    assert problems == []


def test_sanity_median_is_per_item():
    # gs-002's small counts must not drag down gs-001's median
    problems = extraction_sanity_check(
        {("gs-001", 1): 30, ("gs-001", 2): 30, ("gs-002", 1): 3, ("gs-002", 2): 3}
    )
    assert problems == []


# ------------------------------------------------------ artifact validation


def test_validate_facts_ok_and_empty():
    assert validate_facts(facts_payload(3), "ctx") == ["f1", "f2", "f3"]
    assert validate_facts({"facts": []}, "ctx") == []


def test_validate_facts_duplicate_ids():
    payload = {"facts": [{"id": "f1", "type": "t", "text": "a"},
                         {"id": "f1", "type": "t", "text": "b"}]}
    with pytest.raises(PipelineError, match="duplicate fact ids"):
        validate_facts(payload, "ctx")


def test_validate_facts_missing_field():
    with pytest.raises(PipelineError, match="'text'"):
        validate_facts({"facts": [{"id": "f1", "type": "t"}]}, "ctx")


def test_supported_output_facts_missing_fact_id():
    payload = supported_output_facts_payload(3, 3)
    payload["verdicts"].pop()
    with pytest.raises(PipelineError, match="missing=\\['f3'\\]"):
        validate_supported_output_facts_verdicts(payload, ["f1", "f2", "f3"], "ctx")


def test_supported_output_facts_unknown_fact_id():
    payload = supported_output_facts_payload(3, 3)
    with pytest.raises(PipelineError, match="unknown=\\['f3'\\]"):
        validate_supported_output_facts_verdicts(payload, ["f1", "f2"], "ctx")


def test_supported_output_facts_duplicate_fact_id():
    payload = {"verdicts": [
        {"fact_id": "f1", "verdict": "supported", "evidence": "e"},
        {"fact_id": "f1", "verdict": "unsupported", "evidence": "e"},
    ]}
    with pytest.raises(PipelineError, match="duplicate verdict"):
        validate_supported_output_facts_verdicts(payload, ["f1"], "ctx")


def test_supported_output_facts_invalid_verdict_value():
    payload = {"verdicts": [{"fact_id": "f1", "verdict": "maybe", "evidence": "e"}]}
    with pytest.raises(PipelineError, match="'maybe'"):
        validate_supported_output_facts_verdicts(payload, ["f1"], "ctx")


def test_supported_output_facts_numeric_score_rejected():
    payload = {"verdicts": [{"fact_id": "f1", "verdict": 0.9, "evidence": "e"}]}
    with pytest.raises(PipelineError):
        validate_supported_output_facts_verdicts(payload, ["f1"], "ctx")


def test_supported_output_facts_requires_evidence():
    payload = {"verdicts": [{"fact_id": "f1", "verdict": "supported", "evidence": ""}]}
    with pytest.raises(PipelineError, match="'evidence'"):
        validate_supported_output_facts_verdicts(payload, ["f1"], "ctx")


def test_supported_output_facts_counts_supported():
    assert validate_supported_output_facts_verdicts(supported_output_facts_payload(5, 3), [f"f{k}" for k in range(1, 6)], "ctx") == 3


def test_expected_output_facts_covered_requires_known_covered_by():
    payload = {"verdicts": [
        {
            "reference_fact_id": "gf1",
            "verdict": "covered",
            "covered_by": "f99",
            "evidence": "f99",
        }
    ]}
    with pytest.raises(PipelineError, match="covered_by"):
        validate_expected_output_facts_verdicts(payload, ["gf1"], ["f1"], "ctx")


def test_expected_output_facts_covered_without_covered_by():
    payload = {"verdicts": [
        {"reference_fact_id": "gf1", "verdict": "covered", "evidence": "f1"}
    ]}
    with pytest.raises(PipelineError, match="covered_by"):
        validate_expected_output_facts_verdicts(payload, ["gf1"], ["f1"], "ctx")


def test_expected_output_facts_missing_must_not_set_covered_by():
    payload = {"verdicts": [
        {
            "reference_fact_id": "gf1",
            "verdict": "missing",
            "covered_by": "f1",
            "evidence": "not covered",
        }
    ]}
    with pytest.raises(PipelineError, match="must not set"):
        validate_expected_output_facts_verdicts(payload, ["gf1"], ["f1"], "ctx")


def test_expected_output_facts_requires_evidence():
    payload = {"verdicts": [
        {"reference_fact_id": "gf1", "verdict": "missing"}
    ]}
    with pytest.raises(PipelineError, match="'evidence'"):
        validate_expected_output_facts_verdicts(payload, ["gf1"], ["f1"], "ctx")


def test_expected_output_facts_returns_covered_ids():
    covered = validate_expected_output_facts_verdicts(
        expected_output_facts_payload(3, {"gf1", "gf3"}), ["gf1", "gf2", "gf3"], ["f1"], "ctx"
    )
    assert covered == {"gf1", "gf3"}


# ------------------------------------------------------------- golden set


def test_load_golden_set_ok(tmp_path):
    gdir = make_golden(tmp_path, [golden_item_payload("gs-001", 4)])
    golden = load_golden_set(gdir)
    assert golden.target_skill == "demo-skill"
    assert golden.owner == "test"
    assert golden.defaults_min_supported_to_total_output_facts_ratio == 0.8
    assert golden.items[0].reference_fact_ids == ("gf1", "gf2", "gf3", "gf4")
    assert golden.hash.startswith("sha256:")


def test_golden_manifest_schema_version_required(tmp_path):
    gdir = make_golden(tmp_path, [golden_item_payload("gs-001", 2)])
    manifest = json.loads((gdir / "manifest.json").read_text())
    manifest["schema_version"] = aggregate.SCHEMA_VERSION + 1
    write_json(gdir / "manifest.json", manifest)
    with pytest.raises(PipelineError, match="schema_version"):
        load_golden_set(gdir)


def test_golden_manifest_owner_required(tmp_path):
    gdir = make_golden(tmp_path, [golden_item_payload("gs-001", 2)])
    manifest = json.loads((gdir / "manifest.json").read_text())
    manifest.pop("owner")
    write_json(gdir / "manifest.json", manifest)
    with pytest.raises(PipelineError, match="'owner'"):
        load_golden_set(gdir)


def test_golden_weights_must_sum_to_one(tmp_path):
    weights = {"gf1": 0.5, "gf2": 0.6}
    gdir = make_golden(tmp_path, [golden_item_payload("gs-001", 2, weights=weights)])
    with pytest.raises(PipelineError, match="sum to 1.0"):
        load_golden_set(gdir)


def test_golden_weights_keys_must_match_fact_ids(tmp_path):
    weights = {"gf1": 0.5, "gf9": 0.5}
    gdir = make_golden(tmp_path, [golden_item_payload("gs-001", 2, weights=weights)])
    with pytest.raises(PipelineError, match="exactly the reference fact ids"):
        load_golden_set(gdir)


def test_golden_empty_reference_facts_rejected(tmp_path):
    payload = golden_item_payload("gs-001", 1)
    payload["reference"]["reference_facts"] = []
    gdir = make_golden(tmp_path, [payload])
    with pytest.raises(PipelineError, match="non-empty array"):
        load_golden_set(gdir)


def test_golden_missing_snapshot_rejected(tmp_path):
    payload = golden_item_payload("gs-001", 2)
    payload["input"] = {"type": "text", "snapshot": ""}
    gdir = make_golden(tmp_path, [payload])
    with pytest.raises(PipelineError, match="snapshot"):
        load_golden_set(gdir)


def test_golden_id_must_match_filename(tmp_path):
    gdir = make_golden(tmp_path, [golden_item_payload("gs-001", 2)])
    write_json(gdir / "items" / "gs-002.json", golden_item_payload("gs-001", 2))
    with pytest.raises(PipelineError, match="does not match filename"):
        load_golden_set(gdir)


def test_golden_threshold_out_of_range(tmp_path):
    gdir = make_golden(tmp_path, [golden_item_payload("gs-001", 2)], min_supported_to_total_output_facts_ratio=1.5)
    with pytest.raises(PipelineError, match=r"\[0, 1\]"):
        load_golden_set(gdir)


def test_hash_changes_when_item_changes(tmp_path):
    gdir = make_golden(tmp_path, [golden_item_payload("gs-001", 2)])
    h1 = golden_set_hash(gdir)
    write_json(gdir / "items" / "gs-001.json", golden_item_payload("gs-001", 3))
    assert golden_set_hash(gdir) != h1


# ---------------------------------------------------------- main / e2e


def make_passing_layout(tmp_path, iterations=2):
    """1 item, 4 golden facts; each run: supported_to_total_output_facts_ratio = 4/5 = 0.8, covered_to_total_reference_facts_ratio = 3/4 = 0.75."""
    gdir = make_golden(tmp_path, [golden_item_payload("gs-001", 4)])
    run_dir = tmp_path / "run"
    for i in range(1, iterations + 1):
        write_run(run_dir, "gs-001", i, n_facts=5, n_supported=4, n_golden=4,
                  covered_ids={"gf1", "gf2", "gf3"})
    return gdir, run_dir


def base_args(gdir, run_dir, iterations=2):
    return ["--run-dir", str(run_dir), "--golden-set", str(gdir),
            "--iterations", str(iterations)]


def test_main_pass_writes_results(tmp_path, capsys):
    gdir, run_dir = make_passing_layout(tmp_path)
    code = aggregate.main(base_args(gdir, run_dir) + ["--model-id", "test-model"])
    assert code == EXIT_PASS

    results = json.loads((run_dir / "results.json").read_text())
    assert results["verdict"] == "pass"
    assert results["target_skill"] == "demo-skill"
    assert results["model_id"] == "test-model"
    assert results["iterations"] == 2
    assert results["golden_set"]["hash"].startswith("sha256:")
    assert results["golden_set"]["owner"] == "test"
    assert results["thresholds"] == {
        "min_supported_to_total_output_facts_ratio": 0.8, "min_covered_to_total_reference_facts_ratio": 0.7,
        "source": {"min_supported_to_total_output_facts_ratio": "manifest", "min_covered_to_total_reference_facts_ratio": "manifest"}
    }
    assert len(results["runs"]) == 2
    assert results["runs"][0]["supported_to_total_output_facts_ratio"]["value"] == 0.8
    assert results["runs"][0]["covered_to_total_reference_facts_ratio"]["value"] == 0.75
    report = (run_dir / "report.md").read_text()
    assert "Verdict: **PASS**" in report
    assert "| gs-001 | 1 | 0.8000 | 0.7500 |" in report
    assert "## Verdict evidence" in report
    assert "no output fact covers gf4" in report
    assert results["runs"][0]["diagnostics"]["unsupported"]
    assert results["runs"][0]["diagnostics"]["missing"]
    assert "PASS" in capsys.readouterr().out


def test_main_gate_failure_exit_1(tmp_path):
    gdir, run_dir = make_passing_layout(tmp_path)
    code = aggregate.main(base_args(gdir, run_dir) + ["--min-supported-to-total-output-facts-ratio", "0.9"])
    assert code == EXIT_GATE_FAILED
    assert json.loads((run_dir / "results.json").read_text())["verdict"] == "fail"


def test_main_cli_thresholds_override_manifest(tmp_path):
    gdir, run_dir = make_passing_layout(tmp_path)
    code = aggregate.main(
        base_args(gdir, run_dir) + ["--min-supported-to-total-output-facts-ratio", "0.5", "--min-covered-to-total-reference-facts-ratio", "0.5"]
    )
    assert code == EXIT_PASS
    results = json.loads((run_dir / "results.json").read_text())
    assert results["thresholds"]["source"] == {"min_supported_to_total_output_facts_ratio": "cli", "min_covered_to_total_reference_facts_ratio": "cli"}
    assert results["thresholds"]["min_supported_to_total_output_facts_ratio"] == 0.5


def test_main_missing_artifact_exit_2_lists_paths(tmp_path, capsys):
    gdir, run_dir = make_passing_layout(tmp_path)
    missing = run_dir / "verdicts" / "gs-001" / "2-expected-output-facts.json"
    missing.unlink()
    code = aggregate.main(base_args(gdir, run_dir))
    assert code == EXIT_PIPELINE_ERROR
    err = capsys.readouterr().err
    assert "missing run artifacts" in err
    assert str(missing) in err
    assert not (run_dir / "results.json").exists()


def test_main_missing_raw_output_exit_2_lists_path(tmp_path, capsys):
    gdir, run_dir = make_passing_layout(tmp_path)
    missing = run_dir / "runs" / "gs-001" / "2.md"
    missing.unlink()
    code = aggregate.main(base_args(gdir, run_dir))
    assert code == EXIT_PIPELINE_ERROR
    err = capsys.readouterr().err
    assert "missing run artifacts" in err
    assert str(missing) in err


def test_main_malformed_json_exit_2(tmp_path, capsys):
    gdir, run_dir = make_passing_layout(tmp_path)
    (run_dir / "facts" / "gs-001" / "1.json").write_text("{not json", encoding="utf-8")
    code = aggregate.main(base_args(gdir, run_dir))
    assert code == EXIT_PIPELINE_ERROR
    assert "invalid JSON" in capsys.readouterr().err


def test_main_sanity_failure_exit_2_before_verdicts(tmp_path, capsys):
    gdir, run_dir = make_passing_layout(tmp_path, iterations=3)
    # iteration 3: 1 extracted fact vs median 5 -> sanity failure even though
    # its verdict files are malformed relative to it — sanity runs first
    write_json(run_dir / "facts" / "gs-001" / "3.json", facts_payload(1))
    code = aggregate.main(base_args(gdir, run_dir, iterations=3))
    assert code == EXIT_PIPELINE_ERROR
    err = capsys.readouterr().err
    assert "sanity check failed" in err
    assert "gs-001/3" in err


def test_main_zero_facts_exit_2(tmp_path, capsys):
    gdir, run_dir = make_passing_layout(tmp_path)
    write_json(run_dir / "facts" / "gs-001" / "1.json", {"facts": []})
    code = aggregate.main(base_args(gdir, run_dir))
    assert code == EXIT_PIPELINE_ERROR
    assert "0 output facts" in capsys.readouterr().err


def test_main_invalid_iterations_exit_2(tmp_path):
    gdir, run_dir = make_passing_layout(tmp_path)
    code = aggregate.main(base_args(gdir, run_dir, iterations=0))
    assert code == EXIT_PIPELINE_ERROR


def test_main_bad_cli_threshold_exit_2(tmp_path):
    gdir, run_dir = make_passing_layout(tmp_path)
    code = aggregate.main(base_args(gdir, run_dir) + ["--min-supported-to-total-output-facts-ratio", "1.5"])
    assert code == EXIT_PIPELINE_ERROR
