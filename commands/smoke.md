---
description: Run a fast 3-item × 2-iteration aissert evaluation
argument-hint: golden_set=<dir> [target_skill=<name>] [min_supported_to_total_output_facts_ratio=0.80] [min_covered_to_total_reference_facts_ratio=0.70]
---

Use the `aissert` skill to run a smoke evaluation with these arguments:
$ARGUMENTS --smoke

Follow the skill's orchestration flow exactly. Do not evaluate or score anything
yourself — all metrics and the verdict come from scripts/aggregate.py.
