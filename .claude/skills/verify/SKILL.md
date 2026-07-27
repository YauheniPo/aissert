---
name: verify
description: Run after code, workflow, plugin, test, or documentation edits in this repository to verify the diff, execute the relevant deterministic checks, and report pass/fail evidence without weakening tests.
---

# Verify Aissert Changes

Use this skill before finishing any change that edits repository files.

## Procedure

1. Inspect the diff:
   - `git status --short`
   - `git diff --stat`
   - `git diff -- .`
2. Run checks based on touched paths:
   - Always for code/plugin changes: `pytest tests/ -q`
   - For plugin packaging, manifests, agents, skills, commands, docs linked from README, or release workflows: `python3 scripts/build_plugin_zip.py`
   - For `knowledge/` or `scripts/wiki/`: `python3 scripts/wiki/lint.py`
   - For GitHub workflow edits: review the YAML indentation and action versions in `.github/workflows/`
3. Verify test integrity:
   - If tests changed, read the test diff.
   - Fail the verification if assertions were removed, fixtures were narrowed, or behavior was skipped only to make checks pass.
4. Report:
   - changed files summary;
   - commands run and exit status;
   - any residual risk or skipped check with the reason.

Do not modify code while using this skill unless the user asked for fixes or a verification command exposes a concrete issue.
