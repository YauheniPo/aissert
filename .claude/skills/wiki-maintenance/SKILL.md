---
name: wiki-maintenance
description: Maintain the repo-local knowledge wiki when scripts/wiki/changed.py reports significant_change, wiki lint reports structural issues, or a task changes knowledge/, scripts/wiki/, architecture, workflows, agent prompts, contracts, or eval pipeline behavior.
---

# Wiki Maintenance

Use this skill only when wiki work is relevant to the current task or explicitly requested.

## Procedure

1. Run:
   - `python3 scripts/wiki/changed.py`
   - `python3 scripts/wiki/lint.py`
2. Read only the wiki pages reported as stale, structurally broken, orphaned, missing from index, or covering files touched by the current task.
3. Re-check each page against its `source_paths`; do not re-anchor pages you did not validate.
4. Update impacted pages with concise summaries, invariants, file links, and cross-links. Do not paste large code blocks.
5. Refresh `knowledge/index.md` only for navigation changes.
6. Append a dated one-line entry to `knowledge/log.md` when wiki content changes.
7. For every page touched, set `last_validated_commit` from a fresh `git rev-parse HEAD`.
8. Re-run `python3 scripts/wiki/lint.py`.

Stale-only output is informational unless the current task touches that page's area. Avoid churn-only SHA updates.
