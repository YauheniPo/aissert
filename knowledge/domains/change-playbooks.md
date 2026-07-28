---
title: Change playbooks — what to re-verify before updating
kind: domain
summary: Per change-type checklist (judge prompt, aggregate.py, model pin, golden set, canary item) — what CI does NOT catch for you.
source_paths:
  - skills/aissert/scripts/aggregate.py
  - agents/judge-supported-output-facts.md
  - agents/judge-expected-output-facts.md
  - agents/fact-extractor.md
  - canary/manifest.json
  - golden/example/manifest.json
  - .github/workflows/ci.yml
related_pages:
  - ../index.md
  - eval-pipeline.md
  - ../hotspots/aggregate-py.md
  - ../hotspots/judges-and-canary.md
last_validated_commit: 6a43e361b0b3e72ce833b6592e96ac86feb170c6
---

Baseline for any PR, always:

```bash
pytest tests/ -q
python3 skills/aissert/scripts/validate_golden.py golden/example
```

Then, by change type:

## Agent prompt (`agents/*.md`)

1. `pytest tests/test_plugin_schema.py -q` — frontmatter (`tools: []`,
   `model:` pin) unchanged.
2. Run canary: orchestrator reruns judges on `canary/items/*.json`, then
   `check_canary.py --canary-set canary --verdicts-dir <output>`. If canary
   fails (exit 1) and you **intended** to change judge behavior: expected —
   manually re-review `expected` in the affected canary items, update them.
   If it fails and you didn't touch the rubric on purpose: regression, revert.
3. `--smoke` run on `golden/example`, read `results.json` — metrics shouldn't
   move without a reason you can explain.

## Math / contract (`aggregate.py`, `results-schema.md`)

1. Update contract and code together — they must never disagree (see
   [aggregate-py.md](../hotspots/aggregate-py.md) for why `validate_golden.py`
   and `check_canary.py` share functions with `aggregate.py`).
2. Add/update a unit test in `test_aggregate.py` for the new edge case.
3. `pytest tests/ -q` — this also re-exercises `check_canary.py` and
   `validate_golden.py`, which import from `aggregate.py`.

## Model pin (`model:` in `agents/*.md`)

The most expensive change in this repo — invalidates the canary baseline and
every historical metric trend (DESIGN.md §3). Order matters:

1. Change `model:` in all three `agents/*.md` (schema lint requires the same
   pin everywhere).
2. Run canary on the new model — **expect divergence**. That's a signal to
   re-check the rubric under the new model, not a failure to suppress.
3. Hand-review every mismatched canary item: is the new model right and the
   old label wrong, or did the new model actually stop following the rubric?
   Fix `expected`/rubric on the merits, never just to make it pass.
4. Only after canary is stable again: run a new baseline. Old `results.json`
   history from before the pin change is not comparable — expected, not a
   regression.

## Golden set (any file under `golden/<skill>/`)

1. `validate_golden.py <set>` — confirm the printed hash actually changed.
2. Bump `manifest.json.set_version`.
3. Old trends stop being comparable after a set change — by design (the hash
   in `results.json` ties a run to an exact data version).

## Canary item

1. **Never** set `reviewed: true` without actually reading `input` yourself
   and deciding the verdict against the judge's rubric — `check_canary.py`
   enforces the flag, but it can't enforce that you actually read anything.
2. New `borderline: true` items: verify against both possible verdicts using
   the rubric in `agents/judge-supported-output-facts.md` / `judge-expected-output-facts.md` — a
   "borderline" item that's actually obvious under the rubric just adds
   noise, not calibration signal.

## Before merge — what CI actually gates

Only `pytest tests/test_plugin_schema.py -q` and `pytest tests/ -q`, per PR.
**Canary eval and baseline runs are never run per-PR** (real API cost,
`workflow_dispatch` + weekly only). If your change needed canary
verification above, you had to do it yourself — CI will not save you here.
