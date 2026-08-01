---
title: Eval pipeline
kind: domain
summary: The core idea (binary fact-level verdicts instead of holistic scores), the data flow, and what each agent does and doesn't see.
source_paths:
  - DESIGN.md
  - agents/fact-extractor.md
  - agents/judge-supported-output-facts.md
  - agents/judge-expected-output-facts.md
  - skills/aissert/SKILL.md
  - skills/aissert-codex/SKILL.md
  - skills/aissert-workflow/SKILL.md
  - commands/eval.md
  - commands/smoke.md
  - skills/aissert/references/results-schema.md
related_pages:
  - ../index.md
  - ../hotspots/aggregate-py.md
  - ../hotspots/judges-and-canary.md
  - golden-and-canary.md
last_validated_commit: 464e7c20c4e6b2e85fe28dbb3d04f5515734b4af
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
judge-supported-output-facts      judge-expected-output-facts   <- run in parallel, isolated from each other
     |                   |
     v                   v
verdicts/*-supported-output-facts.json   verdicts/*-expected-output-facts.json
     |___________________|
             v
       aggregate.py                 <- ALL math and the verdict, never an LLM
             v
   results.json + exit code (0 pass / 1 gate failed / 2 pipeline error)
```

Generate and extract are each dispatched **in parallel** across every
item x iteration (independent, clean-context spawns — nothing to isolate them
from), same as the judge step. A prior real run dispatched generate/extract
sequentially instead (SKILL.md didn't say otherwise at the time) and lost
most of its wall-clock to that; the rule is now explicit in SKILL.md steps 2-3.

This repeats `item x iterations` times per `/aissert:eval` call. Golden facts
are extracted **once**, at golden-set creation time, human-reviewed, and
never re-extracted at eval time — see
[golden-and-canary.md](golden-and-canary.md).

## Agents (`agents/*.md`)

All three: `tools: []` (never read/write files — content is pasted into the
prompt, the orchestrator persists the JSON out) and `model: inherit`, which
uses the current Claude Code session model. Changing the selected session model
is the highest-risk evaluation change in this repo — see the model playbook in
[change-playbooks.md](change-playbooks.md).

| Agent | Job | Sees | Never sees |
|---|---|---|---|
| `fact-extractor` | Split one raw skill output into atomic facts | the raw output only | golden facts (would bias decomposition toward the "right" answer) |
| `judge-supported-output-facts` (precision) | Per extracted fact: `supported`/`unsupported` | extracted facts + golden facts | the other judge, thresholds, other iterations |
| `judge-expected-output-facts` (recall) | Per golden fact: `covered`/`missing` | golden facts + extracted facts | same |

Each prompt's only calibration lever (besides the canary) is its decision
rubric + anchored right/wrong examples. If a judge systematically misjudges a
class of cases, fix the rubric/examples in `agents/judge-*.md` — never a
threshold in `manifest.json`.

## Orchestrator (`skills/aissert-workflow/SKILL.md`)

Single place that knows the whole flow. Hard discipline: it dispatches
subagents and scripts, it **never evaluates anything itself** — every number
and the verdict come from `aggregate.py`. Steps: 0. canary check → 1.
validate golden set → 2. generate (clean-context subagent per item x
iteration, dispatched in parallel) → 3. extract (parallel per output) → 4.
judge (parallel) → 5. aggregate. Read the file directly for the exact
per-step contract details — this page is a map, not a restatement.

Step 0 covers all three runtime agents: frozen fact sets isolate both judge
rubrics, while separate synthetic raw-output cases regression-test extractor
splitting/deduplication without exposing it to golden facts. Canary pass/fail
is computed in Python with separate precision, recall, non-borderline, and
extractor gates.

`commands/eval.md` passes full-eval arguments through unchanged.
`commands/smoke.md` is the separate fast entry point: it supplies the internal
`--smoke` marker, fixing the matrix at 3 items × 2 iterations. Touch these
wrappers only when their slash-command signatures change.

`skills/aissert/SKILL.md` and `skills/aissert-workflow/SKILL.md` contain no
host-specific rules. Claude Code agent selection stays in `commands/*.md`; the
Codex-only `skills/aissert-codex/SKILL.md` invokes `run_codex_eval.py`, owns
its isolated-worker rules, and accepts an explicit external `SKILL.md` for a
target that is not bundled with aissert.
