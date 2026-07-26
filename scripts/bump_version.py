#!/usr/bin/env python3
"""Bump plugin.json/marketplace.json version from conventional commits.

Scans commit subjects between the last stable `aissert--vX.Y.Z` tag (or repo
start, if none exists) and HEAD, picks ONE bump level for the whole range:

  - subject matches `type(scope)!:` (e.g. `feat!:`) -> major
  - else any `feat:`/`feat(scope):` subject -> minor
  - else any `fix:`/`fix(scope):` subject -> patch
  - else any non-empty range (docs/style/test/ci/chore/refactor/etc.) -> patch

Only the `!` subject-line marker is checked for breaking changes — footer-style
`BREAKING CHANGE:` bodies are not scanned, to keep this a subject-line-only,
single-pass tool.

Writes the bumped version into .claude-plugin/plugin.json and the matching
plugin entry in .claude-plugin/marketplace.json. Does not commit, tag, or
push — the calling workflow does that.

Exit codes: 0 = bumped (new version printed to stdout), 3 = no commits in
range (nothing printed), 2 = pipeline error (git/manifest failure).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JSON = REPO_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"

MAJOR_RE = re.compile(r"^\w+(\([^)]*\))?!:")
FEAT_RE = re.compile(r"^feat(\([^)]*\))?:")
FIX_RE = re.compile(r"^fix(\([^)]*\))?:")
STABLE_RELEASE_TAG_RE = re.compile(r"^aissert--v(\d+)\.(\d+)\.(\d+)$")


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def latest_release_tag() -> str | None:
    tags = [t for t in run_git("tag", "-l", "aissert--v*").splitlines() if t.strip()]
    if not tags:
        return None

    def version_key(tag: str) -> tuple[int, int, int] | None:
        match = STABLE_RELEASE_TAG_RE.match(tag)
        if match is None:
            return None
        return tuple(int(p) for p in match.groups())

    release_tags = [(version_key(tag), tag) for tag in tags]
    stable_release_tags = [(key, tag) for key, tag in release_tags if key is not None]
    if not stable_release_tags:
        return None
    return max(stable_release_tags)[1]


def commit_subjects_since(tag: str | None) -> list[str]:
    rev_range = f"{tag}..HEAD" if tag else "HEAD"
    return [s for s in run_git("log", rev_range, "--format=%s").splitlines() if s.strip()]


def bump_level(subjects: list[str]) -> str | None:
    if any(MAJOR_RE.match(s) for s in subjects):
        return "major"
    if any(FEAT_RE.match(s) for s in subjects):
        return "minor"
    if any(FIX_RE.match(s) for s in subjects):
        return "patch"
    if subjects:
        return "patch"
    return None


def bump(version: str, level: str) -> str:
    major, minor, patch = (int(p) for p in version.split("."))
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def write_version(new_version: str) -> None:
    plugin = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
    plugin["version"] = new_version
    PLUGIN_JSON.write_text(json.dumps(plugin, indent=2) + "\n", encoding="utf-8")

    marketplace = json.loads(MARKETPLACE_JSON.read_text(encoding="utf-8"))
    entry = next(p for p in marketplace["plugins"] if p["name"] == plugin["name"])
    entry["version"] = new_version
    MARKETPLACE_JSON.write_text(json.dumps(marketplace, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    try:
        plugin = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
        current_version = plugin["version"]
        tag = latest_release_tag()
        subjects = commit_subjects_since(tag)
    except (OSError, KeyError, ValueError, RuntimeError, json.JSONDecodeError) as e:
        print(f"bump_version: {e}", file=sys.stderr)
        return 2

    level = bump_level(subjects)
    if level is None:
        print("bump_version: no commits since last release", file=sys.stderr)
        return 3

    new_version = bump(current_version, level)
    write_version(new_version)
    print(new_version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
