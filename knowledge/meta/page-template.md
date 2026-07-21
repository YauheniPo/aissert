---
title: Page template
kind: meta
summary: Required frontmatter contract for every knowledge/ page except index.md and log.md.
source_paths:
  - scripts/wiki/config.py
related_pages:
  - ../index.md
  - lint-rules.md
last_validated_commit: 2ea2ad69e142faeae395e4f9105cfed1c2d84969
---

Every page under `knowledge/` except `index.md` and `log.md` needs this
frontmatter block (enforced by `scripts/wiki/lint.py`):

```yaml
---
title: <short human title>
kind: repo | domain | hotspot | query | meta
summary: <one sentence — used to decide relevance, be specific>
source_paths:
  - <repo-relative file or dir this page describes>
related_pages:
  - <relative .md link to another knowledge/ page>
last_validated_commit: <full git SHA>
---
```

Optional fields: `stale_when` (a plain-language condition under which this
page should be re-checked even if `source_paths` hasn't technically diffed),
`owner_scope` (who/what team this page's content belongs to), `confidence`
(how sure you are the page reflects reality — useful for pages written from
partial information).

## Field notes

- `source_paths` — every entry MUST exist in the repo (file or directory).
  This is what makes a page "stale": `lint.py`/`changed.py` diff these paths
  against `last_validated_commit`.
- `related_pages` — paths are relative to **this page's own directory**, not
  to `knowledge/` root. A page in `hotspots/` linking to `domains/` writes
  `../domains/eval-pipeline.md`.
- `last_validated_commit` — take it from a fresh `git rev-parse HEAD` in the
  same session you're writing/updating the page. Never retype a SHA from
  memory or from earlier conversation context — a hallucinated SHA is worse
  than no SHA, because `lint.py`'s `invalid_last_validated_commit` check only
  catches SHAs that don't resolve to a real commit at all, not wrong-but-real
  ones.
- `kind` vocabulary:
  - `repo` — structural facts about the repository itself (layout, build/CI).
  - `domain` — a feature area spanning multiple files (the eval pipeline, the
    golden/canary split).
  - `hotspot` — a specific file or small file group that needs extra care
    before touching (aggregate.py, the judge prompts).
  - `query` — a reusable, non-obvious lesson captured via `/wiki-capture`.
  - `meta` — pages about the wiki system itself (this one, lint rules,
    source inventory).

## Anti-bloat

- Don't paste large code excerpts — link the file path and describe the
  invariant instead.
- Don't dump chat history into `query` pages — only the reusable answer.
- Keep `index.md` and `status.md` short enough to be practical startup reads.
