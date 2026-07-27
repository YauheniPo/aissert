#!/usr/bin/env python3
"""PreToolUse guardrails for Claude Code sessions in this repo.

Exit codes:
0 = allow; JSON stdout may deny a tool call.
2 = malformed hook input; block conservatively.
"""
from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def deny(message: str) -> None:
    sys.stdout.write(
        json.dumps(
            {
                "permissionDecision": "deny",
                "permissionDecisionReason": message,
            }
        )
    )


def normalized_repo_path(value: str | None) -> str:
    if not value:
        return ""
    path = Path(value)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(REPO_ROOT).as_posix()
        except ValueError:
            return path.as_posix()
    return value.replace("\\", "/").lstrip("./")


def command_pushes_main(command: str) -> bool:
    try:
        parts = shlex.split(command)
    except ValueError:
        parts = command.split()
    if len(parts) < 3 or parts[0] != "git" or parts[1] != "push":
        return False
    return any(
        ref == "main" or ref.endswith(":main") or ref.endswith("/main")
        for ref in parts[2:]
    )


def command_writes_real_data_inside_repo(command: str) -> bool:
    normalized = command.replace("\\", "/")
    blocked_markers = (
        "golden-local/",
        "/golden-local",
        "real-golden/",
        "/real-golden",
    )
    return any(marker in normalized for marker in blocked_markers)


def paths_from_tool_input(tool_input: dict) -> list[str]:
    paths: list[str] = []
    for key in ("file_path", "path"):
        value = tool_input.get(key)
        if isinstance(value, str):
            paths.append(normalized_repo_path(value))
    return paths


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError as exc:
        print(f"hook_pre_tool_guard: invalid JSON input: {exc}", file=sys.stderr)
        return 2

    tool_name = payload.get("tool_name") or payload.get("toolName")
    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}

    if tool_name == "Bash":
        command = str(tool_input.get("command", ""))
        if command_pushes_main(command):
            deny("Do not push directly to main from Claude Code. Push a feature branch or ask explicitly.")
            return 0
        if command_writes_real_data_inside_repo(command):
            deny("Real golden datasets must stay outside the repository tree.")
            return 0

    if tool_name in {"Write", "Edit", "MultiEdit"}:
        for repo_path in paths_from_tool_input(tool_input):
            if repo_path.startswith(("golden-local/", "real-golden/")):
                deny("Real golden datasets must stay outside the repository tree.")
                return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
