---
title: Eval pipeline
kind: domain
summary: The core idea (binary fact-level verdicts instead of holistic scores), the data flow, and what each agent does and doesn't see.
source_paths:
  - DESIGN.md
  - agents/fact-extractor.md
  - agents/judge-precision.md
  - agents/judge-recall.md
  - skills/aissert/SKILL.md
  - commands/eval.md
  - skills/aissert/references/results-schema.md
related_pages:
  - ../index.md
  - ../hotspots/aggregate-py.md
  - ../hotspots/judges-and-canary.md
  - golden-and-canary.md
last_validated_commit: 2ea2ad69e142faeae395e4f9105cfed1c2d84969
---

## Why not a holistic 0-100 score

High variance, not reproducible, hard to debug why a run failed. Instead:
decompose the skill's output into atomic facts, get a **binary** verdict per
fact from an isolated judge, and compute every number in deterministic
Python. Binary decisions are far more stable than holistic scores — variance
moves out of judging into honest statistics across iterations.

## Data flow, one run of one item/iteration

```
runs/{item}/{i}.md              <- target_skill output, generated with a clean-context subagent
     |
     v
fact-extractor                  <- decomposes into atomic facts (JSON), NEVER sees golden data
     |  facts/{item}/{i}.json
     |------------------.
     v                   v
judge-precision      judge-recall   <- run in parallel, isolated from each other
     |                   |
     v                   v
verdicts/*-m1.json   verdicts/*-m2.json
     |___________________|
             v
       aggregate.py                 <- ALL math and the verdict, never an LLM
             v
   results.json + exit code (0 pass / 1 gate failed / 2 pipeline error)
```

This repeats `item x iterations` times per `/aissert:eval` call. Golden facts
are extracted **once**, at golden-set creation time, human-reviewed, and
never re-extracted at eval time — see
[golden-and-canary.md](golden-and-canary.md).

## Agents (`agents/*.md`)

All three: `tools: []` (never read/write files — content is pasted into the
prompt, the orchestrator persists the JSON out) and `model: claude-sonnet-5`
pinned (schema-lint enforced). Changing the pin is the highest-risk change in
this repo — see the model-pin playbook in
[change-playbooks.md](change-playbooks.md).

| Agent | Job | Sees | Never sees |
|---|---|---|---|
| `fact-extractor` | Split one raw skill output into atomic facts | the raw output only | golden facts (would bias decomposition toward the "right" answer) |
| `judge-precision` (m1) | Per extracted fact: `supported`/`unsupported` | extracted facts + golden facts | the other judge, thresholds, other iterations |
| `judge-recall` (m2) | Per golden fact: `covered`/`missing` | golden facts + extracted facts | same |

Each prompt's only calibration lever (besides the canary) is its decision
rubric + anchored right/wrong examples. If a judge systematically misjudges a
class of cases, fix the rubric/examples in `agents/judge-*.md` — never a
threshold in `manifest.json`.

## Orchestrator (`skills/aissert/SKILL.md`)

Single place that knows the whole flow. Hard discipline: it dispatches
subagents and scripts, it **never evaluates anything itself** — every number
and the verdict come from `aggregate.py`. Steps: 0. canary check → 1.
validate golden set → 2. generate (clean-context subagent per item x
iteration) → 3. extract → 4. judge (parallel) → 5. aggregate. Read the file
directly for the exact per-step contract details — this page is a map, not a
restatement.

`commands/eval.md` is a thin wrapper passing `$ARGUMENTS` through; touch it
only if the slash-command signature itself changes.
