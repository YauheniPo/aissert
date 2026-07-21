---
title: Source inventory
kind: meta
summary: Which raw repo paths are covered by which wiki page — the map scripts/wiki/changed.py uses to find coverage gaps.
source_paths:
  - agents
  - skills
  - commands
  - golden
  - canary
  - scripts
  - tests
  - DESIGN.md
  - CLAUDE.md
  - README.md
related_pages:
  - ../index.md
  - lint-rules.md
last_validated_commit: 2ea2ad69e142faeae395e4f9105cfed1c2d84969
---

Coverage = union of every page's `source_paths`. A high-signal path (see
[lint-rules.md](lint-rules.md) trigger 3) that isn't under any row below is a
wiki gap, not a project gap — `scripts/wiki/changed.py` will flag it.

| Raw path | Covered by |
|---|---|
| `DESIGN.md` | [repo/structure.md](../repo/structure.md), [domains/eval-pipeline.md](../domains/eval-pipeline.md), [status.md](../status.md) |
| `CLAUDE.md` | [lint-rules.md](lint-rules.md) (hard rules referenced throughout) |
| `README.md` | [repo/structure.md](../repo/structure.md), [repo/build-test-and-ci.md](../repo/build-test-and-ci.md) |
| `.claude-plugin/` | [repo/structure.md](../repo/structure.md) |
| `agents/fact-extractor.md` | [domains/eval-pipeline.md](../domains/eval-pipeline.md), [hotspots/judges-and-canary.md](../hotspots/judges-and-canary.md) |
| `agents/judge-precision.md`, `agents/judge-recall.md` | [hotspots/judges-and-canary.md](../hotspots/judges-and-canary.md), [domains/eval-pipeline.md](../domains/eval-pipeline.md) |
| `skills/aissert/SKILL.md`, `commands/eval.md` | [domains/eval-pipeline.md](../domains/eval-pipeline.md) |
| `skills/aissert/scripts/aggregate.py`, `validate_golden.py` | [hotspots/aggregate-py.md](../hotspots/aggregate-py.md) |
| `skills/aissert/scripts/check_canary.py` | [hotspots/judges-and-canary.md](../hotspots/judges-and-canary.md), [hotspots/aggregate-py.md](../hotspots/aggregate-py.md) |
| `skills/aissert/scripts/run_target.py` | [repo/build-test-and-ci.md](../repo/build-test-and-ci.md) |
| `skills/aissert/references/*.md` | [hotspots/aggregate-py.md](../hotspots/aggregate-py.md), [domains/eval-pipeline.md](../domains/eval-pipeline.md), [domains/golden-and-canary.md](../domains/golden-and-canary.md) |
| `golden/` | [domains/golden-and-canary.md](../domains/golden-and-canary.md) |
| `canary/` | [domains/golden-and-canary.md](../domains/golden-and-canary.md), [hotspots/judges-and-canary.md](../hotspots/judges-and-canary.md) |
| `tests/` | [repo/build-test-and-ci.md](../repo/build-test-and-ci.md), [hotspots/aggregate-py.md](../hotspots/aggregate-py.md) |
| `.github/workflows/ci.yml` | [repo/build-test-and-ci.md](../repo/build-test-and-ci.md) |
| `scripts/wiki/` | [lint-rules.md](lint-rules.md), this page |

Not covered by design, and that's fine: `eval-runs/` (gitignored run
artifacts, not source), `.claude-plugin/marketplace.json` internals beyond
what `repo/structure.md` states (single-entry manifest, low churn).
