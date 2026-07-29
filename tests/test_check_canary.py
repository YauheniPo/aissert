"""Tests for check_canary.py — agreement math, reviewed gate, exit codes."""
import json
from pathlib import Path

import pytest

import aggregate
import check_canary
from aggregate import EXIT_GATE_FAILED, EXIT_PASS, EXIT_PIPELINE_ERROR, PipelineError
from check_canary import (
    CanaryItem,
    ExtractorCanaryItem,
    ExpectedExtractorFact,
    compare_extractor_item,
    compare_item,
    load_canary_set,
)

from test_aggregate import write_json


def canary_item_payload(item_id, judge="precision", expected=None, reviewed=True,
                        borderline=False):
    id_key = "fact_id" if judge == "precision" else "reference_fact_id"
    expected = expected or {"f1": "supported"}
    reference_ids = list(expected) if judge == "recall" else ["gf1"]
    output_ids = list(expected) if judge == "precision" else ["f1"]
    return {
        "id": item_id,
        "judge": judge,
        "borderline": borderline,
        "reviewed": reviewed,
        "source": {"note": "synthetic"},
        "input": {
            "reference_facts": [{"id": gid, "text": "g"} for gid in reference_ids],
            "output_facts": [
                {"id": fid, "type": "other", "text": "e"} for fid in output_ids
            ],
        },
        "expected": {"verdicts": [{id_key: vid, "verdict": v} for vid, v in expected.items()]},
    }


def make_canary(tmp_path, items, min_agreement=1.0):
    cdir = tmp_path / "canary"
    write_json(cdir / "manifest.json",
               {"schema_version": aggregate.SCHEMA_VERSION, "description": "test",
                "min_agreement": min_agreement})
    for item in items:
        write_json(cdir / "items" / f"{item['id']}.json", item)
    return cdir


def write_actual(vdir, item_id, verdicts, id_key="fact_id"):
    rows = []
    for vid, verdict in verdicts.items():
        row = {id_key: vid, "verdict": verdict, "evidence": "e"}
        if id_key == "reference_fact_id" and verdict == "covered":
            row["covered_by"] = "f1"
        rows.append(row)
    write_json(vdir / f"{item_id}.json", {"verdicts": rows})


# ------------------------------------------------------------------ loading


def test_unreviewed_item_is_pipeline_error(tmp_path):
    cdir = make_canary(tmp_path, [canary_item_payload("cn-001", reviewed=False)])
    with pytest.raises(PipelineError, match="not hand-reviewed"):
        load_canary_set(cdir)


def test_bad_judge_kind_rejected(tmp_path):
    payload = canary_item_payload("cn-001")
    payload["judge"] = "vibes"
    cdir = make_canary(tmp_path, [payload])
    with pytest.raises(PipelineError, match="'judge'"):
        load_canary_set(cdir)


def test_recall_item_uses_reference_fact_id_and_enum(tmp_path):
    payload = canary_item_payload("cn-001", judge="recall", expected={"gf1": "covered"})
    cdir = make_canary(tmp_path, [payload])
    _, items, extractor_items = load_canary_set(cdir)
    assert items[0].expected == {"gf1": "covered"}
    assert extractor_items == []


def test_wrong_enum_for_judge_kind_rejected(tmp_path):
    # 'supported' is an precision value; invalid for a recall item
    payload = canary_item_payload("cn-001", judge="recall", expected={"gf1": "supported"})
    cdir = make_canary(tmp_path, [payload])
    with pytest.raises(PipelineError, match="verdict must be one of"):
        load_canary_set(cdir)


def test_min_agreement_validated(tmp_path):
    cdir = make_canary(tmp_path, [canary_item_payload("cn-001")], min_agreement=0)
    with pytest.raises(PipelineError, match="min_agreement"):
        load_canary_set(cdir)


def test_canary_manifest_schema_version_required(tmp_path):
    cdir = make_canary(tmp_path, [canary_item_payload("cn-001")])
    manifest = json.loads((cdir / "manifest.json").read_text())
    manifest["schema_version"] = aggregate.SCHEMA_VERSION + 1
    write_json(cdir / "manifest.json", manifest)
    with pytest.raises(PipelineError, match="schema_version"):
        load_canary_set(cdir)


# ------------------------------------------------------------- compare_item


def make_item(expected, judge="precision"):
    reference_ids = tuple(expected) if judge == "recall" else ("gf1",)
    output_ids = tuple(expected) if judge == "precision" else ("f1",)
    return CanaryItem(
        id="cn-001",
        judge=judge,
        borderline=False,
        expected=expected,
        reference_fact_ids=reference_ids,
        output_fact_ids=output_ids,
    )


