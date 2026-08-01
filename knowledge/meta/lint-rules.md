---
title: Lint rules
kind: meta
summary: What scripts/wiki/lint.py checks and why each check exists — read before adding or restructuring wiki pages.
source_paths:
  - scripts/wiki/lib.py
  - scripts/wiki/config.py
  - scripts/wiki/lint.py
related_pages:
  - ../index.md
  - page-template.md
  - source-inventory.md
last_validated_commit: 3d3e86042a857f6b8f7023c559cca5eb4421bcb3
---

`python3 scripts/wiki/lint.py` exits 0 only if all of these are empty. Every
check maps to one `lib.py` function; fix the page, not the checker, unless
the checker itself has a bug.

| Check | Function | Fails when |
|---|---|---|
| `frontmatter_errors` | `validate_frontmatter` | Missing frontmatter block, missing required field, unknown field, invalid `kind`, or `source_paths`/`related_pages` not a list. |
| `invalid_validated_commits` | `find_invalid_validated_commits` | `last_validated_commit` doesn't resolve to a real commit via `git rev-parse --verify <sha>^{commit}`. |
| `broken_source_paths` | `find_broken_source_paths` | A `source_paths` entry doesn't exist in the repo. |
| `broken_links` | `find_broken_links` | A markdown link in the page body, or a `related_pages` entry, resolves to a `.md` file that isn't a real wiki page. |
| `missing_index_entries` | `find_missing_index_entries` | A page (other than `index.md`/`log.md`) has no link pointing to it from `index.md`. |
| `orphan_pages` | `find_orphans` | A page has zero inbound links — not from `index.md`, not from another page's body, not from another page's `related_pages`. |
| `stale_pages` | `find_stale_pages` | Any of a page's `source_paths` changed (per `git diff <last_validated_commit> -- <paths>`) since it was last validated. Informational at session start, not a hard lint failure gate — see below. |

## Why `stale_pages` doesn't block `lint.py`'s ok/not-ok verdict path the same way

It does count toward `summary.stale_pages` and the hook's "informational"
note, but a stale page is not automatically wrong — the change to its
`source_paths` might be unrelated to the claim the page makes. Re-check a
stale page's actual content only when your current task touches that area;
don't blanket re-anchor `last_validated_commit` just to silence the flag —
that's churn, not validation (see [judges-and-canary.md](../hotspots/judges-and-canary.md)
for why "looks fine, bump the SHA" is exactly the failure mode this wiki is
trying to avoid at the *judge* layer too).

## Significant-change detection (`scripts/wiki/changed.py`)

Separate from lint — this decides whether the current diff is big/risky
enough to warrant a maintenance pass at all, before any structural issue
exists. Three triggers (`config.py`):

1. **`changed_file_threshold`** — 8+ tracked, non-`knowledge/` files changed.
   Smaller than the 12 used by the project this was ported from — aissert has
   far fewer tracked files, so 8 is already a broad change here.
2. **`architectural_anchor_changed`** — any of `SIGNIFICANT_ANCHORS` (e.g.
   `DESIGN.md`, `skills/aissert/SKILL.md`, `canary/manifest.json`) or a file
   under `SIGNIFICANT_PREFIXES` (`.claude/`, `.codex/`, `agents/`, `scripts/claude/`, `scripts/codex/`,
   `scripts/hooks/`, `hooks/`, `skills/aissert/scripts/`,
   `skills/aissert/references/`) changed — these
   implement or gate the architecture and automation, so any change is
   significant regardless of size.
3. **`uncovered_high_signal_path`** — a changed file under a high-signal
   prefix (`.claude/`, `.codex/`, `agents/`, `skills/`, `commands/`, `golden/`,
   `canary/`, `scripts/claude/`, `scripts/codex/`, `scripts/hooks/`, `hooks/`, `scripts/wiki/`, or one of
   `README.md`/`DESIGN.md`/`PROJECT_RULES.md`/`AGENTS.md`/`CLAUDE.md`) that no wiki page's `source_paths`
   covers at all — a gap in wiki coverage itself.

No `new_src_top_level_folder` heuristic here (the ported project's fourth
trigger) — aissert has no growing `src/` tree to watch for new top-level
folders in; don't reintroduce that check without a concrete reason.
