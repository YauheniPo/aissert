#!/usr/bin/env python3
"""Host-neutral PostToolUse hook: auto-bump a golden set's manifest.json set_version
when Write/Edit/MultiEdit touches golden/<skill>/items/*.json, or edits
golden/<skill>/manifest.json directly (e.g. defaults.min_supported_to_total_output_facts_ratio,
target_skill).

Idempotent per commit: bumps the patch component only if the working-tree
set_version still equals the last committed (HEAD) value. Once bumped, later
edits in the same working-tree session leave it alone until the next commit
resets the baseline — otherwise every keystroke-level edit would bump again.

Exit codes: 0 always (informational only, never blocks — see
CLAUDE.md 'Claude automation': PostToolUse fires after the tool already ran).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def normalized_repo_path(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(REPO_ROOT)
        except ValueError:
            return None
    return Path(value)


def golden_manifest_for_item(item_path: Path) -> Path | None:
    parts = item_path.parts
    if len(parts) >= 3 and parts[0] == "golden" and parts[2] == "items":
        return Path(parts[0], parts[1], "manifest.json")
    return None


def golden_manifest_for_edited_path(path: Path) -> Path | None:
    parts = path.parts
    if len(parts) == 3 and parts[0] == "golden" and parts[2] == "manifest.json":
        return path
    return golden_manifest_for_item(path)


def git_show_head(rel_path: Path) -> str | None:
    result = subprocess.run(
        ["git", "show", f"HEAD:{rel_path.as_posix()}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return result.stdout if result.returncode == 0 else None


def bump_patch(version: str) -> str | None:
    parts = version.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return None
    major, minor, patch = (int(p) for p in parts)
    return f"{major}.{minor}.{patch + 1}"


def maybe_bump(manifest_path: Path) -> str | None:
    abs_path = REPO_ROOT / manifest_path
    if not abs_path.exists():
        return None
    try:
        manifest = json.loads(abs_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    current = manifest.get("set_version")
    if not isinstance(current, str):
        return None

    head_text = git_show_head(manifest_path)
    if head_text is not None:
        try:
            head_version = json.loads(head_text).get("set_version")
        except json.JSONDecodeError:
            head_version = None
        if head_version != current:
            return None  # already bumped since last commit

    new_version = bump_patch(current)
    if new_version is None:
        return None

    manifest["set_version"] = new_version
    abs_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return new_version


def paths_from_tool_input(tool_input: dict) -> list[Path]:
    paths: list[Path] = []
    for key in ("file_path", "path"):
        value = tool_input.get(key)
        if isinstance(value, str):
            rel = normalized_repo_path(value)
            if rel is not None:
                paths.append(rel)
    return paths


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0

    tool_name = payload.get("tool_name") or payload.get("toolName")
    if tool_name not in {"Write", "Edit", "MultiEdit"}:
        return 0

    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
    if not isinstance(tool_input, dict):
        return 0

    bumped: list[str] = []
    for path in paths_from_tool_input(tool_input):
        manifest_path = golden_manifest_for_edited_path(path)
        if manifest_path is None:
            continue
        new_version = maybe_bump(manifest_path)
        if new_version:
            bumped.append(f"{manifest_path.as_posix()} -> {new_version}")

    if bumped:
        print("hook_bump_golden_version: bumped " + ", ".join(bumped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
