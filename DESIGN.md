# aissert — Design Document

LLM-as-judge eval harness for Claude Code skills. Runs a target skill against golden
datasets over N iterations, extracts atomic facts, and gates on precision/recall
thresholds. Fact-level binary verdicts instead of holistic scores; all math is
deterministic Python, never LLM.

Status: design approved, milestones 1–4 in progress: 1–3 done (contracts,
aggregate.py + tests, plugin scaffold, schema-lint CI, agent prompts, scripts,
synthetic golden/example); milestone 4 pilot ran end-to-end, canary draft built
from pilot verdicts — awaiting hand review (reviewed: false), judge calibration
pending. This document is the source of truth. If implementation needs to deviate, update this file in the same MR/PR.

---

## 1. Core idea

Holistic 0–100 LLM scores are high-variance. Instead:

1. **fact-extractor** agent decomposes a skill's raw output into atomic facts (JSON).
2. **judge-precision** agent: for each extracted fact → binary `supported/unsupported`
   vs golden facts (metric 1 = precision / grounding).
3. **judge-recall** agent: for each golden fact → binary `covered/missing`
   (metric 2 = recall / completeness).
4. **aggregate.py** computes the numbers and the verdict. Exit code = CI gate.

```
runs/{item}/{i}.md
  └─ fact-extractor        → facts.json
       ├─ judge-precision  → verdicts_m1.json
       └─ judge-recall     → verdicts_m2.json
            └─ aggregate.py → results.json, report.md, exit code
```

Binary per-fact decisions are far more stable than holistic scores; variance moves
out of judging into honest statistics across iterations. `unsupported` facts =
hallucination clusters; `missing` facts = coverage-gap map — both with evidence.

## 2. Invocation contract

```
/aissert:eval
  golden_set: <path to dataset dir>
  target_skill: <skill to evaluate>
  iterations: N          # runs of target skill per dataset item
  k1: 0.80               # min mean precision across iterations
  k2: 0.70               # min mean recall across iterations
--smoke                  # 3 items x 2 iterations, for fast checks after skill edits
```

Defaults for k1/k2 live in the golden set's `manifest.json`; CLI values override.

## 3. Repository layout

```
aissert/
├── .claude-plugin/
│   ├── plugin.json                # name "aissert" — IMMUTABLE once published
│   └── marketplace.json           # repo is its own single-plugin marketplace
├── agents/                        # plugin-level subagents (Task tool, clean context)
│   ├── fact-extractor.md
│   ├── judge-precision.md
│   └── judge-recall.md
├── skills/
│   └── aissert/
│       ├── SKILL.md               # orchestrator: dispatch only, never evaluates
│       ├── references/
│       │   ├── golden-set-schema.md
│       │   └── results-schema.md
│       └── scripts/
│           ├── validate_golden.py
│           ├── run_target.py      # CI-only: claude -p wrapper for headless runs
│           └── aggregate.py
├── commands/
│   └── eval.md                    # thin slash-command wrapper over the skill
├── golden/
│   └── example/                   # SYNTHETIC demo set only (doubles as CI fixture)
├── canary/                        # judge regression set (references/canary-schema.md)
├── tests/                         # pytest: aggregate.py units + canary fixtures
├── .github/workflows/ci.yml
└── README.md
```

Rules:
- Agents never read/write files themselves. The orchestrator passes content in and
  saves their JSON out. Prevents nondeterministic paths and silent overwrites.
- Judges get `tools: []` in frontmatter — also mitigates prompt injection via the
  evaluated output.
- Judge model is deliberately NOT pinned. If pinning is ever added, changing the pin
  must invalidate the canary baseline.

## 4. Agents

### agents/fact-extractor.md
- Input: one raw output of the target skill. **Never sees the reference** (otherwise
  extraction bends toward the golden answer).
- Output: strict JSON `{"facts": [{"id","type","text"}]}` — atomic facts
  (one fact = one verifiable claim; compound steps must be split).
- Prompt contains atomicity rules + 3–5 anchored right/wrong decomposition examples.
- Riskiest component: garbage extraction breaks both metrics at once. Guard: sanity
  check in aggregate.py (fact count vs output size; 0 facts or <1/3 of the median
  across iterations = pipeline failure, NOT a skill failure).

Golden-side facts are extracted ONCE at golden-set creation time, human-reviewed,
and stored in the set (`reference.golden_facts`). Never re-extracted at eval time.

### agents/judge-precision.md (metric 1)
- Input: facts.json + golden_facts.
- Output per fact: `{"fact_id","verdict":"supported|unsupported","evidence"}`.

### agents/judge-recall.md (metric 2)
- Inverse direction: per golden fact → `covered|missing` with fact_id reference.

Isolation (both judges): run in parallel, never see each other's verdicts, the
thresholds, or other iterations.

Judges output NO numeric scores — binary verdicts only. All numbers come from code.

## 5. Golden set format

```
golden/<target-skill>/
├── manifest.json        # target_skill, set version, default k1/k2
└── items/
    └── gs-001.json
```

Item:
```json
{
  "id": "gs-001",
  "input": {"type": "jira", "key": "...", "snapshot": "..."},
  "reference": {"golden_facts": [{"id": "gf1", "text": "..."}]},
  "weights": {}
}
```

- `weights` are per-golden-fact recall weights and affect **m2 only**: empty `{}` =
  uniform (`m2 = covered / total_golden`); non-empty = keys exactly the item's golden
  fact ids, values sum to 1.0, `m2 = sum of weights of covered golden facts`. Weights
  never apply to precision — extracted facts have no stable identity across runs.
  Full contract: references/golden-set-schema.md.
