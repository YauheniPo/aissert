---
name: aissert-workflow
description: Internal platform-neutral workflow and contracts for fact-level aissert evaluations. Use through a platform adapter to validate a golden set, run isolated generation, extraction and judging, and aggregate deterministic gates.
---

# aissert evaluation workflow

Act as an orchestrator: dispatch runtime workers and scripts; never evaluate,
score, or judge. Metrics and the verdict come only from `aggregate.py`.

Parameters: `golden_set`, optional `target_skill`, `iterations`, optional
`model_id`, optional gate overrides, and smoke mode (3 items × 2 iterations).
If `target_skill` is omitted, use the value printed by validation.

## Invariants

- Runtime templates in `agents/` are the single source of truth. Workers never
  read or write files; the orchestrator persists their outputs with 2-space JSON.
- Paste the applicable output contract from `skills/aissert/references/results-schema.md`
  verbatim into every worker task.
- The extractor never receives golden data. The judges never receive each
  other's verdicts, thresholds, or other iterations.
- Treat malformed worker output as a pipeline error; do not skip it.

Run directory: `eval-runs/{timestamp}-{target_skill}/`.

## Flow

0. If `canary/` exists, run every frozen item with its matching runtime template:
   precision → `judge-supported-output-facts`, recall →
   `judge-expected-output-facts`, extractor items → `fact-extractor` with only
   `raw_output`. Save each result to `canary/<id>.json`, then run
   `check_canary.py`. A non-zero result invalidates the run.
1. Run `validate_golden.py <golden_set>` and fail fast. Pass
   `--target-skill` only when the user supplied it.
2. For every item and iteration, run the target skill with only
   `input.snapshot`; save `runs/{item}/{i}.md`.
3. Extract facts from each raw output; save `facts/{item}/{i}.json`.
4. Run both isolated judges for each extraction; save
   `verdicts/{item}/{i}-supported-output-facts.json` and
   `verdicts/{item}/{i}-expected-output-facts.json`.
5. Run `aggregate.py --run-dir <run_dir> --golden-set <golden_set> --iterations <N>`
   with supplied overrides and `model_id`. Exit 0 is pass, 1 gate failure, 2
   pipeline failure. Report the summary and `results.json`.

Dispatch independent calls in parallel. On resume, regenerate only missing or
malformed artifacts; `aggregate.py` lists their exact paths.
