#!/usr/bin/env python3
"""Synchronize the release version across Claude and Codex plugin manifests.

This script updates .claude-plugin/plugin.json, its marketplace entry, and
.codex-plugin/plugin.json to use the same version.

Usage:
    sync_versions.py <version>

Exit codes: 0 = success, 2 = error reading/writing manifests.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JSON = REPO_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"
CODEX_PLUGIN_JSON = REPO_ROOT / ".codex-plugin" / "plugin.json"


def sync_versions(version: str) -> int:
    try:
        # Update plugin.json
        plugin = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
        plugin["version"] = version
        PLUGIN_JSON.write_text(json.dumps(plugin, indent=2) + "\n", encoding="utf-8")

        # Update marketplace.json
        marketplace = json.loads(MARKETPLACE_JSON.read_text(encoding="utf-8"))
        entry = next(p for p in marketplace["plugins"] if p["name"] == plugin["name"])
        entry["version"] = version
        MARKETPLACE_JSON.write_text(
            json.dumps(marketplace, indent=2) + "\n", encoding="utf-8"
        )

        codex_plugin = json.loads(CODEX_PLUGIN_JSON.read_text(encoding="utf-8"))
        codex_plugin["version"] = version
        CODEX_PLUGIN_JSON.write_text(
            json.dumps(codex_plugin, indent=2) + "\n", encoding="utf-8"
        )

        print(f"✓ Synced versions to {version}")
        return 0
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as e:
        print(f"sync_versions: {e}", file=sys.stderr)
        return 2


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    if len(args) != 1:
        print("Usage: sync_versions.py <version>", file=sys.stderr)
        return 2
    return sync_versions(args[0])


if __name__ == "__main__":
    sys.exit(main())
