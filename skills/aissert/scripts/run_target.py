#!/usr/bin/env python3
"""CI-only headless generation: run the target skill via `claude -p` per item x iteration.

Interactive runs use the SKILL.md orchestrator with clean-context subagents; this
wrapper exists for CI (canary/baseline) where no orchestrator session is available.
Each invocation is a fresh headless process, so the clean-context rule holds.

Resume-aware: existing non-empty outputs under runs/{item}/{i}.md are kept, only
missing ones are generated. Failures don't abort the sweep — the script reports
them and exits 2; aggregate.py will list the still-missing artifacts.

Exit codes: 0 = all outputs present, 2 = at least one generation failed.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from aggregate import EXIT_PASS, EXIT_PIPELINE_ERROR, PipelineError, load_golden_set

GENERATION_PROMPT = """\
Use the "{target_skill}" skill to process the input below. Reply with ONLY the
skill's final output — no preamble, no commentary.

<input>
{snapshot}
</input>
"""


def generate_one(claude_cmd: str, target_skill: str, snapshot: str, timeout: int) -> str:
    prompt = GENERATION_PROMPT.format(target_skill=target_skill, snapshot=snapshot)
    result = subprocess.run(
        [claude_cmd, "-p", prompt],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"exit {result.returncode}: {result.stderr.strip()[:500] or 'no stderr'}"
        )
    if not result.stdout.strip():
        raise RuntimeError("empty output")
    return result.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Headless target-skill runs over a golden set (CI only)."
    )
    parser.add_argument("--golden-set", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--target-skill", required=True)
    parser.add_argument("--iterations", required=True, type=int)
    parser.add_argument("--claude-cmd", default="claude", help="claude CLI binary")
    parser.add_argument("--timeout", type=int, default=600, help="seconds per run")
    args = parser.parse_args(argv)

    try:
        if args.iterations < 1:
            raise PipelineError(f"--iterations must be >= 1, got {args.iterations}")
        golden = load_golden_set(args.golden_set)
        if golden.target_skill != args.target_skill:
            raise PipelineError(
                f"target_skill mismatch: manifest has {golden.target_skill!r}, "
                f"command requested {args.target_skill!r}"
            )
    except PipelineError as e:
        print(f"run_target: {e}", file=sys.stderr)
        return EXIT_PIPELINE_ERROR

    generated, skipped, failed = 0, 0, []
    for item in golden.items:
        for i in range(1, args.iterations + 1):
            out_path = args.run_dir / "runs" / item.id / f"{i}.md"
            if out_path.is_file() and out_path.stat().st_size > 0:
                skipped += 1
                continue
            try:
                output = generate_one(
                    args.claude_cmd, args.target_skill, item.snapshot, args.timeout
                )
            except (RuntimeError, OSError, subprocess.TimeoutExpired) as e:
                failed.append(f"{item.id}/{i}: {e}")
                continue
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(output, encoding="utf-8")
            generated += 1

    print(f"run_target: generated={generated} resumed(skipped)={skipped} failed={len(failed)}")
    if failed:
        for f in failed:
            print(f"  FAILED {f}", file=sys.stderr)
        print("run_target: re-run to retry only the failed outputs", file=sys.stderr)
        return EXIT_PIPELINE_ERROR
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
