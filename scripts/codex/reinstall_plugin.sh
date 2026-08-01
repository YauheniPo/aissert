#!/usr/bin/env bash
# Refresh the locally installed aissert Codex plugin from this repository.
#
# Codex keys a local plugin cache by its manifest version.  The cachebuster
# appends a temporary local suffix, after which `plugin add` installs the fresh
# tree from the directory-source marketplace.
#
# Run from a plain terminal (not from a sandboxed Codex turn, which cannot
# write the Codex plugin cache):
#   scripts/codex/reinstall_plugin.sh
#
# Exit codes: 0 = reinstalled, non-zero = prerequisite, build, or Codex CLI
# failure.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MARKETPLACE="aissert"
PLUGIN_ID="aissert@${MARKETPLACE}"
CODEX_SKILLS_ROOT="${CODEX_HOME:-$HOME/.codex}/skills"
CACHEBUSTER_SCRIPT="${CODEX_SKILLS_ROOT}/.system/plugin-creator/scripts/update_plugin_cachebuster.py"
PYTHON_BIN="${AISSERT_PYTHON:-$REPO_ROOT/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

command -v codex >/dev/null 2>&1 || {
  echo "error: codex CLI not found in PATH" >&2
  exit 2
}

[[ -f "$CACHEBUSTER_SCRIPT" ]] || {
  echo "error: Codex plugin cachebuster not found: $CACHEBUSTER_SCRIPT" >&2
  echo "Install the plugin-creator skill, or set CODEX_HOME to its Codex home." >&2
  exit 2
}

echo "==> Build check: Codex manifest and package"
"$PYTHON_BIN" -m pytest "$REPO_ROOT/tests/test_plugin_schema.py" "$REPO_ROOT/tests/test_claude_automation.py" -q
"$PYTHON_BIN" "$REPO_ROOT/scripts/build_codex_plugin_zip.py"

echo "==> Ensure directory-source marketplace '$MARKETPLACE' is registered"
if ! codex plugin marketplace list 2>/dev/null | grep -Fq "$REPO_ROOT/.agents/plugins/marketplace.json"; then
  codex plugin marketplace add "$REPO_ROOT"
fi

echo "==> Update local plugin cachebuster"
"$PYTHON_BIN" "$CACHEBUSTER_SCRIPT" "$REPO_ROOT"

echo "==> Reinstall $PLUGIN_ID"
codex plugin add "$PLUGIN_ID" --json

echo "==> Installed state"
codex plugin list 2>/dev/null | grep -F "$PLUGIN_ID" || true

echo
echo "Done. Launching a new Codex session in $REPO_ROOT ..."
echo "Try: run the aissert skill with golden_set=golden/example"
cd "$REPO_ROOT"
exec codex
