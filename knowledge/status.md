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
  - hotspots/judges-and-canary.md
last_validated_commit: 6a43e361b0b3e72ce833b6592e96ac86feb170c6
---

## Where things stand

Milestones 1-4 (contracts, aggregate.py + tests, plugin scaffold, schema-lint
CI, agent prompts, scripts, synthetic `golden/example`) are done.

Milestone 4's canary hand-review (2026-07-21): all 13 items in `canary/items/`
are `reviewed: true` (12 from the pilot + `cn-013`, added to cover a
`missing`-verdict gap). A live canary run since then, against a real target
skill, **failed** at the original `min_agreement=1.0` (agreement 0.9245,
8/106 mismatches, all `judge-supported-output-facts`, all `borderline: true`) — genuine
judge drift, not a stale review. Fixed via both calibration levers: a rubric
addition to `agents/judge-supported-output-facts.md`, and `min_agreement` relaxed to `0.90`
with the observed-run evidence recorded in `canary/manifest.json`'s
`description`. A rerun against the new threshold **passed** (0.9340 ≥ 0.90).
Full mismatch breakdown: [judges-and-canary.md](hotspots/judges-and-canary.md).

Plugin packaging and release automation are built: `scripts/build_plugin_zip.py`
(allowlist-based), `scripts/bump_version.py`, `.github/workflows/auto-release.yml`
and `release.yml`.

Milestone 5 (baseline-derived thresholds, report-only period, then gate) has
not started for any golden set committed to this repo — `golden/example`'s
`min_supported_to_total_output_facts_ratio`/`min_covered_to_total_reference_facts_ratio` are still
invented placeholders, not derived from a baseline.

## What this means in practice

- The canary is live-reconfirmed as of 2026-07-21 at `min_agreement=0.90` —
  don't reflexively re-run it, but any judge-prompt or model-pin change still
  requires a fresh run (see [change-playbooks.md](domains/change-playbooks.md)).
- Threshold defaults in `golden/example/manifest.json` are invented, not
  derived from a baseline — don't treat them as meaningful thresholds.
- **Real datasets must live fully outside this repo's directory, not merely
  gitignored inside it.** A directory-source local plugin marketplace install
  copies the whole working tree, `.gitignore` included, into
  `~/.claude/plugins/cache/...` — confirmed 2026-07-21, see
  [golden-and-canary.md](domains/golden-and-canary.md) and README.md's
  Install section.

## Known, accepted limitations (not bugs)

- Verbosity ratio is report-only, never a gate (anti-Goodhart diagnostic).
- Output format/duplication quality is not measured at all — deferred.
- Meta-eval (monthly hand-label of 20-30 random verdicts) is described in
  DESIGN.md §7.8 but not automated.
- A subset of `judge-supported-output-facts`'s borderline calls are model-stochastic
  (confirmed by two live reruns on identical frozen inputs producing
  different mismatch sets) — `min_agreement=0.90` absorbs this, it is not a
  bug to chase with more rubric wording.

Full rationale: `DESIGN.md` §7, §9, §10.
