---
title: aggregate.py — the single source of every number
kind: hotspot
summary: All scoring math, aggregation, and verdicts live here, never in an LLM. validate_golden.py and check_canary.py import its shared functions to stay in sync.
source_paths:
  - skills/aissert/scripts/aggregate.py
  - skills/aissert/scripts/validate_golden.py
  - skills/aissert/scripts/check_canary.py
  - skills/aissert/references/results-schema.md
  - tests/test_aggregate.py
related_pages:
  - ../index.md
  - ../domains/eval-pipeline.md
  - ../domains/change-playbooks.md
last_validated_commit: 6a43e361b0b3e72ce833b6592e96ac86feb170c6
---

`aggregate.py` is the most important file in the repo: it is the **only**
place that computes m1/m2, applies the min_supported_to_total_output_facts_ratio/min_covered_to_total_reference_facts_ratio gate, and
decides `verdict`.
CLAUDE.md hard rule: all scoring math and pass/fail decisions live in Python,
never delegated to an LLM.

## Shared functions — don't drift the contract in one place only

`validate_golden.py` and `check_canary.py` both `import` from `aggregate.py`
(`load_golden_set`, `PipelineError`, `_load_json`, `_require_str`,
`M1_VERDICTS`, `M2_VERDICTS`) instead of reimplementing validation. This is
deliberate: validation and aggregation physically cannot disagree on the
contract. **If you change one of these functions' behavior, both other
scripts' tests need re-checking** — `test_aggregate.py` alone isn't enough
coverage for that change.

## Exit code discipline — the distinction that matters everywhere in this repo

| Code | Meaning | What it tells you |
|---|---|---|
| 0 | Gate passed | Numbers are trustworthy, skill/judges met threshold. |
| 1 | Gate failed | Harness worked correctly; skill/judges genuinely didn't meet threshold — an expected "bad" result, not a bug. |
| 2 | Pipeline error | Malformed JSON, missing artifact, contract violation, extraction sanity-check failure. **Numbers in this run are not trustworthy** — fix the harness, don't look at the metrics. |

Never conflate 1 and 2. A skill that fails the gate (1) is doing its job
correctly and just needs improvement. A pipeline error (2) means the
measurement itself is broken.

## Key invariants to preserve when editing

- `m1 = supported / total_output_facts`; `m2 = covered / total_reference_facts` (or the
  weighted sum when the item defines non-empty `weights`).
- Extraction sanity check runs **before** any verdict is read: a run with 0
  output facts, or `count * 3 < item_median`, is a pipeline error (2), not
  a low score — garbage extraction breaks both metrics at once, so it can't
  be a "skill got worse" signal.
- `verbosity_ratio = total_output_facts / total_reference_facts` is report-only, never a
  gate — recall doesn't punish verbosity, precision punishes length
  mechanically; this is the counterweight, kept visible on purpose
  (anti-Goodhart).
- Resume mode: missing artifacts are listed by exact path (exit 2) so the
  orchestrator reruns only those, never the full item x iteration matrix —
  don't reintroduce a "just rerun everything" fallback, 500 subagent calls
  will have partial failures as routine, not exceptional.
- Golden-set hash: SHA-256 over `manifest.json` + sorted `items/*.json`.
  Changing any byte in the set changes the hash; that's the mechanism that
  invalidates old trends on data change, not a bug to "fix" by keeping the
  hash stable.
