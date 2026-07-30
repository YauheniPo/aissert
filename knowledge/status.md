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
last_validated_commit: 67069de36bdb491e51409fbecb8cd9ee2b86068a
---

## Where things stand

Milestones 1-4 (contracts, aggregate.py + tests, plugin scaffold, schema-lint
CI, agent prompts, scripts, synthetic `golden/example`) are done.

Milestone 4's canary has 15 reviewed judge items (12 pilot items, `cn-013`
for recall `missing`, and `cn-014`/`cn-015` for exact qualifier/
contradiction coverage) plus 3 reviewed extractor items. A 2026-07-21 live
canary run against a real target skill **failed** at the original pooled
`min_agreement=1.0` (agreement 0.9245,
8/106 mismatches, all `judge-supported-output-facts`, all `borderline: true`) — genuine
judge drift, not a stale review. Fixed via both calibration levers: a rubric
addition to `agents/judge-supported-output-facts.md`. The old pooled
relaxation is now scoped to a precision floor of `0.85`; recall,
non-borderline, and extractor gates are `1.0`. The observed original
precision results were `56/64 = 0.875` and `57/64 = 0.890625`.
Full mismatch breakdown: [judges-and-canary.md](hotspots/judges-and-canary.md).

Plugin packaging and release automation are built: `scripts/build_plugin_zip.py`
(allowlist-based), `scripts/bump_version.py`, `.github/workflows/auto-release.yml`
and `release.yml`.

Milestone 5 (baseline-derived thresholds, report-only period, then gate) has
not started for any golden set committed to this repo — `golden/example`'s
`min_supported_to_total_output_facts_ratio`/`min_covered_to_total_reference_facts_ratio` are still
invented placeholders, not derived from a baseline.

## What this means in practice

- The frozen labels and deterministic checker are reviewed. Agent prompts and
  contracts changed on 2026-07-28; a live step-0 canary rerun that day
  confirmed agreement for the new grouped gates after a recall rubric fix
  (recall 42/42, precision `0.9559`, extractor and non-borderline exact — see
  [judges-and-canary.md](hotspots/judges-and-canary.md)). Re-confirm again
  after any further judge-prompt or model-pin change; don't assume this
  confirmation carries forward automatically.
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
- Synthetic extractor regression cases now run in canary, but broader
  meta-eval (monthly hand-label of 20-30 random real-output samples) is still
  described in DESIGN.md §7.8 and not automated.
- A subset of `judge-supported-output-facts`'s borderline calls are model-stochastic
  (confirmed by two live reruns on identical frozen inputs producing
  different mismatch sets) — the precision `0.85` group floor absorbs this;
  it is not a bug to chase with more rubric wording. Recall, non-borderline,
  and extractor canary gates are exact.

Full rationale: `DESIGN.md` §7, §9, §10.
