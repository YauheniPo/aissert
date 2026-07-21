---
description: Capture a non-obvious session lesson into knowledge/queries/
argument-hint: <short lesson title or description>
---

Capture a reusable, non-obvious lesson learned while working into the
repo-local wiki under `knowledge/queries/`. This is for knowledge that is NOT
derivable from the source (why a canary item's expected verdict was actually
wrong and what the correct rubric reading is, a non-obvious pipeline-error
cause, a subtle aggregate.py/contract interaction). Do not dump chat history —
save only a reusable answer.

Input: $ARGUMENTS

Steps:

1. Read `knowledge/meta/page-template.md` for the required frontmatter and
   body format. Read `knowledge/index.md` to see the existing Queries
   section.

2. Decide the lesson. If `$ARGUMENTS` is empty, infer the single most
   valuable reusable lesson from the current session; otherwise use
   `$ARGUMENTS` as the topic. If nothing reusable was learned, say so and
   stop — do not invent one.

3. Check for an existing `knowledge/queries/*.md` page on the same topic. If
   one exists, update it instead of creating a duplicate.

4. Write `knowledge/queries/<kebab-case-slug>.md` with:
   - `kind: query`
   - `source_paths`: the raw files the lesson is grounded in (every entry
     MUST exist in the repo — `scripts/wiki/lint.py` fails otherwise).
   - `related_pages`: link to relevant domain/hotspot pages and
     `../index.md`.
   - `last_validated_commit`: current `git rev-parse HEAD` — take it fresh in
     this session, never retype one from memory.
   - Body: the question/situation, the answer/fix, and the invariant to
     remember. Reference raw file paths, do not paste large code blocks.

5. Add a bullet for the new page under the `## Queries` section of
   `knowledge/index.md` (replace the "No saved query pages yet" placeholder
   if present).

6. Append a one-line entry to `knowledge/log.md` under a dated heading.

7. Run `python3 scripts/wiki/lint.py` and fix any reported issue for the new
   page (broken source_paths, missing index entry, orphan, frontmatter
   errors).

8. Report the created/updated page path and the lint result.
