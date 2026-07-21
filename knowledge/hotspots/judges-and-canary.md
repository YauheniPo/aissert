---
title: Judges & canary review
kind: hotspot
summary: How judge prompts get calibrated (rubric + anchored examples), the reviewed:false blocker, and a worked borderline example from the actual canary set.
source_paths:
  - agents/judge-precision.md
  - agents/judge-recall.md
  - agents/fact-extractor.md
  - canary
  - skills/aissert/references/canary-schema.md
  - tests/test_check_canary.py
related_pages:
  - ../index.md
  - ../domains/golden-and-canary.md
  - ../domains/change-playbooks.md
  - ../status.md
last_validated_commit: 2ea2ad69e142faeae395e4f9105cfed1c2d84969
---

## Current blocker (as of `status.md`)

Every item in `canary/items/` is `reviewed: false` right now — they're
pre-filled from milestone-4 pilot judge output, not yet hand-verified.
`check_canary.py` refuses to run against an unreviewed item (exit 2): a
canary that tests the judge against its own pilot output would prove
nothing. Until these are reviewed, treat every eval verdict as uncalibrated.

## The rubric IS the calibration mechanism

There is no numeric tuning knob for a judge. The only two levers are: (1)
the decision rubric + anchored right/wrong examples in `agents/judge-*.md`,
and (2) the canary set that catches when the model stops following that
rubric. If a judge is systematically wrong on some class of input, the fix
is always "add/adjust a rubric example," never "adjust K1/K2" — thresholds
live in `golden/*/manifest.json` and are about the skill, not the judge.

## `precision`'s "added specificity" rule, worked

The core precision rule: a claim is `unsupported` if it states ANY part not
in the golden facts — including extra detail the golden facts don't mention,
even if it's plausible. `canary/items/cn-004.json` (borderline, precision)
shows this concretely. Golden facts describe a language-switch bug losing
workout history; extracted facts add specifics like "Premium account",
"Pixel 8 phone", "Galaxy Tab tablet". Hand-labeled `expected`:

- `f7`/`f8` (device models) → `supported` — golden fact `gf5` explicitly
  names "Pixel 8 phone and Galaxy Tab tablet", so this specificity **is**
  grounded.
- `f9` ("Premium account") → `unsupported` — no golden fact mentions account
  tier at all; this is invented specificity, not entailed by anything.
- `f1`/`f2` (app-name / "despite months of data") → `unsupported` — same
  reasoning, added detail the golden facts never state.

The distinguishing question is always "does a golden fact literally state
this," not "is this plausible given the golden facts" — plausible-but-
unstated is exactly what `unsupported` exists to catch.

## Review workflow for an unreviewed canary item

1. Read `input.golden_facts` and `input.extracted_facts` — these are frozen,
   don't regenerate them.
2. For `judge: precision` items: decide `supported`/`unsupported` per
   extracted fact using the rubric in `agents/judge-precision.md` (the "added
   specificity" example above is the sharpest edge case to get right). For
   `judge: recall` items: decide `covered`/`missing` per golden fact using
   `agents/judge-recall.md`.
3. Correct `expected.verdicts` if the pilot got it wrong — don't just rubber
   -stamp the pre-fill.
4. Set `reviewed: true` only after doing 1-3 for real.
5. Confirm several items are `borderline: true` — if none are, the set only
   proves the judge handles the easy cases.

See [change-playbooks.md](../domains/change-playbooks.md) for what triggers
a full canary re-run (any judge prompt change, any model-pin change).
