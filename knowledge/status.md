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

Milestone 4 (pilot + judge calibration) ran end-to-end technically, but is
**not calibrated**: the canary draft built from pilot verdicts has every item
at `reviewed: false`. `check_canary.py` refuses unreviewed items by design
(see [judges-and-canary.md](hotspots/judges-and-canary.md)) — this is the
current hard blocker before any eval result can be trusted.

Milestone 5 (baseline-derived K1/K2, report-only period, then gate) has not
started; it depends on a reviewed canary.

## What this means in practice

- Until the canary is reviewed: treat any `results.json` verdict as
  **uncalibrated**, don't use it to gate a real skill.
- K1/K2 defaults in `golden/*/manifest.json` are currently invented, not
  derived from a baseline — don't treat them as meaningful thresholds yet.
- Any change to judge prompts or the model pin (`model:` in `agents/*.md`)
  makes the review-blocker worse until canary review happens — see the
  model-pin playbook in [change-playbooks.md](domains/change-playbooks.md).

## Known, accepted limitations (not bugs)

- Verbosity ratio is report-only, never a gate (anti-Goodhart diagnostic).
- Output format/duplication quality is not measured at all — deferred.
- Meta-eval (monthly hand-label of 20-30 random verdicts) is described in
  DESIGN.md §7.8 but not automated.

Full rationale: `DESIGN.md` §7, §10.
