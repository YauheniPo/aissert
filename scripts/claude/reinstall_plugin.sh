#!/usr/bin/env bash
# Refresh the locally installed aissert plugin from this repo's working tree.
#
# The plugin is installed from a directory-source marketplace pointing at this
# repo, and `claude plugin update` is version-gated: while plugin.json keeps
# the same version it never re-copies the working tree. Forcing a fresh cache
# copy requires uninstall + install.
#
# Run from a plain terminal (NOT inside a Claude Code session sandbox —
# writes to ~/.claude/plugins are blocked there):
#   scripts/claude/reinstall_plugin.sh
#
# Exit codes: 0 = reinstalled, non-zero = schema check or claude CLI failed.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLUGIN_ID="aissert@aissert"

command -v claude >/dev/null 2>&1 || {
  echo "error: claude CLI not found in PATH" >&2
  exit 2
}

echo "==> Build check: plugin schema invariants"
python3 -m pytest "$REPO_ROOT/tests/test_plugin_schema.py" -q

echo "==> Ensure directory-source marketplace 'aissert' is registered"
if ! claude plugin marketplace list 2>/dev/null | grep -q 'aissert'; then
  claude plugin marketplace add "$REPO_ROOT"
fi

echo "==> Reinstall $PLUGIN_ID (uninstall is best-effort on first install)"
claude plugin uninstall "$PLUGIN_ID" || true
claude plugin install "$PLUGIN_ID"

echo "==> Installed state"
claude plugin list 2>/dev/null | grep -i aissert || true

echo
echo "Done. Launching a new Claude Code session in $REPO_ROOT ..."
echo "Try: /aissert:smoke golden_set=golden/example"
cd "$REPO_ROOT"
exec claude
