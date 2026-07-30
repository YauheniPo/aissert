---
name: aissert
description: Evaluate a Claude Code skill against a golden dataset with LLM-as-judge fact-level metrics. Runs the target skill N times per item, extracts atomic facts, judges precision and recall with binary verdicts, and gates on deterministic Python-computed thresholds.
---

# aissert — eval orchestrator

You are the ORCHESTRATOR. You dispatch subagents and scripts; you NEVER evaluate,
score, or judge anything yourself. All numbers and the verdict come from
`scripts/aggregate.py`. Design rationale: DESIGN.md at the repo root.

> **Calibration status.** The canary set exists and is hand-reviewed (all items
> `reviewed: true`) — step 0 below is meaningful. min_supported_to_total_output_facts_ratio/min_covered_to_total_reference_facts_ratio defaults in golden-set
> manifests are not yet baseline-derived for every set; treat them as
> uncalibrated placeholders unless a set's own `CALIBRATION.md` says otherwise.
> Full rationale and current project status: DESIGN.md.

## Invocation parameters

- `golden_set` — path to a golden set directory (contract:
  `references/golden-set-schema.md`)
- `target_skill` — optional; the skill to evaluate. If omitted, use the
  `target_skill` printed by `validate_golden.py` in step 1 (the golden set's
  manifest.json). If given explicitly, it still gets passed to
  `validate_golden.py --target-skill` as a mismatch check against the manifest.
- `iterations` — runs of the target skill per dataset item
- `min_supported_to_total_output_facts_ratio`, `min_covered_to_total_reference_facts_ratio` — optional gate overrides; defaults come from
  the set's manifest.json
- smoke mode — 3 items × 2 iterations, selected by the `/aissert:smoke`
  command (the wrapper supplies the internal `--smoke` marker)

## Hard rules (all steps)

- Subagents never read or write files. Pass content INTO prompts; persist their
  JSON yourself, exactly at the paths below. Pretty-print with 2-space indent
  when writing — content must stay identical, only whitespace changes.
- Paste output contracts from `references/results-schema.md` verbatim into every
  subagent prompt (subagents have `tools: []` and cannot read the file). Never
  paraphrase a contract.
- fact-extractor never sees reference/golden data.
- Judges never see each other's verdicts, the thresholds, or other iterations.
- A malformed subagent response is a pipeline error — stop and report, never skip.

## Flow

Run directory: `eval-runs/{timestamp}-{target_skill}/` (gitignored).

0. **Canary** (when a canary set exists for this golden set, contract:
   `references/canary-schema.md`) — dispatch every canary item to its matching
   runtime agent:
   - `items/*.json` with `judge: precision` → `judge-supported-output-facts`
   - `items/*.json` with `judge: recall` → `judge-expected-output-facts`
   - `extractor-items/*.json` → `fact-extractor`, using only `raw_output` and
     the pasted facts contract (never judge inputs or golden data)

   Save each output to `<run_dir>/canary/<canary-item-id>.json`, then run
   `scripts/check_canary.py --canary-set <dir> --verdicts-dir
   <run_dir>/canary`. Dispatch independent canary calls in parallel. Non-zero
   exit means runtime-agent drift or malformed output; the whole run is
   invalid — stop, report, and do NOT proceed to evaluation.
1. **Validate** — run
   `scripts/validate_golden.py <golden_set>` (add `--target-skill <target_skill>`
   only if the user passed `target_skill` explicitly). Fail fast on non-zero
   exit. This verifies the golden-set schema and, when `--target-skill` is
   given, catches using a dataset for the wrong skill before any LLM calls.
   Record the printed set hash and `target_skill` — if the invocation omitted
   `target_skill`, use the printed value for step 2 onward.
2. **Generate** — per item × iteration: spawn a subagent with ONLY the target
   skill and the item's `input.snapshot`. Clean context is mandatory — you have
   seen the reference data, the generator must not. Save the raw output to
   `runs/{item}/{i}.md` (iterations are 1-based). All item × iteration spawns
   are independent — dispatch them in parallel (batch the calls), not one at a
   time.
3. **Extract** — per output: `fact-extractor` agent gets the facts contract + the
   raw output. Save to `facts/{item}/{i}.json`. Independent per output — dispatch
   in parallel across all outputs, not one at a time.
4. **Judge** — per output, both judges in parallel, isolated:
   - `judge-supported-output-facts`: supported-output-facts contract + extracted facts + golden facts →
     `verdicts/{item}/{i}-supported-output-facts.json`
   - `judge-expected-output-facts`: expected-output-facts contract + golden facts + extracted facts →
     `verdicts/{item}/{i}-expected-output-facts.json`
5. **Aggregate** — run:
   ```
   python3 scripts/aggregate.py --run-dir <run_dir> --golden-set <golden_set> \
     --iterations <N> [--min-supported-to-total-output-facts-ratio ..] [--min-covered-to-total-reference-facts-ratio ..] [--model-id <id>]
   ```
   Exit code is the verdict: 0 = pass, 1 = gate failed, 2 = pipeline error.
   Report the summary and `results.json` path to the user.

## Resume

Subagent calls fail sometimes; never rerun the full matrix. `aggregate.py`
exits 2 listing exactly the missing artifact paths — re-run only the steps that
produce those files, then aggregate again.
