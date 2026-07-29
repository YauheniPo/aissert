# Runtime-Agent Canary Set Schema

Contract for the runtime-agent regression set (DESIGN.md §7.3). Single source
of truth.

The canary answers one question before every eval: **do the runtime evaluation
agents still behave the way a human calibrated them to?** Judge items freeze a
judge's exact input and expected verdicts. Extractor items freeze a raw output
plus tolerant structural/content anchors. The orchestrator re-runs the matching
agent and `check_canary.py` compares the result. Divergence means the eval run
is INVALID.

Judge items freeze **`fact-extractor`'s output** (`output_facts`) so judge drift
is measured independently from extractor drift. Separate extractor items use
raw output but compare fact count, ids, types, and `must_contain`/
`must_not_contain` text anchors rather than exact wording. Monthly sampled
meta-eval remains necessary
for broad real-output quality; the synthetic extractor cases are a regression
gate, not a replacement for it.

Schema version: **6** (shared with `golden-set-schema.md` via aggregate.py's
`SCHEMA_VERSION` — every time the golden set's threshold field names or
`reference_facts`/`output_facts` fields get renamed, this bumps too, even
though this contract's own shape didn't change)

## Directory layout

```
canary/
├── manifest.json
├── items/
│   ├── cn-001.json
│   └── cn-002.json
└── extractor-items/
    └── cx-001.json
```

## manifest.json

```json
{
  "schema_version": 6,
  "description": "runtime-agent regression set",
  "min_agreement": 0.90,
  "min_agreement_by_judge": {
    "precision": 0.85,
    "recall": 1.0
  },
  "min_non_borderline_agreement": 1.0,
  "min_extractor_agreement": 1.0
}
```

- `min_agreement` — overall judge-verdict floor.
- `min_agreement_by_judge` — optional per-judge floors; omitted keys inherit
  `min_agreement`. Use this to prevent drift in one judge from being hidden by
  another judge's stable verdicts.
- `min_non_borderline_agreement` — exactness floor across ordinary judge cases;
  defaults to `1.0`.
- `min_extractor_agreement` — fraction of extractor items with no mismatch;
  defaults to `1.0`.

All thresholds are numbers in `(0, 1]`. Relax only the affected group and only
with repeated evidence that its reviewed borderline cases legitimately
oscillate.

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

The checker validates both frozen input arrays against their main schemas and
requires the expected verdict ids to cover the applicable frozen ids exactly.

## Extractor item (`extractor-items/<id>.json`)

```json
{
  "id": "cx-001",
  "reviewed": true,
  "raw_output": "Tap 'Forgot password' and verify a reset link arrives.",
  "expected": {
    "facts": [
      {
        "id": "f1",
        "type": "action",
        "must_contain": ["Forgot password"],
        "must_not_contain": []
      }
    ],
    "must_not_contain": ["invented root cause"]
  }
}
```

Expected ids must be sequential `f1..fN`. The actual facts must have exactly
those ids and types. Substring comparisons are case-insensitive. An empty
`expected.facts` array explicitly checks the extractor's no-claims path.

## Comparison rules (check_canary.py)

- Actual agent outputs are stored one file per canary item:
  `<verdicts-dir>/<canary-item-id>.json`, in the exact judge output contract
  or facts contract from results-schema.md.
- Judge actuals are validated by the same functions as `aggregate.py`;
  malformed evidence, ids, or `covered_by` are pipeline errors.
- All overall, per-judge, non-borderline, and extractor gates must pass.
- Exit codes: `0` all grouped gates pass; `1` runtime-agent divergence, so the
  eval run is invalid; `2` pipeline error (unreviewed items, missing files,
  malformed JSON).

## Data boundary

Same rule as golden sets: only synthetic canary items in this repo. A canary
built from corporate pilot outputs lives next to its golden set in internal
storage.
