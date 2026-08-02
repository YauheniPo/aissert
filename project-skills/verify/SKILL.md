---
name: verify
description: Verify repository changes after code, tests, documentation, workflow, package, or host-integration edits. Inspect staged and unstaged diffs, run the applicable deterministic checks, validate both plugin packages when relevant, and report evidence without weakening tests.
---

# Verify Aissert Changes

1. Inspect both staged and unstaged work:
   - `git status --short`
   - `git diff --stat`
   - `git diff --cached --stat`
   - read the relevant diffs, especially changed tests.
2. Run `pytest tests/ -q` for code, contracts, prompts, scripts, manifests,
   skills, hooks, workflows, or tests. Reject a change that weakens assertions,
   narrows fixtures, or skips behavior merely to pass.
3. Build every affected package:
   - `python3 scripts/build_claude_plugin_zip.py` for the `.claude-plugin/` package surface.
   - `python3 scripts/build_codex_plugin_zip.py` for the `.codex-plugin/` package surface.
   - Run both when touching shared runtime sources (`agents/`, `skills/`,
     `commands/`, `golden/example/`, `canary/`) or release/version code.
   - For integration wiring (`.claude/`, `.claude-plugin/`, `.codex-plugin/`,
     `hooks/`, `scripts/claude/`, `scripts/hooks/`), run the relevant build and
     confirm the archive contains its referenced configuration and scripts.
4. Run `python3 scripts/wiki/lint.py` for `knowledge/`, `scripts/wiki/`,
   project instructions, or integration/documentation changes.
5. Review workflow YAML and action versions after `.github/workflows/` edits.
   Do not claim a live canary or installed-plugin refresh ran unless it actually
   ran; both require their own explicit scope.
6. Report changed files, commands with exit status, and each skipped check with
   its reason. Do not modify files unless the user requested a fix or a check
   exposed a concrete defect.
