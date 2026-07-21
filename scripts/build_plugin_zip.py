#!/usr/bin/env python3
"""Package the aissert plugin into a distributable zip.

Reads the version from .claude-plugin/plugin.json, checks it matches the
plugin entry in .claude-plugin/marketplace.json, and zips the repo excluding
VCS/dev/corporate-data artifacts (see EXCLUDE_DIRS/EXCLUDE_SUFFIXES below —
golden-local/ in particular must never ship, per DESIGN.md §9).

Exit codes: 0 = zip written, 2 = version mismatch or missing manifest.
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    ".idea",
    ".github",
    ".pytest_cache",
    "__pycache__",
    "eval-runs",
    "golden-local",
    "dist",
}
EXCLUDE_SUFFIXES = {".pyc"}
EXCLUDE_NAMES = {".DS_Store"}


def load_versions() -> tuple[str, str]:
    plugin_path = REPO_ROOT / ".claude-plugin" / "plugin.json"
    marketplace_path = REPO_ROOT / ".claude-plugin" / "marketplace.json"
    plugin = json.loads(plugin_path.read_text(encoding="utf-8"))
    marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))

    plugin_version = plugin["version"]
    entry = next(
        (p for p in marketplace["plugins"] if p["name"] == plugin["name"]), None
    )
    if entry is None:
        raise ValueError(
            f"marketplace.json has no plugin entry named {plugin['name']!r}"
        )
    return plugin_version, entry["version"]


def iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        if EXCLUDE_NAMES & {path.name}:
            continue
        if path.suffix in EXCLUDE_SUFFIXES:
            continue
        rel_parts = path.relative_to(root).parts
        if EXCLUDE_DIRS & set(rel_parts[:-1]):
            continue
        yield path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="output zip path (default: dist/aissert-<version>.zip)",
    )
    args = parser.parse_args(argv)

    try:
        plugin_version, marketplace_version = load_versions()
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as e:
        print(f"build_plugin_zip: cannot read plugin manifests: {e}", file=sys.stderr)
        return 2

    if plugin_version != marketplace_version:
        print(
            f"build_plugin_zip: version mismatch — plugin.json={plugin_version} "
            f"marketplace.json={marketplace_version}",
            file=sys.stderr,
        )
        return 2

    output = args.output or REPO_ROOT / "dist" / f"aissert-{plugin_version}.zip"
    output.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in iter_files(REPO_ROOT):
            zf.write(path, path.relative_to(REPO_ROOT))

    print(f"version: {plugin_version}")
    print(f"output: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
