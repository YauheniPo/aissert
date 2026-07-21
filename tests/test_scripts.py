"""Tests for validate_golden.py and run_target.py, incl. golden/example as CI fixture."""
import json
import stat
from pathlib import Path

import run_target
import validate_golden
from aggregate import EXIT_PASS, EXIT_PIPELINE_ERROR, load_golden_set

from test_aggregate import golden_item_payload, make_golden, write_json

REPO = Path(__file__).resolve().parents[1]
EXAMPLE_SET = REPO / "golden" / "example"


# --------------------------------------------------------- validate_golden


def test_validate_golden_ok(tmp_path, capsys):
    gdir = make_golden(tmp_path, [golden_item_payload("gs-001", 3)])
    assert validate_golden.main([str(gdir)]) == EXIT_PASS
    out = capsys.readouterr().out
    assert "hash: sha256:" in out
    assert "items: 1, golden facts: 3" in out


def test_validate_golden_invalid_exit_2(tmp_path, capsys):
    gdir = make_golden(tmp_path, [golden_item_payload("gs-001", 3)])
    write_json(gdir / "items" / "gs-002.json", {"id": "gs-002"})
    assert validate_golden.main([str(gdir)]) == EXIT_PIPELINE_ERROR
    assert "invalid golden set" in capsys.readouterr().err


def test_validate_golden_missing_dir_exit_2(tmp_path, capsys):
    assert validate_golden.main([str(tmp_path / "nope")]) == EXIT_PIPELINE_ERROR


# ----------------------------------------------- golden/example CI fixture


def test_example_set_is_valid():
    assert validate_golden.main([str(EXAMPLE_SET)]) == EXIT_PASS


def test_example_set_is_synthetic_and_smoke_sized():
    golden = load_golden_set(EXAMPLE_SET)
    assert len(golden.items) >= 3, "--smoke needs 3 items (DESIGN.md §2)"
    assert golden.target_skill == "example-bug-summarizer"
    for item in golden.items:
        assert "fictional" in item.snapshot, (
            "example set must be explicitly synthetic (data boundary, DESIGN.md §9)"
        )


def test_example_set_exercises_weighted_recall():
    golden = load_golden_set(EXAMPLE_SET)
    assert any(item.weights for item in golden.items), (
        "example set should include at least one weighted item as a fixture"
    )


# --------------------------------------------------------------- run_target


def fake_claude(tmp_path, script_body):
    path = tmp_path / "fake-claude"
    path.write_text(f"#!/bin/sh\n{script_body}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def test_run_target_generates_all(tmp_path, capsys):
    gdir = make_golden(tmp_path, [golden_item_payload("gs-001", 2),
                                  golden_item_payload("gs-002", 2)])
    run_dir = tmp_path / "run"
    cmd = fake_claude(tmp_path, 'echo "generated output for: $2"')
    code = run_target.main([
        "--golden-set", str(gdir), "--run-dir", str(run_dir),
        "--target-skill", "demo-skill", "--iterations", "2", "--claude-cmd", cmd,
    ])
    assert code == EXIT_PASS
    outputs = sorted(p.relative_to(run_dir).as_posix() for p in run_dir.rglob("*.md"))
    assert outputs == ["runs/gs-001/1.md", "runs/gs-001/2.md",
                       "runs/gs-002/1.md", "runs/gs-002/2.md"]
    assert "generated=4" in capsys.readouterr().out


def test_run_target_resume_skips_existing(tmp_path, capsys):
    gdir = make_golden(tmp_path, [golden_item_payload("gs-001", 2)])
    run_dir = tmp_path / "run"
    existing = run_dir / "runs" / "gs-001" / "1.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("previous output", encoding="utf-8")
    cmd = fake_claude(tmp_path, 'echo "fresh output"')
    code = run_target.main([
        "--golden-set", str(gdir), "--run-dir", str(run_dir),
        "--target-skill", "demo-skill", "--iterations", "2", "--claude-cmd", cmd,
    ])
    assert code == EXIT_PASS
    assert existing.read_text(encoding="utf-8") == "previous output"
    out = capsys.readouterr().out
    assert "generated=1" in out and "resumed(skipped)=1" in out


def test_run_target_failure_exit_2_and_continues(tmp_path, capsys):
    gdir = make_golden(tmp_path, [golden_item_payload("gs-001", 2),
                                  golden_item_payload("gs-002", 2)])
    run_dir = tmp_path / "run"
    # fails only for the input containing MARKER-1 (gs-001's snapshot)
    for item_file in (gdir / "items").glob("*.json"):
        data = json.loads(item_file.read_text())
        data["input"]["snapshot"] = f"MARKER-{item_file.stem[-1]} synthetic input"
        write_json(item_file, data)
    cmd = fake_claude(
        tmp_path,
        'case "$2" in *MARKER-1*) echo "boom" >&2; exit 1;; *) echo ok;; esac',
    )
    code = run_target.main([
        "--golden-set", str(gdir), "--run-dir", str(run_dir),
        "--target-skill", "demo-skill", "--iterations", "1", "--claude-cmd", cmd,
    ])
    assert code == EXIT_PIPELINE_ERROR
    err = capsys.readouterr().err
    assert "FAILED gs-001/1" in err
    assert (run_dir / "runs" / "gs-002" / "1.md").is_file(), "sweep must continue past failures"
    assert not (run_dir / "runs" / "gs-001" / "1.md").exists()


def test_run_target_empty_output_is_failure(tmp_path):
    gdir = make_golden(tmp_path, [golden_item_payload("gs-001", 2)])
    cmd = fake_claude(tmp_path, "true")
    code = run_target.main([
        "--golden-set", str(gdir), "--run-dir", str(tmp_path / "run"),
        "--target-skill", "demo-skill", "--iterations", "1", "--claude-cmd", cmd,
    ])
    assert code == EXIT_PIPELINE_ERROR
