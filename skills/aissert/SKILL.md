---
name: aissert
description: Evaluate a Claude Code skill against a golden dataset with LLM-as-judge fact-level metrics. Runs the target skill N times per item, extracts atomic facts, judges precision and recall with binary verdicts, and gates on deterministic Python-computed thresholds.
---

# aissert — eval orchestrator

You are the ORCHESTRATOR. You dispatch subagents and scripts; you NEVER evaluate,
score, or judge anything yourself. All numbers and the verdict come from
`scripts/aggregate.py`. Design rationale: DESIGN.md at the repo root.

> **Status (milestone 3).** Pipeline is complete: scripts, agent prompts and the
> synthetic `golden/example` set are implemented. Not yet done: canary set and
> judge calibration (milestone 4), baseline-derived thresholds (milestone 5) —
> until then treat verdicts as uncalibrated.

## Invocation parameters

- `golden_set` — path to a golden set directory (contract:
  `references/golden-set-schema.md`)
- `target_skill` — the skill to evaluate
- `iterations` — runs of the target skill per dataset item
- `k1`, `k2` — optional gate overrides; defaults come from the set's manifest.json
- `--smoke` — 3 items × 2 iterations, for fast checks after skill edits

## Hard rules (all steps)

- Subagents never read or write files. Pass content INTO prompts; persist their
  JSON yourself, exactly at the paths below.
- Paste output contracts from `references/results-schema.md` verbatim into every
  subagent prompt (subagents have `tools: []` and cannot read the file). Never
  paraphrase a contract.
- fact-extractor never sees reference/golden data.
- Judges never see each other's verdicts, the thresholds, or other iterations.
- A malformed subagent response is a pipeline error — stop and report, never skip.

## Flow

Run directory: `eval-runs/{timestamp}-{target_skill}/` (gitignored).

1. **Validate** — run `scripts/validate_golden.py <golden_set>`. Fail fast on
   non-zero exit. Record the printed set hash.
2. **Generate** — per item × iteration: spawn a subagent with ONLY the target
   skill and the item's `input.snapshot`. Clean context is mandatory — you have
   seen the reference data, the generator must not. Save the raw output to
   `runs/{item}/{i}.md` (iterations are 1-based).
3. **Extract** — per output: `fact-extractor` agent gets the facts contract + the
   raw output. Save to `facts/{item}/{i}.json`.
4. **Judge** — per output, both judges in parallel, isolated:
   - `judge-precision`: m1 contract + extracted facts + golden facts →
     `verdicts/{item}/{i}-m1.json`
   - `judge-recall`: m2 contract + golden facts + extracted facts →
     `verdicts/{item}/{i}-m2.json`
5. **Aggregate** — run:
   ```
   python3 scripts/aggregate.py --run-dir <run_dir> --golden-set <golden_set> \
     --iterations <N> [--k1 ..] [--k2 ..] [--model-id <id>]
   ```
   Exit code is the verdict: 0 = pass, 1 = gate failed, 2 = pipeline error.
   Report the summary and `results.json` path to the user.

## Resume

Subagent calls fail sometimes; never rerun the full matrix. `aggregate.py`
exits 2 listing exactly the missing artifact paths — re-run only the steps that
produce those files, then aggregate again.
