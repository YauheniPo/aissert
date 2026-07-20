---
description: Evaluate a Claude Code skill against a golden set (LLM-as-judge, deterministic gates)
argument-hint: golden_set=<dir> target_skill=<name> [iterations=N] [k1=0.80] [k2=0.70] [--smoke]
---

Use the `aissert` skill to run an evaluation with these arguments: $ARGUMENTS

Follow the skill's orchestration flow exactly. Do not evaluate or score anything
yourself — all metrics and the verdict come from scripts/aggregate.py.
