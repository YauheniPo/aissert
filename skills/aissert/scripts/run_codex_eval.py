#!/usr/bin/env python3
"""Run aissert with isolated headless Codex workers.

Codex CLI has no named plugin-agent registry.  This adapter starts one fresh
``codex exec`` process per runtime call, builds its prompt from the shared
``agents/`` templates and results-schema contract, and persists the returned
artifact in the parent process.  It deliberately contains no judging rules.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from aggregate import EXIT_PIPELINE_ERROR, PipelineError, validate_facts


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
REPO_ROOT = SKILL_DIR.parents[1]
AGENTS_DIR = REPO_ROOT / "agents"
CONTRACT = (SKILL_DIR / "references" / "results-schema.md").read_text(encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def worker_prompt(template: str, payload: dict) -> str:
    return """You are an isolated aissert runtime worker. Do not use tools, read files,
write files, or explain your work. Return only the final response requested by the
runtime-agent template below. If the template requires JSON, return one JSON object
with no Markdown fence or prose.

<runtime-agent-template>
{template}
</runtime-agent-template>

<output-contract>
{contract}
</output-contract>

<input>
{payload}
</input>
""".format(template=template, contract=CONTRACT, payload=json.dumps(payload, indent=2))


def target_skill_template(skill: str, supplied_path: Path | None) -> str:
    """Load either a bundled target skill or an explicit external SKILL.md."""
    path = supplied_path or REPO_ROOT / "skills" / skill / "SKILL.md"
    if path.is_dir():
        path = path / "SKILL.md"
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        source = "--target-skill-file" if supplied_path else "the bundled plugin"
        raise PipelineError(
            f"target skill {skill!r} is unavailable from {source}: {path}; "
            "pass --target-skill-file /path/to/SKILL.md for an external skill"
        ) from error


def target_prompt(template: str, snapshot: str) -> str:
    return """You are an isolated target-skill runtime worker. Do not use tools, read
files, or write files. Follow this skill using only the supplied snapshot. Return
only the skill's final output, with no preamble or commentary.

<target-skill>
{template}
</target-skill>

