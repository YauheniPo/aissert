# Run Artifacts & Results Schema

Contract for every JSON artifact produced during an eval run and consumed by
`aggregate.py`. Single source of truth; agent prompts must reference this file,
never restate a diverging copy.

Schema version: **6** (same shared `SCHEMA_VERSION` constant as
`golden-set-schema.md` and `canary-schema.md`)

## Run directory layout

```
eval-runs/{timestamp}-{target}/
├── runs/{item}/{i}.md              # raw target-skill output (not JSON)
├── facts/{item}/{i}.json           # fact-extractor output
├── verdicts/{item}/{i}-supported-output-facts.json # judge-supported-output-facts output
├── verdicts/{item}/{i}-expected-output-facts.json  # judge-expected-output-facts output
├── results.json                    # written by aggregate.py
└── report.md                       # compact human-readable summary
```

`{item}` is the golden item id, `{i}` is the iteration number, **1-based**
(`1.json` … `N.json`). The layout is addressable: aggregate.py derives the full
expected artifact list from the golden set and `--iterations`, and any missing
file is a pipeline error (exit 2) listing exact paths — the orchestrator re-runs
only those (resume), never the whole matrix.

Agents never read or write these files; the orchestrator passes content in and
persists their JSON out.

## facts/{item}/{i}.json — fact-extractor output

```json
{
  "facts": [
    {"id": "f1", "type": "action", "text": "one atomic verifiable claim"},
    {"id": "f2", "type": "expectation", "text": "another atomic claim"}
  ]
}
```

- `id` — non-empty string, unique within the file.
- `type` — non-empty string; vocabulary is defined by the fact-extractor prompt,
  aggregate.py treats it as opaque.
- `text` — non-empty string; one fact = one verifiable claim.
- An empty `facts` array is valid JSON but always fails the extraction sanity
  check (below).
- Unknown extra keys are ignored.

## verdicts/{item}/{i}-supported-output-facts.json — judge-supported-output-facts output

One verdict per **extracted** fact. The verdict set must cover the extracted
fact ids exactly: no missing ids, no unknown ids, no duplicates.

```json
{
  "verdicts": [
    {"fact_id": "f1", "verdict": "supported", "evidence": "matches gf2: ..."},
    {"fact_id": "f2", "verdict": "unsupported", "evidence": "no reference fact states this"}
  ]
}
```

- `verdict` — exactly `"supported"` or `"unsupported"`. Binary only; judges
  never output numeric scores.
- `evidence` — non-empty string: which reference fact supports it, or why nothing does.

## verdicts/{item}/{i}-expected-output-facts.json — judge-expected-output-facts output

One verdict per **reference** fact. Must cover the item's reference fact ids exactly.

```json
{
  "verdicts": [
    {"reference_fact_id": "gf1", "verdict": "covered", "covered_by": "f1", "evidence": "..."},
    {"reference_fact_id": "gf2", "verdict": "missing", "evidence": "no extracted fact mentions this"}
  ]
}
```

- `verdict` — exactly `"covered"` or `"missing"`.
- `covered_by` — required when `covered`; must be an id present in the run's
  facts file. Must be absent or `null` when `missing`.
- `evidence` — required non-empty string. For `covered`, name the output fact
  that carries the core assertion and any additional output fact ids needed to
  cover the full reference claim. For `missing`, state which part is absent or
  contradicted.

Any malformed judge response (wrong id set, bad verdict value, missing required
field) is a **pipeline error, never a silent skip**.

## results.json — aggregate.py output

