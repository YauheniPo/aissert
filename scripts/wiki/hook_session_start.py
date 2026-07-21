#!/usr/bin/env python3
"""SessionStart hook: inject the wiki read-plan for the current working tree.

Ported from a sibling project's scripts/wiki/hook-session-start.js. The plan is
emitted via hookSpecificOutput.additionalContext so it reaches the model's
context (a bare "systemMessage" only shows a terminal warning to the user and
never reaches the model). Fail-open: any error degrades to a minimal reminder,
never blocks or fails the session.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> None:
    from lib import (
        analyze_significant_change,
        get_changed_files,
        get_read_plan,
        load_wiki_pages,
        summarize_health,
        collect_wiki_health,
    )

    changed_files = get_changed_files()
    read_plan = get_read_plan(changed_files)
    pages = load_wiki_pages()
    significant = analyze_significant_change(changed_files, pages)
    health = summarize_health(collect_wiki_health())

    lines = [
        "[LLM Wiki] Repo-local wiki active. Read order: "
        "knowledge/index.md -> knowledge/status.md -> the pages below -> raw files."
    ]

    if read_plan:
        lines.append(f"Read-plan for current diff ({len(changed_files)} changed file(s)):")
        for page in read_plan:
            lines.append(f"  - {page}")

    if significant["significant_change"]:
        lines.append(
            "significant_change: true - run wiki maintenance (see CLAUDE.md 'Wiki') "
            "before finishing. Run `python3 scripts/wiki/changed.py` for details."
        )

    # Stale pages are informational only: re-check them when the current task
    # actually touches their area. Forcing a maintenance pass for every stale
    # page produces low-value re-anchor churn (SHA bumps without content).
    if health["stale_pages"]:
        lines.append(
            "Stale wiki pages (re-check only if your task touches their area): "
            + ", ".join(health["stale_pages"])
        )

    structural_issues = (
        health["broken_links"]
        + health["broken_source_paths"]
        + health["frontmatter_errors"]
        + health["invalid_validated_commits"]
        + health["missing_index_entries"]
        + health["orphan_pages"]
    )
    needs_fix = structural_issues > 0 or significant["significant_change"]

    # Session-start is where the agent fixes the wiki — commits/pushes are
    # intentionally NOT blocked. Make this an explicit action item so the
    # agent repairs drift before starting the user's task, not a passive note.
    if needs_fix:
        lines.append("")
        lines.append(
            "WARNING: WIKI MAINTENANCE REQUIRED - do this at the START of the session, "
            "before the user's task:"
        )
        lines.append(
            "  1. `python3 scripts/wiki/changed.py` and `python3 scripts/wiki/lint.py` "
            "to see what drifted."
        )
        lines.append("  2. Re-validate the flagged pages against their `source_paths` raw files; fix drift.")
        lines.append("  3. Re-anchor `last_validated_commit` to HEAD in every page you touch.")
        lines.append(
            "  4. Refresh `knowledge/index.md` and append `knowledge/log.md` "
            "(see CLAUDE.md 'Wiki' -> Maintenance Workflow)."
        )
        lines.append("  5. Confirm `python3 scripts/wiki/lint.py` is ok, then proceed with the requested work.")

    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": "\n".join(lines),
                }
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.stdout.write(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": (
                            "[LLM Wiki] Read knowledge/index.md then knowledge/status.md "
                            "before working. See CLAUDE.md 'Wiki'."
                        ),
                    }
                }
            )
        )
