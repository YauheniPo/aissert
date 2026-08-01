---
name: wiki-maintenance
description: Maintain the repo-local knowledge wiki when architecture, project instructions, host integrations, workflows, prompts, contracts, evaluation behavior, knowledge files, or wiki tooling changes, or when wiki checks report an issue.
---

# Wiki Maintenance

1. Run `python3 scripts/wiki/changed.py` and `python3 scripts/wiki/lint.py`.
2. Read only pages reported stale/broken/orphaned/uncovered and pages covering
   files changed by the task. Re-check every page against `source_paths` before
   editing it.
3. For project instruction, package, hook, or integration changes, also check
   `knowledge/repo/structure.md`, `knowledge/repo/build-test-and-ci.md`,
   `knowledge/meta/source-inventory.md`, and `knowledge/meta/lint-rules.md`.
4. Update concise summaries, invariants, source mappings, and links. Keep
   wiring host-specific and shared behavior in one source; do not paste code.
5. Update `knowledge/index.md` only when navigation changes. Append a dated
   short entry to `knowledge/log.md` whenever wiki content changes.
6. Set `last_validated_commit` from a fresh `git rev-parse HEAD` only on pages
   actually revalidated. Stale-only output is informational outside the touched
   area; never churn SHAs just to silence it.
7. Re-run `python3 scripts/wiki/lint.py` and report any remaining issue.
