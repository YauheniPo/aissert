#!/usr/bin/env python3
"""Host-neutral Stop hook: run deterministic checks before a turn ends.

Exit codes:
0 = checks passed or no relevant changes;
2 = block Stop and feed failures back to Claude.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def pytest_command() -> list[str]:
    venv_pytest = REPO_ROOT / ".venv" / "bin" / "pytest"
    if venv_pytest.is_file():
        return [str(venv_pytest), "tests/", "-q"]
    return ["pytest", "tests/", "-q"]


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def git_lines(args: list[str]) -> set[str]:
    result = run(["git", *args])
    if result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def changed_files() -> set[str]:
    files: set[str] = set()
    files.update(git_lines(["diff", "--name-only"]))
    files.update(git_lines(["diff", "--name-only", "--cached"]))
    files.update(git_lines(["ls-files", "--others", "--exclude-standard"]))
    return files


def touches_any(files: set[str], prefixes: tuple[str, ...], exact: tuple[str, ...] = ()) -> bool:
    return any(path in exact or path.startswith(prefixes) for path in files)


def wiki_lint_structural_failure(stdout: str) -> bool:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return True
    summary = payload.get("summary", {})
    structural_keys = (
        "missing_index_entries",
        "orphan_pages",
        "invalid_validated_commits",
        "broken_source_paths",
        "broken_links",
        "frontmatter_errors",
    )
    return any(int(summary.get(key, 0)) > 0 for key in structural_keys)


def append_failure(failures: list[str], label: str, result: subprocess.CompletedProcess[str]) -> None:
    output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
    if len(output) > 4000:
        output = output[-4000:]
    failures.append(f"{label} failed with exit {result.returncode}\n{output}")


def main() -> int:
    if os.environ.get("AISSERT_SKIP_STOP_VERIFY") == "1":
        return 0

    files = changed_files()
    if not files:
        return 0

    should_pytest = touches_any(
        files,
        (
            "agents/",
            "canary/",
            "commands/",
            "golden/example/",
            "scripts/",
            "hooks/",
            "scripts/hooks/",
            "skills/",
            "tests/",
            ".claude/",
            ".codex-plugin/",
        ),
        exact=("CLAUDE.md", "DESIGN.md"),
    )
    should_package = touches_any(
        files,
        (
            ".claude-plugin/",
            ".codex-plugin/",
            "agents/",
            "canary/",
            "commands/",
            "golden/example/",
            "hooks/",
            "skills/",
        ),
        exact=(
            "README.md",
            "CHANGELOG.md",
            "CODE_OF_CONDUCT.md",
            "CONTRIBUTING.md",
            "LICENSE",
            "ROADMAP.md",
            "SECURITY.md",
            "scripts/build_plugin_zip.py",
            "scripts/build_codex_plugin_zip.py",
        ),
    )
    should_wiki = touches_any(files, ("knowledge/", "scripts/wiki/"))

    checks: list[tuple[str, list[str]]] = []
    if should_pytest:
        checks.append(("pytest tests/ -q", pytest_command()))
    if should_package:
        checks.append(("python3 scripts/build_plugin_zip.py", ["python3", "scripts/build_plugin_zip.py"]))
        checks.append(("python3 scripts/build_codex_plugin_zip.py", ["python3", "scripts/build_codex_plugin_zip.py"]))
    if should_wiki:
        checks.append(("python3 scripts/wiki/lint.py", ["python3", "scripts/wiki/lint.py"]))

    failures: list[str] = []
    warnings: list[str] = []
    for label, args in checks:
        result = run(args)
        if label == "python3 scripts/wiki/lint.py" and result.returncode != 0:
            if wiki_lint_structural_failure(result.stdout):
                append_failure(failures, label, result)
            else:
                warnings.append("wiki lint has stale-page warnings only")
            continue
        if result.returncode != 0:
            append_failure(failures, label, result)

    if warnings:
        print("Stop hook warnings: " + "; ".join(warnings), file=sys.stderr)

    if failures:
        print("Stop hook blocked completion. Fix these checks:", file=sys.stderr)
        for failure in failures:
            print("\n" + failure, file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
