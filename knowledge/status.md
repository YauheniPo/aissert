---
title: Project status
kind: repo
summary: Current milestone status, what's a blocker vs a known limitation. Mirrors the DESIGN.md status line.
source_paths:
  - DESIGN.md
related_pages:
  - index.md
  - domains/eval-pipeline.md
  - domains/golden-and-canary.md
last_validated_commit: 2ea2ad69e142faeae395e4f9105cfed1c2d84969
---

## Where things stand

Milestones 1-3 (contracts, aggregate.py + tests, plugin scaffold, schema-lint
CI, agent prompts, scripts, synthetic `golden/example`) are done.

Milestone 4's canary hand-review is done (2026-07-21): all 13 items in
`canary/items/` are `reviewed: true` (12 from the pilot + `cn-013`, added to
cover a `missing`-verdict gap). Two calibration inconsistencies were found
and fixed in the pilot labels during review — see
[judges-and-canary.md](hotspots/judges-and-canary.md) for what and why.

**Not yet done, don't overstate the above:** this review hand-verified the
frozen `expected` labels against the rubric. It did not run the current live
judge agents against these inputs — that live-agreement check
(`check_canary.py` comparing fresh judge output to `expected`) happens at
eval time (`SKILL.md` step 0) and hasn't been executed since these fixes
landed. Run it once before trusting the next real eval's verdict.

Milestone 5 (baseline-derived K1/K2, report-only period, then gate) has not
started.

## What this means in practice

- The canary is reviewed, but not yet re-confirmed live — run
  `check_canary.py` against fresh judge output before trusting a
  `results.json` verdict, don't assume "canary reviewed" alone covers it.
- K1/K2 defaults in `golden/*/manifest.json` are currently invented, not
  derived from a baseline — don't treat them as meaningful thresholds yet.
- Any change to judge prompts or the model pin (`model:` in `agents/*.md`)
  requires a fresh canary run and, if it diverges, a fresh calibration
  decision, same as before this review — see the model-pin playbook in
  [change-playbooks.md](domains/change-playbooks.md).

## Known, accepted limitations (not bugs)

- Verbosity ratio is report-only, never a gate (anti-Goodhart diagnostic).
- Output format/duplication quality is not measured at all — deferred.
- Meta-eval (monthly hand-label of 20-30 random verdicts) is described in
  DESIGN.md §7.8 but not automated.

Full rationale: `DESIGN.md` §7, §10.
