---
title: Source inventory
kind: meta
summary: Which raw repo paths are covered by which wiki page — the map scripts/wiki/changed.py uses to find coverage gaps.
source_paths:
  - .claude
  - .codex
  - .codex-plugin
  - agents
  - skills
  - commands
  - golden
  - canary
  - scripts
  - project-skills
  - tests
  - DESIGN.md
  - CLAUDE.md
  - AGENTS.md
  - PROJECT_RULES.md
  - README.md
  - .worktreeinclude
related_pages:
  - ../index.md
  - lint-rules.md
last_validated_commit: 966557e7ce41bf0565e705c7a7d365197790b61f
---

Coverage = union of every page's `source_paths`. A high-signal path (see
[lint-rules.md](lint-rules.md) trigger 3) that isn't under any row below is a
wiki gap, not a project gap — `scripts/wiki/changed.py` will flag it.

| Raw path | Covered by |
|---|---|
| `DESIGN.md` | [repo/structure.md](../repo/structure.md), [domains/eval-pipeline.md](../domains/eval-pipeline.md), [status.md](../status.md) |
| `PROJECT_RULES.md`, `AGENTS.md`, `CLAUDE.md` | [repo/structure.md](../repo/structure.md), [repo/build-test-and-ci.md](../repo/build-test-and-ci.md), [lint-rules.md](lint-rules.md) |
| `README.md` | [repo/structure.md](../repo/structure.md), [repo/build-test-and-ci.md](../repo/build-test-and-ci.md) |
| `.worktreeinclude` | [repo/structure.md](../repo/structure.md) |
| `.claude/settings.json`, `.claude/skills/`, `.claude/agents/` | [repo/structure.md](../repo/structure.md), [repo/build-test-and-ci.md](../repo/build-test-and-ci.md) |
| `.codex/skills/`, `project-skills/` | [repo/structure.md](../repo/structure.md), [repo/build-test-and-ci.md](../repo/build-test-and-ci.md) |
| `.claude-plugin/`, `.codex-plugin/` | [repo/structure.md](../repo/structure.md), [repo/build-test-and-ci.md](../repo/build-test-and-ci.md) |
| `agents/fact-extractor.md` | [domains/eval-pipeline.md](../domains/eval-pipeline.md), [hotspots/judges-and-canary.md](../hotspots/judges-and-canary.md) |
| `agents/judge-supported-output-facts.md`, `agents/judge-expected-output-facts.md` | [hotspots/judges-and-canary.md](../hotspots/judges-and-canary.md), [domains/eval-pipeline.md](../domains/eval-pipeline.md) |
| `skills/aissert/SKILL.md`, `skills/aissert-codex/SKILL.md`, `skills/aissert-workflow/SKILL.md`, `commands/eval.md`, `commands/smoke.md` | [domains/eval-pipeline.md](../domains/eval-pipeline.md) |
| `golden/example/skill/` | [repo/structure.md](../repo/structure.md), [repo/build-test-and-ci.md](../repo/build-test-and-ci.md) |
| `skills/aissert/scripts/aggregate.py`, `validate_golden.py` | [hotspots/aggregate-py.md](../hotspots/aggregate-py.md) |
| `skills/aissert/scripts/check_canary.py` | [hotspots/judges-and-canary.md](../hotspots/judges-and-canary.md), [hotspots/aggregate-py.md](../hotspots/aggregate-py.md) |
| `skills/aissert/scripts/run_target.py` | [repo/build-test-and-ci.md](../repo/build-test-and-ci.md) |
| `skills/aissert/references/*.md` | [hotspots/aggregate-py.md](../hotspots/aggregate-py.md), [domains/eval-pipeline.md](../domains/eval-pipeline.md), [domains/golden-and-canary.md](../domains/golden-and-canary.md) |
| `golden/` | [domains/golden-and-canary.md](../domains/golden-and-canary.md), [repo/build-test-and-ci.md](../repo/build-test-and-ci.md) |
| `canary/items/`, `canary/extractor-items/`, `canary/manifest.json` | [domains/golden-and-canary.md](../domains/golden-and-canary.md), [hotspots/judges-and-canary.md](../hotspots/judges-and-canary.md) |
| `tests/` | [repo/build-test-and-ci.md](../repo/build-test-and-ci.md), [hotspots/aggregate-py.md](../hotspots/aggregate-py.md) |
| `.github/PULL_REQUEST_TEMPLATE.md`, `.github/workflows/ci.yml`, `snapshot.yml`, `claude.yml`, `auto-release.yml`, `release.yml`, `.github/CLAUDE_CODE_REVIEW_CONFIG.md` | [repo/build-test-and-ci.md](../repo/build-test-and-ci.md) |
| `scripts/build_claude_plugin_zip.py`, `scripts/build_codex_plugin_zip.py`, `scripts/bump_version.py` | [repo/build-test-and-ci.md](../repo/build-test-and-ci.md) |
| `scripts/claude/`, `scripts/codex/`, `scripts/hooks/` | [repo/structure.md](../repo/structure.md), [repo/build-test-and-ci.md](../repo/build-test-and-ci.md) |
| `scripts/wiki/` | [lint-rules.md](lint-rules.md), this page |

Not covered by design, and that's fine: `eval-runs/` (gitignored run
artifacts, not source), `.claude-plugin/marketplace.json` internals beyond
what `repo/structure.md` states (single-entry manifest, low churn).
