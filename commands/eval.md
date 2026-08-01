---
description: Evaluate a Claude Code skill against a golden set (LLM-as-judge, deterministic gates)
argument-hint: golden_set=<dir> [target_skill=<name>] [iterations=N] [min_supported_to_total_output_facts_ratio=0.80] [min_covered_to_total_reference_facts_ratio=0.70]
---

Use the `aissert` skill to run an evaluation with these arguments: $ARGUMENTS

Follow the skill's orchestration flow exactly. Do not evaluate or score anything
yourself — all metrics and the verdict come from scripts/aggregate.py.
Invoke `fact-extractor`, `judge-supported-output-facts`, and
`judge-expected-output-facts` as their named Claude Code agents.
