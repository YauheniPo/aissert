---
title: Golden sets & canary — two different test layers
kind: domain
summary: Golden sets test the skill; canary tests the judges. Easy to conflate, and conflating them breaks the harness's trust model.
source_paths:
  - skills/aissert/references/golden-set-schema.md
  - skills/aissert/references/canary-schema.md
  - golden/example
  - canary
related_pages:
  - ../index.md
  - eval-pipeline.md
  - ../hotspots/judges-and-canary.md
last_validated_commit: 2ea2ad69e142faeae395e4f9105cfed1c2d84969
---

## The distinction that matters

- **Golden set** (`golden/<target-skill>/`) answers: *is the skill good at
  its job?* One set per target skill.
- **Canary** (`canary/`) answers: *are the judges still deciding the way a
  human calibrated them to?* Tests the measuring instrument, not the skill
  under test.

If you only remember one thing from this page: after changing a judge prompt
or the model pin, a passing golden-set eval proves nothing if the canary
hasn't been re-reviewed — you'd be measuring the skill with a broken ruler
and not know it.

## Golden set (contract: `golden-set-schema.md`)

```
golden/<target-skill>/
├── manifest.json        # target_skill, set_version, owner, defaults.{k1,k2}
└── items/gs-001.json    # id, input.snapshot (frozen, no live fetches), reference.golden_facts, weights
```

`golden_facts` are extracted once at set-creation time and human-reviewed —
never re-extracted at eval time (would make the harness grade the
fact-extractor against itself). `weights` affects **recall (m2) only**;
empty `{}` = uniform. Set hash (SHA-256 over manifest + all items) links a
`results.json` to the exact data version — changing any byte = new baseline,
old trends stop being comparable, and that's by design, not a regression.

**Data boundary, hard rule:** no corporate data (real Jira/Confluence
snapshots) in this repo, ever. `golden/example/` is synthetic (fictional
"Meridian" fitness app) and doubles as the CI fixture. Real sets live in
internal GitLab, passed by path via the `golden_set` parameter.

## Canary (contract: `canary-schema.md`)

Each item freezes **one judge's exact input** — golden facts + extracted
facts, not the raw skill output (extraction is nondeterministic, so expected
verdicts can only be pinned to a frozen fact set) — plus hand-labeled
`expected` verdicts. Before every eval, the orchestrator reruns both judges
on these frozen inputs and `check_canary.py` compares. Divergence = the
judge (model or rubric) drifted — the **whole eval run is invalid**, fix the
rubric, never a threshold.

`reviewed: false` until a human hand-verifies `expected` —
`check_canary.py` refuses unreviewed items outright (exit 2), because a
canary pre-filled from judge output and never reviewed would just test the
judge against itself. See [judges-and-canary.md](../hotspots/judges-and-canary.md)
for the review workflow and a worked borderline example.

`borderline: true` marks a deliberately hard case (paraphrase limit,
granularity mismatch, partial overlap) — the set must contain several, or
canary only calibrates the obvious cases. `manifest.json.min_agreement`
(currently `1.0`) is the minimum fraction of matching verdicts to pass;
relax only with evidence a specific borderline case legitimately oscillates.

Same data-boundary rule as golden sets: only synthetic canary items here.
