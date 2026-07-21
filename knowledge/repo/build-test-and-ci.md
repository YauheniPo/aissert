---
title: Build, test & CI
kind: repo
summary: Local dev loop for the plugin, pytest invocation, and what GitHub Actions actually runs per PR vs on demand.
source_paths:
  - tests
  - .github/workflows/ci.yml
  - README.md
related_pages:
  - ../index.md
  - ../hotspots/aggregate-py.md
  - ../domains/change-playbooks.md
last_validated_commit: 2ea2ad69e142faeae395e4f9105cfed1c2d84969
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

Two jobs, on every PR and push to `main`:

- `schema-lint` — `pytest tests/test_plugin_schema.py -q`.
- `tests` — `pytest tests/ -q` (everything, including wiki tests).

**Not run on every PR** — canary eval and baseline runs. They call `claude
-p` (real API cost) and are `workflow_dispatch` + weekly only. If your change
needs canary verification (see
[change-playbooks.md](../domains/change-playbooks.md)), do it locally/by hand
before merging — CI will not catch a canary regression for you.

There is currently no CI job for wiki lint — `python3 scripts/wiki/lint.py`
runs at SessionStart locally, not as a merge gate (by design: commits/pushes
are never blocked on wiki state, see
[judges-and-canary.md](../hotspots/judges-and-canary.md) for the analogous
reasoning on canary). If wiki drift becomes a recurring problem, adding
`scripts/wiki/lint.py` as a third CI job is a reasonable, cheap addition — not
done yet because there's no evidence of drift yet.
