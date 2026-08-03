# Contributing to aissert

Thanks for taking the time to improve aissert. This project is small by design:
runtime code is Python stdlib, contracts are explicit Markdown/JSON, and all
scoring math must stay deterministic.

## Good First Contributions

- Improve docs for creating golden sets.
- Add deterministic validation for golden-set quality.
- Improve `report.md` readability without changing `results.json`.
- Add tests around edge cases in `aggregate.py`, `validate_golden.py`, or
  `check_canary.py`.
- Keep plugin packaging safer and smaller.

See [ROADMAP.md](ROADMAP.md) for larger feature ideas.

## Data Boundary

Do not commit real Jira, Confluence, customer, work-system, or proprietary
snapshots. Only synthetic data belongs in this repository.

Real golden sets must live outside this repository directory, not merely in an
ignored subdirectory. Directory-source plugin installs copy the whole working
tree, including ignored files, into the Claude plugin cache.

Before opening a PR, check:

```bash
git status --short
find . -maxdepth 2 -type d -name 'golden-local' -print
```

The second command should print nothing inside the repo.

## Development Setup

Requirements:

- Python 3.12
- pytest for tests
- Claude Code if you want to run the plugin interactively

Run the deterministic checks:

```bash
pytest tests/ -q
python3 scripts/build_claude_plugin_zip.py
python3 skills/aissert/scripts/validate_golden.py golden/example --target-skill example-bug-summarizer
```

Plugin zips are built from allowlists. `golden/example/` (including its synthetic
target skill) is project-only, so do not add it to either package allowlist.
Adding a new runtime directory means updating the relevant builder intentionally.

## Commit Style

Use conventional commit subjects:

- `fix:` for bug fixes and patch releases
- `feat:` for new user-facing behavior and minor releases
- `feat!:` or `fix!:` for breaking changes and major releases
- `docs:`, `test:`, `ci:`, `chore:` for non-release-worthy maintenance

The release workflow reads commit subjects to decide the next version.

## Pull Request Checklist

- Tests pass with `pytest tests/ -q`.
- Claude plugin packaging passes with `python3 scripts/build_claude_plugin_zip.py`.
- No real or proprietary golden data is present in the repo tree.
- Any contract change updates the matching reference file under
  `skills/aissert/references/`.
- Any design deviation updates [DESIGN.md](DESIGN.md).
- New behavior has focused tests.

## Design Rules

- LLMs may extract and judge, but never compute metrics.
- `aggregate.py` owns all scoring math and exit codes.
- Agents must not receive filesystem tools.
- Golden-side facts are human-reviewed and frozen.
- Canary drift invalidates an eval run; fix the rubric, not thresholds.
