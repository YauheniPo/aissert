#!/usr/bin/env python3
"""Host-neutral PostToolUse invariant checks for high-risk repository files.

Exit codes: 0 = invariants hold or irrelevant tool; 2 = invariant violation.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_AGENT_FILES = [
    REPO_ROOT / "agents" / "fact-extractor.md",
    REPO_ROOT / "agents" / "judge-supported-output-facts.md",
    REPO_ROOT / "agents" / "judge-expected-output-facts.md",
]


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise ValueError(f"{path.relative_to(REPO_ROOT)}: missing frontmatter")
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate() -> list[str]:
    errors: list[str] = []

    claude_manifest = REPO_ROOT / ".claude-plugin" / "plugin.json"
    if claude_manifest.is_file():
        try:
            plugin = load_json(claude_manifest)
            if plugin.get("name") != "aissert":
                errors.append(".claude-plugin/plugin.json name must remain 'aissert'")
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f".claude-plugin/plugin.json is invalid: {exc}")

        try:
            marketplace = load_json(REPO_ROOT / ".claude-plugin" / "marketplace.json")
            entries = [p for p in marketplace.get("plugins", []) if p.get("name") == "aissert"]
            if len(entries) != 1:
                errors.append("marketplace.json must contain exactly one plugin named 'aissert'")
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f".claude-plugin/marketplace.json is invalid: {exc}")

    codex_manifest = REPO_ROOT / ".codex-plugin" / "plugin.json"
    if codex_manifest.is_file():
        try:
            plugin = load_json(codex_manifest)
            if plugin.get("name") != "aissert":
                errors.append(".codex-plugin/plugin.json name must remain 'aissert'")
            if plugin.get("skills") != "./skills/":
                errors.append(".codex-plugin/plugin.json skills must remain './skills/'")
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f".codex-plugin/plugin.json is invalid: {exc}")

    if not claude_manifest.is_file() and not codex_manifest.is_file():
        errors.append("no supported plugin manifest is present")

    for path in RUNTIME_AGENT_FILES:
        try:
            fm = parse_frontmatter(path)
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
            continue
        rel = path.relative_to(REPO_ROOT)
        if fm.get("tools") != "[]":
            errors.append(f"{rel}: runtime judge/extractor agents must keep tools: []")
        if fm.get("model") != "inherit":
            errors.append(f"{rel}: model must remain inherit so the active host session selects the model")

    return errors


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}

    tool_name = payload.get("tool_name") or payload.get("toolName")
    if tool_name not in {"Write", "Edit", "MultiEdit"}:
        return 0

    errors = validate()
    if errors:
        print("Hook invariant violation:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
