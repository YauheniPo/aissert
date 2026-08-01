# aissert — Design Document

LLM-as-judge eval harness for Claude Code skills. Runs a target skill against golden
datasets over N iterations, extracts atomic facts, and gates on precision/recall
thresholds. Fact-level binary verdicts instead of holistic scores; all math is
deterministic Python, never LLM.

Status: design approved, milestones 1–4 done: 1–3 (contracts, aggregate.py +
tests, plugin scaffold, schema-lint CI, agent prompts, scripts, synthetic
golden/example); 4 (canary built and hand-reviewed, all items `reviewed: true`;
a live judge rerun against a real target skill found genuine
judge-supported-output-facts drift on borderline items. Canary gates are now
scoped: precision `0.85` based on the observed original-set floor, recall
`1.0`, non-borderline `1.0`, extractor `1.0` — see
knowledge/hotspots/judges-and-canary.md). `aggregate.py`
now writes both `results.json` and a compact `report.md`; richer evidence
clustering remains future polish. Milestone 5 (baseline run, min_supported_to_total_output_facts_ratio/min_covered_to_total_reference_facts_ratio derived from
it, report-only period, then gate) has not started — current min_supported_to_total_output_facts_ratio/min_covered_to_total_reference_facts_ratio in
golden/*/manifest.json are placeholders, not calibrated. This document is the
source of truth. If implementation needs to deviate, update this file in the
same MR/PR.

---

## 1. Core idea

Holistic 0–100 LLM scores are high-variance. Instead:

1. **fact-extractor** agent decomposes a skill's raw output into atomic facts (JSON).
2. **judge-supported-output-facts** agent: for each extracted fact → binary `supported/unsupported`
   vs reference facts (precision / grounding).
3. **judge-expected-output-facts** agent: for each reference fact → binary `covered/missing`
   (recall / completeness).
4. **aggregate.py** computes the numbers and the verdict. Exit code = CI gate.

```
runs/{item}/{i}.md
  └─ fact-extractor        → facts.json
       ├─ judge-supported-output-facts  → verdicts_supported_output_facts.json
       └─ judge-expected-output-facts     → verdicts_expected_output_facts.json
            └─ aggregate.py → results.json, report.md, exit code
```

Binary per-fact decisions are far more stable than holistic scores; variance moves
out of judging into honest statistics across iterations. `unsupported` facts =
hallucination clusters; `missing` facts = coverage-gap map — both with evidence.

## 2. Invocation contract

```
/aissert:eval
  golden_set: <path to dataset dir>
  target_skill: <skill to evaluate>   # optional, defaults to the manifest's target_skill
  iterations: N          # runs of target skill per dataset item
  min_supported_to_total_output_facts_ratio: 0.80    # min mean precision across iterations
  min_covered_to_total_reference_facts_ratio: 0.70       # min mean recall across iterations

/aissert:smoke
  golden_set: <path to dataset dir>
  target_skill: <skill to evaluate>   # optional, defaults to the manifest's target_skill
  min_supported_to_total_output_facts_ratio: 0.80
  min_covered_to_total_reference_facts_ratio: 0.70
  # fixed at 3 items x 2 iterations
```

Defaults for min_supported_to_total_output_facts_ratio/min_covered_to_total_reference_facts_ratio live in the golden set's `manifest.json`;
CLI values override.
`target_skill` also defaults from the manifest; pass it explicitly only to get
the preflight mismatch check (dataset vs. requested skill) in
`validate_golden.py`.

## 3. Repository layout

```
aissert/
├── .claude-plugin/
│   ├── plugin.json                # name "aissert" — IMMUTABLE once published
│   └── marketplace.json           # repo is its own single-plugin marketplace
├── agents/                        # plugin-level subagents (Task tool, clean context)
│   ├── fact-extractor.md
│   ├── judge-supported-output-facts.md
│   └── judge-expected-output-facts.md
├── skills/
│   ├── aissert/
│   │   ├── SKILL.md               # orchestrator: dispatch only, never evaluates
│   │   ├── references/
│   │   │   ├── golden-set-schema.md
│   │   │   └── results-schema.md
│   │   └── scripts/
│   │       ├── validate_golden.py
│   │       ├── run_target.py      # CI-only: claude -p wrapper for headless runs
│   │       └── aggregate.py
│   └── example-bug-summarizer/
│       └── SKILL.md               # bundled synthetic target for local evals
├── commands/
│   ├── eval.md                    # full-eval slash-command wrapper
│   └── smoke.md                   # fixed 3-item × 2-iteration wrapper
├── golden/
│   └── example/                   # SYNTHETIC demo set only (doubles as CI fixture)
├── canary/                        # runtime-agent regression set (references/canary-schema.md)
├── tests/                         # pytest: aggregate.py units + canary fixtures
├── .github/workflows/ci.yml
└── README.md
```

Rules:
- Agents never read/write files themselves. The orchestrator passes content in and
  saves their JSON out. Prevents nondeterministic paths and silent overwrites.
- Judges get `tools: []` in frontmatter — also mitigates prompt injection via the
  evaluated output.
- Runtime agents use `model: inherit`, so Claude Code evaluates them with the
  current model selected for the parent session. A session-model change still
  invalidates the canary baseline and metric trends — re-review the canary before
  comparing results across models.

## 4. Agents

### agents/fact-extractor.md
- Input: one raw output of the target skill. **Never sees the reference** (otherwise
  extraction bends toward the golden answer).
- Output: strict JSON `{"facts": [{"id","type","text"}]}` — atomic facts
  (one fact = one verifiable claim; compound steps must be split).
- Prompt contains atomicity rules + 3–5 anchored right/wrong decomposition examples.
- Riskiest component: garbage extraction breaks both metrics at once. Guard: sanity
  check in aggregate.py (fact count vs output size; 0 facts or <1/3 of the median
  across iterations = pipeline failure, NOT a skill failure), plus reviewed
  synthetic extractor canary cases for compound splitting, qualifier retention,
  deduplication, no-inference, and the empty-facts path.

Reference-side facts are extracted ONCE at golden-set creation time, human-reviewed,
and stored in the set (`reference.reference_facts`). Never re-extracted at eval time.

### agents/judge-supported-output-facts.md (precision)
- Input: facts.json + reference_facts.
- Output per fact: `{"fact_id","verdict":"supported|unsupported","evidence"}`.

### agents/judge-expected-output-facts.md (recall)
- Inverse direction: per reference fact → `covered|missing` with a validated
  `covered_by` fact id when covered and non-empty evidence for every verdict.

Isolation (both judges): run in parallel, never see each other's verdicts, the
thresholds, or other iterations.

Judges output NO numeric scores — binary verdicts only. All numbers come from code.

## 5. Golden set format

```
golden/<target-skill>/
├── manifest.json        # target_skill, set version, default min_supported_to_total_output_facts_ratio/min_covered_to_total_reference_facts_ratio
└── items/
    └── gs-001.json
```

Item:
```json
{
  "id": "gs-001",
  "input": {"type": "jira", "key": "...", "snapshot": "..."},
  "reference": {"reference_facts": [{"id": "gf1", "text": "..."}]},
  "weights": {}
}
```

- `weights` are per-reference-fact recall weights and affect
  **covered_to_total_reference_facts_ratio only**: empty `{}` = uniform
  (`covered_to_total_reference_facts_ratio = covered / total_reference_facts`);
  non-empty = keys exactly the item's reference fact ids, values sum to 1.0,
  `covered_to_total_reference_facts_ratio = sum of weights of covered reference facts`.
  Weights
  never apply to precision — output facts have no stable identity across runs.
  Full contract: references/golden-set-schema.md.
- `input.snapshot` is mandatory — no live Jira/Confluence fetches; live inputs make
  the set nondeterministic.
- Set hash is printed by validate_golden.py and recorded in results.json. Changing
  the set = new baseline; old trends are invalid.
- One set per target skill.

## 6. Orchestrator flow (SKILL.md)

0. `check_canary.py` — run the matching runtime agent over frozen judge inputs and
   synthetic extractor raw outputs. Overall, per-judge, non-borderline, and
   extractor agreement gates must all pass.
1. `validate_golden.py` — fail fast: item schema, snapshot + reference_facts present,
   unique ids, weights sum to 1.0. Prints set hash.
2. Generation: per item × N iterations — subagent with ONLY the target skill and the
   input. Clean context is mandatory (the orchestrator has seen the reference).
   Output → `eval-runs/{ts}-{target}/runs/{item}/{i}.md`.
3. Extraction, then both judges in parallel per output.
4. `aggregate.py`:
   - `supported_to_total_output_facts_ratio = supported / total_output_facts`;
     `covered_to_total_reference_facts_ratio = covered / total_reference_facts` (per run)
   - verdict = `mean(supported_to_total_output_facts_ratio) >= min_supported_to_total_output_facts_ratio`
     AND `mean(covered_to_total_reference_facts_ratio) >= min_covered_to_total_reference_facts_ratio`
   - reports all-run dispersion plus per-item iteration stddev (the latter is
     the actual stability signal; report-only for now)
   - diagnostics: fact count, verbosity ratio (extracted/golden) — anti-Goodhart
     signal (recall doesn't punish verbosity; precision punishes length mechanically)
   - extraction sanity check (see §4)
   - resume mode: rebuild only missing artifacts from the addressable file layout
     (500 subagent calls WILL have partial failures; no full reruns)
   - exit code = gate
5. Report: results.json + report.md with per-item × per-metric breakdown and
   the first 20 unsupported/missing evidence rows; verdict artifacts retain
   the complete set.

Run artifacts (`eval-runs/`, gitignored):
```
eval-runs/{timestamp}-{target}/
├── runs/{item}/{i}.md
├── facts/{item}/{i}.json
├── verdicts/{item}/{i}-supported-output-facts.json, {i}-expected-output-facts.json
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
   **canary set** with 10–15 frozen judge inputs plus a small extractor suite.
   Judge items use hand-labeled verdicts and include deliberately borderline
   cases. Extractor items compare exact fact count/id/type plus tolerant
   `must_contain`/`must_not_contain` content anchors; they do not require exact
   paraphrase wording. Overall, each judge, non-borderline cases, and extractor cases have
   separate gates so stable groups cannot hide a regression elsewhere. Contract:
   references/canary-schema.md, checker: check_canary.py. Run before every eval;
   divergence = invalid run. Monthly sampled meta-eval (§7.8) still checks broader
   extractor/judge quality beyond the synthetic regression cases.
4. **Borderline "supported" semantics** (paraphrase, granularity mismatch, partial
   overlap): calibrated via borderline canary examples, not longer instructions.
5. **Premature blocking CI gate**: order is baseline run → derive min_supported_to_total_output_facts_ratio/min_covered_to_total_reference_facts_ratio from baseline
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
3. **Wiki lint** (every PR, seconds, non-blocking): `scripts/wiki/lint.py` via
   step-level `continue-on-error: true` — visible in the job log, never fails
   the check or blocks a merge.
4. **Canary eval** is mandatory inside every `/aissert:eval`. A standalone
   `workflow_dispatch`/weekly workflow remains roadmap work because it needs API
   credentials and a headless runtime-agent dispatcher; do not claim scheduled
   coverage until that workflow exists.

## 9. Data boundary (hard rule)

Public/publishable GitHub repo → NO real golden sets. Jira/test-case snapshots from
work systems are corporate data. Only the synthetic golden/example lives here; real
sets live in internal GitLab and are passed by path via the golden_set parameter.
The set hash in results.json links harness version to data version.

Repo history note: repo may go public later — nothing corporate in any commit, ever,
including temporary fixtures.

Gitignore is not enough: a directory-source local plugin marketplace install
(`/plugin marketplace add <path>`) copies the whole working tree — `.gitignore`
included — into `~/.claude/plugins/cache/...`. Real sets must live fully outside
this repo's directory, not merely gitignored inside it (confirmed 2026-07-21,
see knowledge/domains/golden-and-canary.md).

## 10. Implementation milestones

1. **Contracts first**: golden-set-schema.md, results-schema.md, aggregate.py verdict
   logic + pytest. Cheapest to fix while nothing depends on them.
2. Plugin scaffold: manifests, empty agents with frontmatter, SKILL.md skeleton,
   schema-lint CI. Local dev loop: add repo dir as a local marketplace, reinstall to
   iterate. The synthetic `golden/example` target skill is bundled so this loop can
   be exercised without installing another plugin.
3. Agent prompts (extractor + 2 judges) with anchored examples; synthetic
   golden/example set.
4. Pilot on 5–10 items; **calibration**: compare judge verdicts to hand labels; bad
   correlation → fix rubrics, not thresholds. Build the canary set from pilot outputs.
5. Baseline run → derive default min_supported_to_total_output_facts_ratio/min_covered_to_total_reference_facts_ratio → report-only period → then gate. Optional:
   results.json → Allure launch conversion (separate CI step, not part of the skill).

Priority: canary set and baseline BEFORE polishing reports — they decide whether the
numbers can be trusted at all.