```json
{
  "schema_version": 6,
  "target_skill": "test-cases-writer",
  "golden_set": {
    "path": "golden/example",
    "hash": "sha256:…",
    "set_version": "1.0.0",
    "owner": "epopovich"
  },
  "model_id": "provider/active-session-model",
  "iterations": 3,
  "thresholds": {
    "min_supported_to_total_output_facts_ratio": 0.80,
    "min_covered_to_total_reference_facts_ratio": 0.70,
    "source": {"min_supported_to_total_output_facts_ratio": "cli", "min_covered_to_total_reference_facts_ratio": "manifest"}
  },
  "runs": [
    {
      "item_id": "gs-001",
      "iteration": 1,
      "supported_to_total_output_facts_ratio": {"supported": 8, "unsupported": 2, "total_output_facts": 10, "value": 0.8},
      "covered_to_total_reference_facts_ratio": {"covered": 7, "missing": 3, "total_reference_facts": 10, "value": 0.7},
      "verbosity_ratio": 1.0,
      "diagnostics": {
        "unsupported": [
          {"fact_id": "f9", "evidence": "No reference fact states the device model"}
        ],
        "missing": [
          {"reference_fact_id": "gf8", "evidence": "No output fact states the expiry"}
        ]
      }
    }
  ],
  "summary": {
    "supported_to_total_output_facts_ratio": {"mean": 0.8, "stddev": 0.0},
    "covered_to_total_reference_facts_ratio": {"mean": 0.7, "stddev": 0.0},
    "within_item_stability": {
      "supported_to_total_output_facts_ratio": {"stddev_mean": 0.0, "stddev_max": 0.0},
      "covered_to_total_reference_facts_ratio": {"stddev_mean": 0.0, "stddev_max": 0.0}
    },
    "per_item": [
      {
        "item_id": "gs-001",
        "supported_to_total_output_facts_ratio": {"mean": 0.8, "stddev": 0.0},
        "covered_to_total_reference_facts_ratio": {"mean": 0.7, "stddev": 0.0}
      }
    ],
    "verbosity_ratio_mean": 1.0
  },
  "gates": {
    "supported_to_total_output_facts_ratio": {"mean": 0.8, "threshold": 0.8, "pass": true},
    "covered_to_total_reference_facts_ratio": {"mean": 0.7, "threshold": 0.7, "pass": true}
  },
  "verdict": "pass"
}
```

Top-level `summary.supported_to_total_output_facts_ratio.stddev` and
`summary.covered_to_total_reference_facts_ratio.stddev` describe dispersion
across all item-iteration rows, so they include both item difficulty and
iteration noise. `within_item_stability` isolates run-to-run noise by first
computing stddev across iterations of each item, then reporting its mean and maximum.
`per_item` retains those item-level means and stddevs for diagnosis.
Each run also carries the evidence for its `unsupported` and `missing`
verdicts. `report.md` renders the first 20 such rows; the verdict JSON files
remain the complete canonical evidence.

Definitions (all computed in Python, never by an LLM):

- Per run: `supported_to_total_output_facts_ratio.value = supported / total_output_facts`;
  `covered_to_total_reference_facts_ratio.value = covered / total_reference_facts`,
  or the weighted sum of covered reference facts when the item defines non-empty
  `weights` (see golden-set-schema.md).
  `covered_to_total_reference_facts_ratio.covered` and
  `covered_to_total_reference_facts_ratio.missing` stay raw counts.
- `verbosity_ratio = total_output_facts / total_reference_facts` — anti-Goodhart diagnostic
  (recall does not punish verbosity; precision punishes length mechanically).
  Report-only, no gate.
- `summary.*.stddev` — sample stddev across all runs; `0.0` when fewer than
  2 runs. This is dispersion, not pure iteration stability.
- `summary.within_item_stability` — mean/max of per-item iteration stddev;
  report-only for now (may become a third gate later via manifest).
- Gate: `verdict = "pass"` iff
  `mean(supported_to_total_output_facts_ratio) >= min_supported_to_total_output_facts_ratio AND mean(covered_to_total_reference_facts_ratio) >= min_covered_to_total_reference_facts_ratio`
  (inclusive).
- `model_id` — target-skill model as reported by the orchestrator; `null` if
  not provided (model drift tracking, DESIGN.md §7.3).
- `runs` sorted by `(item_id, iteration)`.

## report.md — aggregate.py output

A compact Markdown rendering of the same deterministic data in `results.json`:
verdict, golden-set identity, gate summary, within-item stability, up to 20
unsupported/missing evidence rows, verbosity, and both named ratio values per run.
`results.json` remains canonical for machines and trend storage.

## Extraction sanity check

Garbage extraction breaks both metrics at once, so it is a **pipeline failure,
not a skill failure**. Per item, over its iterations' extracted-fact counts:

- any run with `0` facts, or
- any run with fewer than 1/3 of the item's median fact count (strictly
  `count * 3 < median`)

→ aggregate.py exits 2 without writing results.json, listing offending runs.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Gate passed. |
| 1 | Gate failed (skill got worse). |
| 2 | Pipeline/infra error: missing artifacts, malformed JSON, contract violation, sanity-check failure. Harness broke — the numbers are not trustworthy. |
