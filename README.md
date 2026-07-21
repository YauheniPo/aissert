# aissert

Eval harness for Claude Code skills: golden sets, fact-level LLM judges,
precision/recall gates. Packaged as a Claude Code plugin.

Instead of high-variance holistic 0–100 LLM scores: decompose the skill's output
into atomic facts, get binary per-fact verdicts from two isolated judges
(precision: is each claim grounded? recall: is each golden fact covered?), and
compute all numbers and the pass/fail verdict in deterministic Python.
Full rationale and architecture: [DESIGN.md](DESIGN.md).

## Install (local dev loop)

```
/plugin marketplace add /path/to/aissert
/plugin install aissert@aissert
```

After editing agents or manifests: `/reload-plugins`. Skill edits apply immediately.

## Usage

```
/aissert:eval golden_set=golden/example target_skill=<skill> iterations=3
/aissert:eval golden_set=golden/example target_skill=<skill> --smoke   # 3 items x 2 iterations
```

Thresholds default from the set's `manifest.json` (`k1` = min mean precision,
`k2` = min mean recall); pass `k1=` / `k2=` to override.

Exit codes from `aggregate.py`: `0` gate passed, `1` gate failed, `2` pipeline
error (harness broke — numbers not trustworthy).

## Golden sets

Contract: [skills/aissert/references/golden-set-schema.md](skills/aissert/references/golden-set-schema.md).
Validate with:

```
python3 skills/aissert/scripts/validate_golden.py <set-dir>
```

`golden/example/` is a synthetic demo set (fictional app) that doubles as the CI
fixture. **No corporate data in this repo, ever** — real sets live in internal
storage and are passed by path.

## Status

Milestones 1–3 done (contracts, deterministic aggregation, plugin scaffold,
agent prompts, example set). Pending: canary set + judge calibration, then
baseline-derived thresholds — until then verdicts are uncalibrated
(DESIGN.md §10).

## Development

```
pytest tests/ -q
```

Python 3.12, stdlib only. CI runs schema lint + tests per PR; canary eval is
manual/scheduled only (costs API money).