def test_compare_full_agreement():
    item = make_item({"f1": "supported", "f2": "unsupported"})
    actual = {"verdicts": [
        {"fact_id": "f1", "verdict": "supported", "evidence": "e"},
        {"fact_id": "f2", "verdict": "unsupported", "evidence": "e"},
    ]}
    assert compare_item(item, actual) == []


def test_compare_reports_mismatch():
    item = make_item({"f1": "supported"})
    actual = {"verdicts": [{"fact_id": "f1", "verdict": "unsupported", "evidence": "e"}]}
    mismatches = compare_item(item, actual)
    assert len(mismatches) == 1
    assert "expected supported, got unsupported" in mismatches[0]


def test_compare_id_set_mismatch_is_pipeline_error():
    item = make_item({"f1": "supported", "f2": "supported"})
    actual = {"verdicts": [{"fact_id": "f1", "verdict": "supported", "evidence": "e"}]}
    with pytest.raises(PipelineError, match="missing=\\['f2'\\]"):
        compare_item(item, actual)


def test_compare_precision_requires_evidence():
    item = make_item({"f1": "supported"})
    actual = {"verdicts": [{"fact_id": "f1", "verdict": "supported"}]}
    with pytest.raises(PipelineError, match="'evidence'"):
        compare_item(item, actual)


def test_compare_recall_requires_covered_by():
    item = make_item({"gf1": "covered"}, judge="recall")
    actual = {"verdicts": [
        {"reference_fact_id": "gf1", "verdict": "covered", "evidence": "f1"}
    ]}
    with pytest.raises(PipelineError, match="covered_by"):
        compare_item(item, actual)


def test_expected_ids_must_match_frozen_input(tmp_path):
    payload = canary_item_payload("cn-001")
    payload["expected"]["verdicts"].append(
        {"fact_id": "f2", "verdict": "unsupported"}
    )
    cdir = make_canary(tmp_path, [payload])
    with pytest.raises(PipelineError, match="must match frozen precision input"):
        load_canary_set(cdir)


# -------------------------------------------------------- extractor compare


def test_compare_extractor_uses_count_types_and_text_anchors():
    item = ExtractorCanaryItem(
        id="cx-001",
        raw_output="raw",
        expected_facts=(
            ExpectedExtractorFact(
                id="f1",
                type="expectation",
                must_contain=("reset link", "60 seconds"),
                must_not_contain=("SMS",),
            ),
        ),
        must_not_contain=("race condition",),
    )
    actual = {
        "facts": [
            {
                "id": "f1",
                "type": "expectation",
                "text": "A reset link arrives within 60 seconds",
            }
        ]
    }
    assert compare_extractor_item(item, actual) == []


def test_compare_extractor_reports_missing_anchor():
    item = ExtractorCanaryItem(
        id="cx-001",
        raw_output="raw",
        expected_facts=(
            ExpectedExtractorFact(
                id="f1",
                type="expectation",
                must_contain=("60 seconds",),
                must_not_contain=(),
            ),
        ),
        must_not_contain=(),
    )
    actual = {
        "facts": [{"id": "f1", "type": "expectation", "text": "A link arrives"}]
    }
    assert "lacks required substring" in compare_extractor_item(item, actual)[0]


# ------------------------------------------------------------------- main


def test_main_pass(tmp_path, capsys):
    cdir = make_canary(tmp_path, [
        canary_item_payload("cn-001", expected={"f1": "supported", "f2": "unsupported"}),
        canary_item_payload("cn-002", judge="recall", expected={"gf1": "covered"}),
    ])
    vdir = tmp_path / "actual"
    write_actual(vdir, "cn-001", {"f1": "supported", "f2": "unsupported"})
    write_actual(vdir, "cn-002", {"gf1": "covered"}, id_key="reference_fact_id")
    code = check_canary.main(["--canary-set", str(cdir), "--verdicts-dir", str(vdir)])
    assert code == EXIT_PASS
    assert "agreement=1.0000" in capsys.readouterr().out


def test_main_divergence_exit_1(tmp_path, capsys):
    cdir = make_canary(tmp_path, [
        canary_item_payload("cn-001", expected={"f1": "supported", "f2": "unsupported"}),
    ])
    vdir = tmp_path / "actual"
    write_actual(vdir, "cn-001", {"f1": "supported", "f2": "supported"})
    code = check_canary.main(["--canary-set", str(cdir), "--verdicts-dir", str(vdir)])
    assert code == EXIT_GATE_FAILED
    out, err = capsys.readouterr()
    assert "MISMATCH cn-001" in out
    assert "agreement=0.5000" in out
    assert "DIVERGENCE" in err


