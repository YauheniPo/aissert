---
title: Golden sets & canary — two different test layers
kind: domain
summary: Golden sets test the skill; canary tests the three runtime evaluation agents. Easy to conflate, and conflating them breaks the harness's trust model.
source_paths:
  - skills/aissert/references/golden-set-schema.md
  - skills/aissert/references/canary-schema.md
  - golden/example
  - canary
related_pages:
  - ../index.md
  - eval-pipeline.md
  - ../hotspots/judges-and-canary.md
last_validated_commit: 966557e7ce41bf0565e705c7a7d365197790b61f
---

## The distinction that matters

- **Golden set** (`golden/<target-skill>/`) answers: *is the skill good at
  its job?* One set per target skill.
- **Canary** (`canary/`) answers: *are the extractor and judges still behaving
  the way a human calibrated them to?* Tests the measuring instrument, not
  the skill under test.

If you only remember one thing from this page: after changing a judge prompt
or the active model, a passing golden-set eval proves nothing if the canary
hasn't been re-reviewed — you'd be measuring the skill with a broken ruler
and not know it.

## Golden set (contract: `golden-set-schema.md`)

```
golden/<target-skill>/
├── manifest.json        # target_skill, set_version, owner, defaults.{min_supported_to_total_output_facts_ratio,min_covered_to_total_reference_facts_ratio}
└── items/gs-001.json    # id, input.snapshot (frozen, no live fetches), reference.reference_facts, weights
```

`reference_facts` are extracted once at set-creation time and human-reviewed —
never re-extracted at eval time (would make the harness grade the
fact-extractor against itself). `weights` affects **recall only**;
empty `{}` = uniform. Set hash (SHA-256 over manifest + all items) links a
`results.json` to the exact data version — changing any byte = new baseline,
old trends stop being comparable, and that's by design, not a regression.

**`reference_facts` must be complete with respect to the snapshot, not just
correct.** Precision is judged as "output ⊆ reference_facts" — the judge never
sees the snapshot. So any fact the skill legitimately reports from the input
but the reference list omits is scored `unsupported`, and precision drops for a
skill that did nothing wrong. Symptom: an eval fails precision while recall
stays at `1.0` and every `unsupported` evidence line reads "no reference fact
states this" about something plainly present in `input.snapshot`. Fix the set,
not the skill: fold qualifiers (place, timing, exact wording) into the existing
fact they belong to, and add genuinely separate observations as new facts.

**Data boundary, hard rule:** no corporate data (real Jira/Confluence
snapshots) in this repo, ever. `golden/example/` is synthetic (fictional
"Meridian" fitness app) and doubles as the CI fixture. Its
`golden/example/skill/` target is a project-only fixture, excluded from both
release plugin archives. Real sets live in internal GitLab, passed by path via
the `golden_set` parameter.

**Gitignore is not enough — real sets must live outside the repo tree
entirely.** A local "directory"-source plugin marketplace install
(`/plugin marketplace add ./`) copies the whole working tree into
`~/.claude/plugins/cache/...` verbatim, `.gitignore` included — a gitignored
`golden-local/` folder *inside* the repo still leaks into that global cache on
every install/reinstall, just outside git history instead of inside it. Real
sets need a path outside the repo directory (e.g. `~/golden-sets/<skill>/`),
not merely gitignored, or they leak on every reinstall regardless.

## Canary (contract: `canary-schema.md`)

Judge items freeze **one judge's exact input** — golden facts + extracted
facts — plus hand-labeled `expected` verdicts. Separate extractor items freeze
raw output and use tolerant structural/content anchors rather than exact
paraphrase text. Before every eval, the orchestrator reruns the matching
runtime agent and `check_canary.py` compares. Divergence means the **whole
eval run is invalid**.

`reviewed: false` until a human hand-verifies `expected` —
`check_canary.py` refuses unreviewed items outright (exit 2), because a
canary pre-filled from judge output and never reviewed would just test the
judge against itself. See [judges-and-canary.md](../hotspots/judges-and-canary.md)
for the review workflow and a worked borderline example.

`borderline: true` marks a deliberately hard judge case. The manifest keeps
an overall floor, per-judge floors, an exact non-borderline gate, and an exact
extractor gate. Precision is the only relaxed group (`0.85`, below the
observed original-set floor of `56/64 = 0.875`); recall, non-borderline cases,
and extractor cases remain `1.0`. This prevents a recall regression from
being hidden inside pooled precision noise.

Same data-boundary rule as golden sets: only synthetic canary items here.
