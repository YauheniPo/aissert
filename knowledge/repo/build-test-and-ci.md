---
title: Build, test & CI
kind: repo
summary: Local dev loop for the plugin, pytest invocation, and what GitHub Actions actually runs per PR vs on demand.
source_paths:
  - tests
  - .github/workflows/ci.yml
  - .github/workflows/auto-release.yml
  - .github/workflows/release.yml
  - scripts/build_plugin_zip.py
  - scripts/bump_version.py
  - README.md
related_pages:
  - ../index.md
  - ../hotspots/aggregate-py.md
  - ../domains/change-playbooks.md
last_validated_commit: ca8ccd58befefbf93978a8b8de609aeedf85f1ac
---

## Local dev loop (plugin)

```bash
/plugin marketplace add /path/to/aissert
/plugin install aissert@aissert
```

After editing `agents/*.md` or manifests: `/reload-plugins`. `SKILL.md` edits
apply immediately, no reload needed.

Run:
```
/aissert:eval golden_set=golden/example target_skill=<skill> iterations=3
/aissert:eval golden_set=golden/example target_skill=<skill> --smoke   # 3 items x 2 iterations
```

## Tests

```bash
pytest tests/ -q
```

Python 3.12, stdlib-only (`CLAUDE.md` hard rule: add a dependency only with a
clear reason). Test files:

| File | Covers |
|---|---|
| `test_plugin_schema.py` | Manifest validity, agent/skill/command frontmatter, version sync. |
| `test_aggregate.py` | `aggregate.py` — verdict logic, sanity checks, resume, edge cases. |
| `test_check_canary.py` | `check_canary.py`. |
| `test_scripts.py` | `validate_golden.py`, `run_target.py`. |
| `test_wiki.py` | `scripts/wiki/lib.py` — frontmatter parsing, significant-change heuristics, lint checks. |

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
  the step shows failed in the job log, the job/check itself still reports
  success. Consistent with commits/pushes never being blocked on wiki state
  (see [judges-and-canary.md](../hotspots/judges-and-canary.md) for the
  analogous reasoning on canary) — this is visibility, not a gate.

**Not run on every PR** — canary eval and baseline runs. They call `claude
-p` (real API cost) and are `workflow_dispatch` + weekly only. If your change
needs canary verification (see
[change-playbooks.md](../domains/change-playbooks.md)), do it locally/by hand
before merging — CI will not catch a canary regression for you.

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
   conventional-commit subjects since the last `aissert--v*` tag, picks one
   bump level for the whole range (`type!:` → major, `feat:` → minor,
   `fix:` → patch, else → exit 3, no release), writes both manifests, commits,
   tags, pushes. Guards against re-triggering itself on the bump commit by
   checking the commit message prefix (`chore(release):`) before running.
2. `release.yml` (tag push matching `aissert--v*`) — builds the zip, checks
   the tag matches `plugin.json`'s version, publishes it as a GitHub Release
   asset.

Requires `main` to accept direct pushes from the default `GITHUB_TOKEN` —
the bump commit goes straight to `main`, not through a PR. See
[golden-and-canary.md](../domains/golden-and-canary.md) for why the zip
allowlist matters for the corporate-data boundary too, not just tidiness.