- `input.snapshot` is mandatory — no live Jira/Confluence fetches; live inputs make
  the set nondeterministic.
- Set hash is printed by validate_golden.py and recorded in results.json. Changing
  the set = new baseline; old trends are invalid.
- One set per target skill.

## 6. Orchestrator flow (SKILL.md)

1. `validate_golden.py` — fail fast: item schema, snapshot + golden_facts present,
   unique ids, weights sum to 1.0. Prints set hash.
2. Generation: per item × N iterations — subagent with ONLY the target skill and the
   input. Clean context is mandatory (the orchestrator has seen the reference).
   Output → `eval-runs/{ts}-{target}/runs/{item}/{i}.md`.
3. Extraction, then both judges in parallel per output.
4. `aggregate.py`:
   - m1 = supported / total_extracted; m2 = covered / total_golden (per run)
   - verdict = mean(m1) >= K1 AND mean(m2) >= K2
   - reports stddev of both metrics (stability is report-only for now; may become a
     third gate later via manifest)
   - diagnostics: fact count, verbosity ratio (extracted/golden) — anti-Goodhart
     signal (recall doesn't punish verbosity; precision punishes length mechanically)
   - extraction sanity check (see §4)
   - resume mode: rebuild only missing artifacts from the addressable file layout
     (500 subagent calls WILL have partial failures; no full reruns)
   - exit code = gate
5. Report: results.json + report.md with per-item × per-metric breakdown and
   evidence for worst verdicts (failure clustering for free).

Run artifacts (`eval-runs/`, gitignored):
```
eval-runs/{timestamp}-{target}/
├── runs/{item}/{i}.md
├── facts/{item}/{i}.json
├── verdicts/{item}/{i}-m1.json, {i}-m2.json
├── results.json          # numbers, verdict, set hash, model id
└── report.md
```
Full traceability: every number resolves to a raw output + evidence without rerunning.

## 7. Known risks and mitigations (decided)

1. **KB leakage** (Tango-specific): target skills that retrieve from a knowledge base
   (e.g. test-cases-writer + Gemini FileSearch) can fetch the golden answer itself.
   Golden items must not exist in the KB, or eval mode must freeze/blank the KB
   context. If the KB stays live, its snapshot version must be recorded.
2. **Goodhart via metric asymmetry**: recall rewards fact-dumping; precision penalizes
   length. Report verbosity ratio as diagnostic even without a gate.
3. **Model drift breaks trends**: record model id in results.json. Maintain a
   **canary set**: 10–15 frozen judge inputs (golden facts + extracted facts) with
   hand-labeled expected verdicts, including deliberately borderline cases. Facts
   are frozen (not raw outputs): extraction is nondeterministic, so expected
   verdicts can only be pinned to a frozen fact set — the extractor is calibrated
   via meta-eval (§7.8) instead. Contract: references/canary-schema.md, checker:
   check_canary.py. Run before every eval; canary divergence = invalid run, fix
   the rubric, not the skill. This is the judges' regression test.
4. **Borderline "supported" semantics** (paraphrase, granularity mismatch, partial
   overlap): calibrated via borderline canary examples, not longer instructions.
5. **Premature blocking CI gate**: order is baseline run → derive K1/K2 from baseline
   (not invented) → report-only for 2–3 weeks → gate only when canary is stable and
   variance is known. A flaky gate trains the team to ignore it.
6. **Golden set ownership**: sets go stale silently as the product changes. Each set
   needs an owner and a staleness trigger; stale items get flagged, not silently kept.
7. **Format/duplication checks**: format is a deterministic linter (script, 0 LLM
   calls) — separate, later. Consolidation quality is measured by nothing yet —
   consciously deferred.
8. **Meta-eval**: monthly, hand-label 20–30 random verdicts and correlate with the
   judges. The only way to know the harness still measures reality.

## 8. CI (GitHub Actions), by cost

1. **Schema lint** (every PR, seconds): plugin.json/marketplace.json validity, agent
   and SKILL.md frontmatter, version sync between manifests.
2. **pytest** (every PR): aggregate.py units on fixtures (all deterministic logic is
   unit-testable); validate_golden.py on golden/example.
3. **Canary eval** (workflow_dispatch + weekly, NOT per-PR — cost): claude -p with
   ANTHROPIC_API_KEY secret, report-only artifact.

## 9. Data boundary (hard rule)

Public/publishable GitHub repo → NO real golden sets. Jira/test-case snapshots from
work systems are corporate data. Only the synthetic golden/example lives here; real
sets live in internal GitLab and are passed by path via the golden_set parameter.
The set hash in results.json links harness version to data version.

Repo history note: repo may go public later — nothing corporate in any commit, ever,
including temporary fixtures.

## 10. Implementation milestones

1. **Contracts first**: golden-set-schema.md, results-schema.md, aggregate.py verdict
   logic + pytest. Cheapest to fix while nothing depends on them.
2. Plugin scaffold: manifests, empty agents with frontmatter, SKILL.md skeleton,
   schema-lint CI. Local dev loop: add repo dir as a local marketplace, reinstall to
   iterate.
3. Agent prompts (extractor + 2 judges) with anchored examples; synthetic
   golden/example set.
4. Pilot on 5–10 items; **calibration**: compare judge verdicts to hand labels; bad
   correlation → fix rubrics, not thresholds. Build the canary set from pilot outputs.
5. Baseline run → derive default K1/K2 → report-only period → then gate. Optional:
   results.json → Allure launch conversion (separate CI step, not part of the skill).

Priority: canary set and baseline BEFORE polishing reports — they decide whether the
numbers can be trusted at all.