def test_main_agreement_threshold_from_manifest(tmp_path):
    # 3 of 4 verdicts match = 0.75 >= 0.7 -> pass
    cdir = make_canary(tmp_path, [
        canary_item_payload("cn-001", expected={"f1": "supported", "f2": "unsupported",
                                                "f3": "supported", "f4": "supported"},
                            borderline=True),
    ], min_agreement=0.7)
    vdir = tmp_path / "actual"
    write_actual(vdir, "cn-001", {"f1": "supported", "f2": "supported",
                                  "f3": "supported", "f4": "supported"})
    code = check_canary.main(["--canary-set", str(cdir), "--verdicts-dir", str(vdir)])
    assert code == EXIT_PASS


def test_main_recall_regression_cannot_hide_in_overall_score(tmp_path):
    items = [
        canary_item_payload(
            "cn-001",
            expected={f"f{i}": "supported" for i in range(1, 10)},
        ),
        canary_item_payload(
            "cn-002", judge="recall", expected={"gf1": "covered"}
        ),
    ]
    cdir = make_canary(tmp_path, items, min_agreement=0.9)
    manifest = json.loads((cdir / "manifest.json").read_text())
    manifest["min_agreement_by_judge"] = {"precision": 0.8, "recall": 1.0}
    write_json(cdir / "manifest.json", manifest)
    vdir = tmp_path / "actual"
    write_actual(
        vdir,
        "cn-001",
        {f"f{i}": "supported" for i in range(1, 10)},
    )
    write_actual(
        vdir,
        "cn-002",
        {"gf1": "missing"},
        id_key="reference_fact_id",
    )
    code = check_canary.main(
        ["--canary-set", str(cdir), "--verdicts-dir", str(vdir)]
    )
    assert code == EXIT_GATE_FAILED


def test_main_extractor_mismatch_fails_its_own_gate(tmp_path):
    cdir = make_canary(tmp_path, [canary_item_payload("cn-001")])
    write_json(
        cdir / "extractor-items" / "cx-001.json",
        {
            "id": "cx-001",
            "reviewed": True,
            "raw_output": "A reset link arrives within 60 seconds.",
            "expected": {
                "facts": [
                    {
                        "id": "f1",
                        "type": "expectation",
                        "must_contain": ["60 seconds"],
                    }
                ],
                "must_not_contain": [],
            },
        },
    )
    vdir = tmp_path / "actual"
    write_actual(vdir, "cn-001", {"f1": "supported"})
    write_json(
        vdir / "cx-001.json",
        {
            "facts": [
                {"id": "f1", "type": "expectation", "text": "A reset link arrives"}
            ]
        },
    )
    code = check_canary.main(
        ["--canary-set", str(cdir), "--verdicts-dir", str(vdir)]
    )
    assert code == EXIT_GATE_FAILED


def test_main_missing_actual_file_exit_2(tmp_path, capsys):
    cdir = make_canary(tmp_path, [canary_item_payload("cn-001")])
    code = check_canary.main(["--canary-set", str(cdir),
                              "--verdicts-dir", str(tmp_path / "actual")])
    assert code == EXIT_PIPELINE_ERROR
    assert "missing runtime-agent outputs" in capsys.readouterr().err


def test_main_unreviewed_exit_2(tmp_path, capsys):
    cdir = make_canary(tmp_path, [canary_item_payload("cn-001", reviewed=False)])
    vdir = tmp_path / "actual"
    write_actual(vdir, "cn-001", {"f1": "supported"})
    code = check_canary.main(["--canary-set", str(cdir), "--verdicts-dir", str(vdir)])
    assert code == EXIT_PIPELINE_ERROR
    assert "not hand-reviewed" in capsys.readouterr().err


# ------------------------------------------------------ repo canary fixture


def test_repo_canary_items_are_structurally_valid():
    """Structural check that survives hand-review (does not assert reviewed flag)."""
    items_dir = Path(__file__).resolve().parents[1] / "canary" / "items"
    files = sorted(items_dir.glob("*.json"))
    assert len(files) >= 10, "canary set should hold 10-15 items (DESIGN.md §7.3)"
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        assert data["id"] == f.stem
        assert data["judge"] in ("precision", "recall")
        assert isinstance(data["reviewed"], bool)
        assert data["expected"]["verdicts"], f"{f.name}: empty expected verdicts"
        assert data["input"]["reference_facts"] and data["input"]["output_facts"]
    borderline = [f for f in files
                  if json.loads(f.read_text(encoding="utf-8"))["borderline"]]
    assert borderline, "canary must include deliberately borderline cases"
    _, _, extractor_items = load_canary_set(Path(__file__).resolve().parents[1] / "canary")
    assert len(extractor_items) >= 3
