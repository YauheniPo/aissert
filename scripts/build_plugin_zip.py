#!/usr/bin/env python3
"""Package the aissert plugin into a distributable zip.

Reads the version from .claude-plugin/plugin.json, checks it matches the
plugin entry in .claude-plugin/marketplace.json, and zips only what the
plugin needs at runtime (INCLUDE_PATHS below) — an allowlist, not a denylist:
dev-only content (tests/, knowledge/ wiki, scripts/wiki/, CLAUDE.md,
DESIGN.md, .git*, .venv, .idea) and anything outside INCLUDE_PATHS is excluded
by construction, so a new dev file added to the repo never ships by accident.
Small public project docs are included because README links to them. golden-local/
(real/corporate golden sets, see DESIGN.md §9) is never in this list.

Exit codes: 0 = zip written, 2 = version mismatch, missing manifest, or an
INCLUDE_PATHS entry that doesn't exist.
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Everything the plugin needs to load and run. Add here explicitly if the
# plugin gains a new runtime-required directory — do not widen this by
# switching back to an exclude-list.
INCLUDE_PATHS = [
    ".claude-plugin",
    "agents",
    "skills",
    "commands",
    "golden/example",
    "canary",
    "README.md",
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "ROADMAP.md",
    "SECURITY.md",
]
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
    for rel in INCLUDE_PATHS:
        base = root / rel
        if not base.exists():
            raise FileNotFoundError(f"INCLUDE_PATHS entry does not exist: {rel}")
        paths = sorted(base.rglob("*")) if base.is_dir() else [base]
        for path in paths:
            if path.is_dir():
                continue
            if path.name in EXCLUDE_NAMES:
                continue
            if path.suffix in EXCLUDE_SUFFIXES:
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

    try:
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in iter_files(REPO_ROOT):
                zf.write(path, path.relative_to(REPO_ROOT))
    except FileNotFoundError as e:
        print(f"build_plugin_zip: {e}", file=sys.stderr)
        return 2

    print(f"version: {plugin_version}")
    print(f"output: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
