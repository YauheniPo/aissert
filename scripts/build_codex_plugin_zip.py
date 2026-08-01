#!/usr/bin/env python3
"""Package the Codex variant of the aissert plugin into a distributable zip.

The archive has ``.codex-plugin/plugin.json`` at its root, so it can be used
as an offline Codex plugin artifact. The GitHub marketplace consumes the same
repository root, which is also the single source of truth for Claude Code.

Exit codes: 0 = archive written, 2 = invalid/missing Codex manifest or source.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / ".codex-plugin" / "plugin.json"
SEMVER_RE = re.compile(
    r"\d+\.\d+\.\d+(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)
EXCLUDE_NAMES = {".DS_Store", "__pycache__"}
EXCLUDE_SUFFIXES = {".pyc"}
INCLUDE_PATHS = [
    ".codex-plugin",
    "agents",
    "skills/aissert/SKILL.md",
    "skills/aissert-codex/SKILL.md",
    "skills/aissert-workflow/SKILL.md",
    "skills/aissert/references",
    "skills/aissert/scripts/aggregate.py",
    "skills/aissert/scripts/check_canary.py",
    "skills/aissert/scripts/run_codex_eval.py",
    "skills/aissert/scripts/validate_golden.py",
    "skills/example-bug-summarizer",
    "golden/example",
    "canary",
    "README.md",
    "LICENSE",
]


def load_version() -> str:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for field in ("name", "version", "description", "author", "interface"):
        if not manifest.get(field):
            raise ValueError(f"Codex manifest is missing required field {field!r}")
    if manifest["name"] != "aissert":
        raise ValueError("Codex manifest name must be 'aissert'")
    version = manifest["version"]
    if not isinstance(version, str) or SEMVER_RE.fullmatch(version) is None:
        raise ValueError(
            "Codex manifest version must be a SemVer release, prerelease, or "
            "build-metadata version"
        )
    if not (REPO_ROOT / "skills" / "aissert" / "SKILL.md").is_file():
        raise ValueError("Codex package is missing the aissert skill")
    return version


def iter_files():
    for relpath in INCLUDE_PATHS:
        source = REPO_ROOT / relpath
        if not source.exists():
            raise FileNotFoundError(f"required Codex package path is missing: {relpath}")
        paths = sorted(source.rglob("*")) if source.is_dir() else [source]
        for path in paths:
            if not path.is_file() or path.name in EXCLUDE_NAMES:
                continue
            if path.suffix in EXCLUDE_SUFFIXES or any(part in EXCLUDE_NAMES for part in path.parts):
                continue
            yield path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        version = load_version()
        output = args.output or REPO_ROOT / "dist" / f"aissert-codex-{version}.zip"
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in iter_files():
                archive.write(path, path.relative_to(REPO_ROOT))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"build_codex_plugin_zip: {error}", file=sys.stderr)
        return 2
    print(f"version: {version}")
    print(f"output: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
