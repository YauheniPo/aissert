# aissert — shared project rules

LLM-as-judge eval harness for agent skills, packaged for supported coding hosts.
**Read DESIGN.md before any non-trivial change — it is the source of truth.** If a
change contradicts DESIGN.md, update DESIGN.md in the same commit or stop and ask.

## Hard rules

- All scoring math, aggregation, verdicts, and gates live in Python
  (`skills/aissert/scripts/`). Never delegate math or pass/fail decisions to an LLM.
- Judge agents output binary per-fact verdicts only — never numeric scores.
- Agents never read or write files; the orchestrator passes content in and persists
  JSON out. Judge agents keep `tools: []` in frontmatter.
- fact-extractor never sees reference/golden data.
- Judges never see each other's verdicts, the thresholds, or other iterations.
- No corporate data (Tango Jira/Allure/Confluence snapshots) anywhere in this repo,
  including tests, fixtures, and examples. Only synthetic data in `golden/example/`.
- Plugin name `aissert` in every plugin manifest is immutable — never rename.
- JSON contracts are defined once in `skills/aissert/references/*.md`; agent prompts
  and scripts must reference those, not restate diverging copies.

## Conventions

- Python 3.12, stdlib-first; add a dependency only with a clear reason.
- Tests: pytest in `tests/`. Every aggregate.py behavior (verdict logic, sanity
  checks, resume, edge cases: zero facts, empty golden, division guards) gets a unit
  test with fixtures — this code is fully deterministic, no excuses.
- Strict input validation at boundaries: scripts validate JSON they receive from
  agents (schema + required fields) and fail with actionable messages; a malformed
  judge response is a pipeline error, never a silent skip.
- Fail fast, explicit exit codes: 0 = pass, 1 = gate failed, 2 = pipeline/infra error.
  CI distinguishes "skill got worse" from "harness broke".
- Keep abstractions minimal: no plugin-internal frameworks, no clever indirection.
  Three scripts with clear responsibilities beat one configurable engine.
- Commit style: conventional commits (feat:/fix:/docs:/test:/ci:).

## Layout pointers

- Orchestration logic: `skills/aissert/SKILL.md` (dispatch only, never evaluates)
- Agent prompts: `agents/*.md` (plugin-level subagents)
- Contracts: `skills/aissert/references/`
- Runtime plugin integration: `agents/`, `skills/`, `commands/`, and plugin manifests
- Shared lifecycle enforcement: `scripts/hooks/`
- Run artifacts: `eval-runs/` — gitignored, never commit
- CI: `.github/workflows/ci.yml` (schema lint + pytest + wiki lint per PR — wiki
  lint is `continue-on-error`, informational only, never blocks; canary eval is
  manual/scheduled only — it costs money)

**Real datasets never go inside this repo's directory, gitignored or not** — a
directory-source marketplace install can copy the whole working tree,
`.gitignore` included. Keep real golden sets fully outside the repo tree (see
README.md's Install section).

## Wiki (knowledge/)

This repo has a repo-local wiki under `knowledge/` — a compact navigation
layer over the raw repository, not a replacement for it. `DESIGN.md`, this
file, agent prompts, scripts, and `skills/aissert/references/*.md` remain
authoritative; if a wiki page and the raw files disagree, fix the page.

**Mandatory read order** for a fresh session: `knowledge/index.md` →
`knowledge/status.md` → only the domain/hotspot pages relevant to the current
task → the raw files those pages point at (`source_paths` in frontmatter).
Prefer `python3 scripts/wiki/read_plan.py` to narrow which pages to read
given the current changed files.

For wiki maintenance, use the canonical workflow in
`project-skills/wiki-maintenance/SKILL.md`; do not copy its procedure into
host instruction files.

**Session-start, not commit-time.** The development `SessionStart` hook
(`scripts/hooks/session_start.py`, wired by the Claude Code integration)
injects a maintenance action item into context when it finds structural
breakage or `significant_change: true`. Do that maintenance **before**
starting the user's task. Commits and pushes are never blocked on wiki
state — the hook is fail-open (any error degrades to a minimal reminder).
Stale pages alone (`source_paths` changed since `last_validated_commit`) are
informational, not an action item — re-check one only when your current task
touches its area; don't blanket re-anchor `last_validated_commit` just to
silence the flag, that's churn, not validation.

**Anti-bloat:** no large code excerpts in wiki pages — file paths, summaries,
invariants, and cross-links instead. `knowledge/queries/` is for reusable
lessons captured via `/wiki-capture`, never a chat-history dump.

Map: `knowledge/index.md` · rules `knowledge/meta/lint-rules.md` · frontmatter
contract `knowledge/meta/page-template.md`.
