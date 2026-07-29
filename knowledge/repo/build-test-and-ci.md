---
title: Build, test & CI
kind: repo
summary: Local dev loop for the plugin, pytest invocation, and what GitHub Actions actually runs per PR vs on demand.
source_paths:
  - .claude/settings.json
  - .claude/skills
  - .claude/agents
  - tests
  - .github/PULL_REQUEST_TEMPLATE.md
  - .github/workflows/ci.yml
  - .github/workflows/claude.yml
  - .github/CLAUDE_CODE_REVIEW_CONFIG.md
  - .github/workflows/auto-release.yml
  - .github/workflows/release.yml
  - scripts/claude
  - scripts/build_plugin_zip.py
  - scripts/bump_version.py
  - README.md
related_pages:
  - ../index.md
  - ../hotspots/aggregate-py.md
  - ../domains/change-playbooks.md
last_validated_commit: 464e7c20c4e6b2e85fe28dbb3d04f5515734b4af
---

## Local dev loop (plugin)

```bash
/plugin marketplace add /path/to/aissert
/plugin install aissert@aissert
```

After editing `agents/*.md` or manifests: `/reload-plugins`. `SKILL.md` edits
apply immediately, no reload needed.

One-command refresh from a plain terminal:
`scripts/claude/reinstall_plugin.sh` — plugin schema check, forced
uninstall+install (needed because `/plugin update` is version-gated and never
re-copies an unchanged-version working tree), then `exec claude` for a fresh
session. Must run outside a Claude Code session: the in-session sandbox
blocks writes to `~/.claude/plugins`.

For other users/teams (no clone needed) — this repo doubles as its own
marketplace (`.claude-plugin/marketplace.json`), so anyone can point at the
GitHub repo directly instead of a local path:

```
/plugin marketplace add YauheniPo/aissert
/plugin install aissert@aissert
```

Documented in README.md's "Install (for users)" section.

Run:
```
/aissert:eval golden_set=golden/example iterations=3
/aissert:eval golden_set=golden/example --smoke   # 3 items x 2 iterations
```

The example manifest selects the bundled `example-bug-summarizer`, so this
path is self-contained. `golden/example/README.md` has the one-session
`claude --plugin-dir .` flow. Pass `target_skill=<skill>` only as an explicit
manifest mismatch check or when using a different matching dataset.

## Tests

```bash
pytest tests/ -q
```

Python 3.12, stdlib-only (`CLAUDE.md` hard rule: add a dependency only with a
clear reason). Test files:

| File | Covers |
|---|---|
| `test_plugin_schema.py` | Manifest validity, agent/skill/command frontmatter, version sync, and golden target skill availability. |
| `test_aggregate.py` | `aggregate.py` — verdict logic, sanity checks, resume, edge cases. |
| `test_check_canary.py` | Strict judge artifacts, grouped gates, and tolerant extractor canary cases. |
| `test_scripts.py` | `validate_golden.py`, `run_target.py`. |
| `test_wiki.py` | `scripts/wiki/lib.py` — frontmatter parsing, significant-change heuristics, lint checks. |
| `test_claude_automation.py` | `.claude` settings, hook helpers, and `@claude` workflow wiring. |

Rule from `CLAUDE.md`: every `aggregate.py` behavior gets a unit test — it's
fully deterministic code, no excuses.

No local pytest install ships with the repo; a gitignored `.venv` works fine:
```bash
python3.12 -m venv .venv && .venv/bin/pip install pytest && .venv/bin/pytest tests/ -q
```

## CI (`.github/workflows/ci.yml`)

Three jobs, on every PR and push to `main`:

- `schema-lint` — `pytest tests/test_plugin_schema.py -q`.
- `tests` — `pytest tests/ -q` (everything, including wiki tests).
- `wiki-lint` — `python3 scripts/wiki/lint.py`, step-level `continue-on-error:
  true`. Runs on every PR so drift is visible early, but never blocks a merge:
  the step emits a warning instead of failing the job. Consistent with
  commits/pushes never being blocked on wiki state
  (see [judges-and-canary.md](../hotspots/judges-and-canary.md) for the
  analogous reasoning on canary) — this is visibility, not a gate.

**Not run on every PR** — live canary and baseline runs. They require real
model calls. Canary is mandatory as step 0 of every `/aissert:eval`, but this
repository does not yet contain the standalone scheduled workflow listed in
the roadmap. If a prompt change needs confirmation before the next eval, run
the canary locally/by hand.

## Claude Code automation

Development-time Claude Code automation lives under `.claude/` and
`scripts/claude/`; it is not part of the packaged plugin zip. The project
settings wire:

- `SessionStart` — injects the wiki read-plan.
- `PreToolUse` — blocks direct pushes to `main` and attempts to place real
  golden data under the repo tree.
- `PostToolUse` — re-checks immutable plugin identity and runtime agent
  invariants after edits.
- `Stop` — runs proportional local verification before a Claude turn ends.

Skills under `.claude/skills/` package repeated procedures (`verify`,
`wiki-maintenance`). Dev helper agents under `.claude/agents/` provide a cold
review pass, release audit, and wiki-maintenance helper; runtime eval agents
remain under top-level `agents/`.

`.github/workflows/claude.yml` enables `@claude` comments and manual
`workflow_dispatch` runs through `anthropics/claude-code-action@v1`. It uses
`.claude/settings.json`, allows only scoped Bash commands needed for status,
diff, pytest, packaging, and wiki lint, and needs the `ANTHROPIC_API_KEY`
repository secret. It grants `actions: read` so Claude can inspect CI failures
when asked.

Managed Claude Code Review is not a workflow. `.github/CLAUDE_CODE_REVIEW_CONFIG.md`
documents the intended admin-side setup for the Claude GitHub app: review PRs
on open/push, optionally support `@claude review`, post findings only, and
leave approval/blocking decisions to humans.

## Packaging & release

`scripts/build_plugin_zip.py` zips the plugin via an **allowlist**
(`.claude-plugin/`, `agents/`, `skills/`, `commands/`, `golden/example/`,
`canary/`, `README.md`, `LICENSE`), not a denylist — a new dev file
(`tests/`, `knowledge/`, `scripts/wiki/`, ...) never ships by accident, and
`golden-local/` structurally can't be in the zip since it's not on the list.
Fails (exit 2) on a `plugin.json`/`marketplace.json` version mismatch or a
missing allowlisted path. Needed for Claude Desktop's "Upload local plugin"
(no `--plugin-dir` equivalent there) and any offline install.

Releases are automatic, triggered off `main`, no manual version editing:

1. `auto-release.yml` (push to `main`) — `scripts/bump_version.py` reads
   commit subjects since the last `aissert--v*` tag, picks one bump level for
   the whole range (`type!:` → major, `feat:` → minor, everything else →
   patch), writes both manifests, commits, tags, pushes. Exit 3 is only for an
   empty commit range. Guards against re-triggering itself on the bump commit
   by checking the commit message prefix (`chore(release):`) before running.
2. `release.yml` (tag push matching `aissert--v*`) — builds the zip, checks
   the tag matches `plugin.json`'s version, publishes it as a GitHub Release
   asset.

Requires `main` to accept direct pushes from the default `GITHUB_TOKEN` —
the bump commit goes straight to `main`, not through a PR. See
[golden-and-canary.md](../domains/golden-and-canary.md) for why the zip
allowlist matters for the corporate-data boundary too, not just tidiness.
