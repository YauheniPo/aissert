# Run Artifacts & Results Schema

Contract for every JSON artifact produced during an eval run and consumed by
`aggregate.py`. Single source of truth; agent prompts must reference this file,
never restate a diverging copy.

Schema version: **1**

## Run directory layout

```
eval-runs/{timestamp}-{target}/
├── runs/{item}/{i}.md              # raw target-skill output (not JSON)
├── facts/{item}/{i}.json           # fact-extractor output
├── verdicts/{item}/{i}-m1.json     # judge-precision output
├── verdicts/{item}/{i}-m2.json     # judge-recall output
├── results.json                    # written by aggregate.py
└── report.md                       # written by aggregate.py (later milestone)
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

## verdicts/{item}/{i}-m1.json — judge-precision output

One verdict per **extracted** fact. The verdict set must cover the extracted
fact ids exactly: no missing ids, no unknown ids, no duplicates.

```json
{
  "verdicts": [
    {"fact_id": "f1", "verdict": "supported", "evidence": "matches gf2: ..."},
    {"fact_id": "f2", "verdict": "unsupported", "evidence": "no golden fact states this"}
  ]
}
```

- `verdict` — exactly `"supported"` or `"unsupported"`. Binary only; judges
  never output numeric scores.
- `evidence` — non-empty string: which golden fact supports it, or why nothing does.

## verdicts/{item}/{i}-m2.json — judge-recall output

One verdict per **golden** fact. Must cover the item's golden fact ids exactly.

```json
{
  "verdicts": [
    {"golden_fact_id": "gf1", "verdict": "covered", "covered_by": "f1", "evidence": "..."},
    {"golden_fact_id": "gf2", "verdict": "missing", "evidence": "no extracted fact mentions this"}
  ]
}
```

- `verdict` — exactly `"covered"` or `"missing"`.
- `covered_by` — required when `covered`; must be an id present in the run's
  facts file. Must be absent or `null` when `missing`.
- `evidence` — optional string.

Any malformed judge response (wrong id set, bad verdict value, missing required
field) is a **pipeline error, never a silent skip**.

## results.json — aggregate.py output

```json
{
  "schema_version": 1,
  "target_skill": "test-cases-writer",
  "golden_set": {
    "path": "golden/example",
    "hash": "sha256:…",
    "set_version": "1.0.0"
  },
  "model_id": "claude-sonnet-5",
  "iterations": 3,
  "thresholds": {
    "k1": 0.80,
    "k2": 0.70,
    "source": {"k1": "cli", "k2": "manifest"}
  },
  "runs": [
    {
      "item_id": "gs-001",
      "iteration": 1,
      "m1": {"supported": 8, "unsupported": 2, "total_extracted": 10, "value": 0.8},
      "m2": {"covered": 7, "missing": 3, "total_golden": 10, "value": 0.7},
      "verbosity_ratio": 1.0
    }
  ],
  "summary": {
    "m1": {"mean": 0.8, "stddev": 0.0},
    "m2": {"mean": 0.7, "stddev": 0.0},
    "verbosity_ratio_mean": 1.0
  },
  "gates": {
    "m1": {"mean": 0.8, "threshold": 0.8, "pass": true},
    "m2": {"mean": 0.7, "threshold": 0.7, "pass": true}
  },
  "verdict": "pass"
}
```

Definitions (all computed in Python, never by an LLM):

- Per run: `m1.value = supported / total_extracted`;
  `m2.value = covered / total_golden`, or the weighted sum of covered golden
  facts when the item defines non-empty `weights`
  (see golden-set-schema.md). `m2.covered` / `m2.missing` stay raw counts.
- `verbosity_ratio = total_extracted / total_golden` — anti-Goodhart diagnostic
  (recall does not punish verbosity; precision punishes length mechanically).
  Report-only, no gate.
- `summary.*.stddev` — sample stddev across all runs; `0.0` when fewer than
  2 runs. Stability is report-only for now (may become a third gate later
  via manifest).
- Gate: `verdict = "pass"` iff `mean(m1) >= k1 AND mean(m2) >= k2`
  (inclusive).
- `model_id` — target-skill model as reported by the orchestrator; `null` if
  not provided (model drift tracking, DESIGN.md §7.3).
- `runs` sorted by `(item_id, iteration)`.

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
