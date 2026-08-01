---
name: aissert-codex
description: Codex execution adapter for aissert evaluations. Use whenever Codex runs a full or smoke aissert evaluation; it invokes the isolated-worker runner and persists the required artifacts.
---

# aissert Codex adapter

Use the packaged runner; do not manually orchestrate target, extractor, or
judge calls. It owns isolated `codex exec` workers, required JSON validation,
canary execution, artifact persistence, and deterministic aggregation.

From the plugin root, create a timestamped run directory and run:

```bash
python3 skills/aissert/scripts/run_codex_eval.py \
  --golden-set <golden_set> \
  --run-dir eval-runs/<timestamp>-<target_skill> \
  --iterations <N>
```

Pass `--target-skill <skill>` only when the user supplied it. For a smoke run,
pass `--smoke` instead of choosing an iteration count; it fixes the run to
three items and two iterations. The runner's exit codes are authoritative:
`0` passed, `1` quality gate failed, `2` pipeline or runtime failure. Report
the resulting `results.json` and `report.md` paths without replacing its
deterministic verdict.
