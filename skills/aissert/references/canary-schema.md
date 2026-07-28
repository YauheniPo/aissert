# Canary Set Schema

Contract for the judge regression set (DESIGN.md §7.3). Single source of truth.

The canary answers one question before every eval: **do the judges still decide
the way a human calibrated them to?** Each item freezes a judge's exact input
(reference facts + output facts) and the hand-labeled expected verdicts. The
orchestrator re-runs the judges on these frozen inputs and `check_canary.py`
compares the verdicts. Divergence = the judge (model or rubric) drifted — the
eval run is INVALID; fix the rubric, never the thresholds or the skill.

The canary freezes **`fact-extractor`'s output** (`output_facts`), not the
target skill's raw output text: fact extraction is itself nondeterministic, so
expected verdicts can only be pinned to a frozen fact set, not to a raw output
that would produce different facts on every re-extraction. The extractor is
calibrated separately via monthly meta-eval (DESIGN.md §7.8).

Schema version: **4** (shared with `golden-set-schema.md` via aggregate.py's
`SCHEMA_VERSION` — every time the golden set's threshold field names or
`reference_facts`/`output_facts` fields get renamed, this bumps too, even
though this contract's own shape didn't change)

## Directory layout

```
canary/
├── manifest.json
└── items/
    ├── cn-001.json
    └── cn-002.json
```

## manifest.json

```json
{
  "schema_version": 4,
  "description": "judge regression set built from the milestone-4 pilot",
  "min_agreement": 1.0
}
```

- `min_agreement` — number in (0, 1]: minimum fraction of matching verdicts
  across all items for the canary to pass. Start at 1.0 (any flip = drift);
  relax only with evidence that a specific borderline case legitimately
  oscillates.

## Item file (`items/<id>.json`)

```json
{
  "id": "cn-001",
  "judge": "precision",
  "borderline": false,
  "reviewed": false,
  "source": {"golden_item": "gs-001", "iteration": 1, "note": "pilot 2026-07-21"},
  "input": {
    "reference_facts": [{"id": "gf1", "text": "..."}],
    "output_facts": [{"id": "f1", "type": "...", "text": "..."}]
  },
  "expected": {
    "verdicts": [{"fact_id": "f1", "verdict": "supported"}]
  }
}
```

| Field | Meaning |
|---|---|
| `judge` | `precision` or `recall` — which judge this item tests. |
| `borderline` | Deliberately hard case (paraphrase limit, granularity mismatch, partial overlap). The set MUST contain several. |
| `reviewed` | `false` until a human has hand-verified `expected`. **check_canary.py refuses unreviewed items** — a canary pre-filled from judge output and never reviewed would only test the judge against itself. |
| `source` | Provenance, informational only. |
| `input.reference_facts` | Frozen reference facts (contract: golden-set-schema.md). |
| `input.output_facts` | Frozen skill-output facts (contract: results-schema.md `facts`). |
| `expected.verdicts` | Hand-labeled truth. For `precision`: one per extracted fact, `fact_id` + `verdict` (`supported`/`unsupported`). For `recall`: one per reference fact, `reference_fact_id` + `verdict` (`covered`/`missing`). Evidence/`covered_by` are NOT compared — only verdict values. |

## Comparison rules (check_canary.py)

- Actual judge outputs are stored one file per canary item:
  `<verdicts-dir>/<canary-item-id>.json`, in the exact judge output contract
  from results-schema.md.
- Actual verdict ids must cover the expected ids exactly; a malformed judge
  response is a pipeline error (exit 2), never a mismatch.
- Agreement = matching verdict values / total expected verdicts, pooled across
  all items.
- Exit codes: `0` agreement >= min_agreement; `1` divergence — judges drifted,
  the eval run is invalid; `2` pipeline error (unreviewed items, missing files,
  malformed JSON).

## Data boundary

Same rule as golden sets: only synthetic canary items in this repo. A canary
built from corporate pilot outputs lives next to its golden set in internal
storage.
