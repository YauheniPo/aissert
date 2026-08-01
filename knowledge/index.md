# aissert — LLM Wiki Index

Repo-local wiki: a compact navigation layer over the raw repository, kept in
sync by `scripts/wiki/*.py` and a SessionStart hook. It exists to help an LLM
(or a middle-level engineer) find the right 1-2 files fast instead of
re-reading the whole tree every session.

**Not a replacement for raw source.** `DESIGN.md`, `PROJECT_RULES.md`,
`AGENTS.md`/`CLAUDE.md`, agent
prompts, scripts, and the JSON contracts in `skills/aissert/references/`
remain authoritative. If a wiki page and the raw files disagree, the raw
files win — fix the page, don't trust it over the source.

Read order for a fresh session: this file → [status.md](status.md) → the
page(s) relevant to your task → the raw files those pages point at
(`source_paths` in each page's frontmatter).

Prefer `python3 scripts/wiki/read_plan.py` to narrow which pages to read
before opening raw code, given your changed files.

## Repo

- [Repo structure](repo/structure.md) — directory layout, file-by-file map.
- [Build, test & CI](repo/build-test-and-ci.md) — local dev loop, pytest, host integrations, and GitHub Actions jobs.

## Domains

- [Eval pipeline](domains/eval-pipeline.md) — core idea, data flow, agents, orchestrator.
- [Golden sets & canary](domains/golden-and-canary.md) — skill evaluation versus regression checks for the three runtime evaluation agents.
- [Change playbooks](domains/change-playbooks.md) — what to re-verify for each type of change, before you update anything.

## Hotspots

- [aggregate.py](hotspots/aggregate-py.md) — the single source of every number in this repo.
- [Judges & canary review](hotspots/judges-and-canary.md) — grouped calibration gates, extractor cases, the `reviewed: false` gate, and model-pin risk.

## Meta

- [Page template](meta/page-template.md) — frontmatter contract for wiki pages.
- [Lint rules](meta/lint-rules.md) — what `scripts/wiki/lint.py` enforces and why.
- [Source inventory](meta/source-inventory.md) — which raw paths are covered by which page.

## Queries

No saved query pages yet. Use `/wiki-capture` to add a reusable, non-obvious
lesson under `knowledge/queries/`.