<input>
{snapshot}
</input>
""".format(template=template, snapshot=snapshot)


def invoke_codex(codex_cmd: str, prompt: str, timeout: int) -> str:
    """Execute a clean child session and return its final message."""
    with tempfile.TemporaryDirectory(prefix="aissert-codex-worker-") as isolated:
        output = Path(isolated) / "final.txt"
        result = subprocess.run(
            [
                codex_cmd,
                "exec",
                "--ephemeral",
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "--cd",
                isolated,
                "--output-last-message",
                str(output),
                "-",
            ],
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        if result.returncode:
            raise RuntimeError(
                f"codex exit {result.returncode}: "
                f"{result.stderr.strip()[-800:] or result.stdout.strip()[-800:]}"
            )
        if not output.is_file() or not output.read_text(encoding="utf-8").strip():
            raise RuntimeError("codex returned no final response")
        return output.read_text(encoding="utf-8").strip()


def write_json_response(path: Path, response: str) -> None:
    try:
        value = json.loads(response)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"malformed JSON response: {error}") from error
    if not isinstance(value, dict):
        raise RuntimeError("JSON response must be an object")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def has_json_object(path: Path) -> bool:
    try:
        return isinstance(read_json(path), dict)
    except (OSError, json.JSONDecodeError):
        return False


def has_valid_facts(path: Path) -> bool:
    try:
        validate_facts(read_json(path), f"facts artifact {path}")
    except (OSError, json.JSONDecodeError, PipelineError):
        return False
    return True


def has_text(path: Path) -> bool:
    try:
        return path.is_file() and bool(path.read_text(encoding="utf-8").strip())
    except OSError:
        return False


def run_parallel(tasks: list[tuple[str, callable]], workers: int) -> list[str]:
    errors: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(task): name for name, task in tasks}
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                future.result()
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
                errors.append(f"{name}: {error}")
    return errors


def canary_tasks(canary_dir: Path, run_dir: Path, codex_cmd: str, timeout: int):
    tasks: list[tuple[str, callable]] = []

    for path in sorted((canary_dir / "items").glob("*.json")):
        item = read_json(path)
        agent = "judge-supported-output-facts" if item["judge"] == "precision" else "judge-expected-output-facts"
        template = (AGENTS_DIR / f"{agent}.md").read_text(encoding="utf-8")
        output = run_dir / "canary" / path.name
        payload = item["input"]
        if not has_json_object(output):
            tasks.append((item["id"], lambda t=template, p=payload, o=output: write_json_response(o, invoke_codex(codex_cmd, worker_prompt(t, p), timeout))))
    template = (AGENTS_DIR / "fact-extractor.md").read_text(encoding="utf-8")
    for path in sorted((canary_dir / "extractor-items").glob("*.json")):
        item = read_json(path)
        output = run_dir / "canary" / path.name
        if not has_json_object(output):
            tasks.append((item["id"], lambda t=template, p={"raw_output": item["raw_output"]}, o=output: write_json_response(o, invoke_codex(codex_cmd, worker_prompt(t, p), timeout))))
    return tasks


def shell(args: list[str]) -> int:
    return subprocess.run(args).returncode


def materialize_smoke_golden_set(
    golden_set: Path, run_dir: Path, item_paths: list[Path]
) -> Path:
    """Create the exact three-item golden view consumed by aggregate.py."""
    smoke_set = run_dir / ".aissert-smoke-golden"
    items_dir = smoke_set / "items"
    if items_dir.exists():
        shutil.rmtree(items_dir)
    items_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(golden_set / "manifest.json", smoke_set / "manifest.json")
    for item_path in item_paths:
        shutil.copy2(item_path, items_dir / item_path.name)
    return smoke_set


def aggregate_command(args: argparse.Namespace, golden_set: Path) -> list[str]:
    command = [
        sys.executable,
        str(SCRIPT_DIR / "aggregate.py"),
        "--run-dir",
        str(args.run_dir),
        "--golden-set",
        str(golden_set),
        "--iterations",
        str(args.iterations),
    ]
    for option, value in (
        ("--min-supported-to-total-output-facts-ratio", args.min_supported_to_total_output_facts_ratio),
        ("--min-covered-to-total-reference-facts-ratio", args.min_covered_to_total_reference_facts_ratio),
        ("--model-id", args.model_id),
    ):
        if value is not None:
            command += [option, str(value)]
    return command


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden-set", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--target-skill")
    parser.add_argument(
        "--target-skill-file",
        type=Path,
        default=None,
        help="external target SKILL.md (or its directory) when it is not bundled",
    )
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--min-supported-to-total-output-facts-ratio", type=float, default=None)
    parser.add_argument("--min-covered-to-total-reference-facts-ratio", type=float, default=None)
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--canary-only", action="store_true")
    parser.add_argument("--codex-cmd", default="codex")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    if sys.version_info < (3, 10):
        print("run_codex_eval: requires Python 3.10+ (use the project's Python 3.12 environment)", file=sys.stderr)
        return 2
    if args.smoke:
        args.iterations = 2
    if args.iterations < 1 or args.workers < 1:
        parser.error("--iterations and --workers must be >= 1")

    args.run_dir.mkdir(parents=True, exist_ok=True)
    canary_dir = REPO_ROOT / "canary"
    if canary_dir.is_dir():
        errors = run_parallel(canary_tasks(canary_dir, args.run_dir, args.codex_cmd, args.timeout), args.workers)
        if errors:
            print("run_codex_eval: canary workers failed:", file=sys.stderr)
            print("\n".join(f"  {error}" for error in errors), file=sys.stderr)
            return 2
        code = shell([sys.executable, str(SCRIPT_DIR / "check_canary.py"), "--canary-set", str(canary_dir), "--verdicts-dir", str(args.run_dir / "canary")])
        if code:
            return code
    if args.canary_only:
        return 0

    validate = [sys.executable, str(SCRIPT_DIR / "validate_golden.py"), str(args.golden_set)]
    if args.target_skill:
        validate += ["--target-skill", args.target_skill]
    if shell(validate):
        return 2
    manifest = read_json(args.golden_set / "manifest.json")
    target_skill = args.target_skill or manifest["target_skill"]
    item_paths = sorted((args.golden_set / "items").glob("*.json"))
    if args.smoke:
        if len(item_paths) < 3:
            print("run_codex_eval: --smoke requires at least 3 golden items", file=sys.stderr)
            return EXIT_PIPELINE_ERROR
        item_paths = item_paths[:3]
        aggregate_golden_set = materialize_smoke_golden_set(
            args.golden_set, args.run_dir, item_paths
        )
    else:
        aggregate_golden_set = args.golden_set
    items = [read_json(path) for path in item_paths]
    try:
        target_template = target_skill_template(target_skill, args.target_skill_file)
    except PipelineError as error:
        print(f"run_codex_eval: pipeline error: {error}", file=sys.stderr)
        return EXIT_PIPELINE_ERROR
    generation: list[tuple[str, callable]] = []
    for item in items:
        for iteration in range(1, args.iterations + 1):
            output = args.run_dir / "runs" / item["id"] / f"{iteration}.md"
            if not has_text(output):
                generation.append((f"generate {item['id']}/{iteration}", lambda p=target_prompt(target_template, item["input"]["snapshot"]), o=output: (o.parent.mkdir(parents=True, exist_ok=True), o.write_text(invoke_codex(args.codex_cmd, p, args.timeout) + "\n", encoding="utf-8"))))
    errors = run_parallel(generation, args.workers)
    if errors:
        print("run_codex_eval: generation failed:\n  " + "\n  ".join(errors), file=sys.stderr); return 2
    extractor = (AGENTS_DIR / "fact-extractor.md").read_text(encoding="utf-8")
    extraction: list[tuple[str, callable]] = []
    for item in items:
        for iteration in range(1, args.iterations + 1):
            raw = (args.run_dir / "runs" / item["id"] / f"{iteration}.md").read_text(encoding="utf-8")
            output = args.run_dir / "facts" / item["id"] / f"{iteration}.json"
            if not has_valid_facts(output):
                extraction.append((f"extract {item['id']}/{iteration}", lambda t=extractor, p={"raw_output": raw}, o=output: write_json_response(o, invoke_codex(args.codex_cmd, worker_prompt(t, p), args.timeout))))
    errors = run_parallel(extraction, args.workers)
    if errors:
        print("run_codex_eval: extraction failed:\n  " + "\n  ".join(errors), file=sys.stderr); return 2
    judges = {name: (AGENTS_DIR / f"{name}.md").read_text(encoding="utf-8") for name in ("judge-supported-output-facts", "judge-expected-output-facts")}
    judging: list[tuple[str, callable]] = []
    for item in items:
        for iteration in range(1, args.iterations + 1):
            facts_path = args.run_dir / "facts" / item["id"] / f"{iteration}.json"
            try:
                facts_data = read_json(facts_path)
                validate_facts(facts_data, f"facts artifact {facts_path}")
                facts = facts_data["facts"]
            except (OSError, json.JSONDecodeError, PipelineError) as error:
                print(f"run_codex_eval: pipeline error: {error}", file=sys.stderr)
                return EXIT_PIPELINE_ERROR
            common = {
                "reference_facts": item["reference"]["reference_facts"],
                "output_facts": facts,
            }
            for agent, suffix in (("judge-supported-output-facts", "supported-output-facts"), ("judge-expected-output-facts", "expected-output-facts")):
                output = args.run_dir / "verdicts" / item["id"] / f"{iteration}-{suffix}.json"
                if not has_json_object(output):
                    judging.append((f"{agent} {item['id']}/{iteration}", lambda t=judges[agent], p=common, o=output: write_json_response(o, invoke_codex(args.codex_cmd, worker_prompt(t, p), args.timeout))))
    errors = run_parallel(judging, args.workers)
    if errors:
        print("run_codex_eval: judging failed:\n  " + "\n  ".join(errors), file=sys.stderr); return 2
    return shell(aggregate_command(args, aggregate_golden_set))


if __name__ == "__main__":
    raise SystemExit(main())
