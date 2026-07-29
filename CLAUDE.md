# aissert — project instructions

LLM-as-judge eval harness for Claude Code skills, packaged as a Claude Code plugin.
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
- Plugin name `aissert` in .claude-plugin/*.json is immutable — never rename.
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
- Claude dev automation: `.claude/settings.json`, `.claude/skills/`,
  `.claude/agents/`, and `scripts/claude/`
- Run artifacts: `eval-runs/` — gitignored, never commit
- CI: `.github/workflows/ci.yml` (schema lint + pytest + wiki lint per PR — wiki
  lint is `continue-on-error`, informational only, never blocks; canary eval is
  manual/scheduled only — it costs money)

## Claude automation

- Use the `verify` skill before finishing repository edits. It checks the diff,
  runs the relevant deterministic commands, and rejects weakened tests.
- Use the `wiki-maintenance` skill only when wiki work is relevant or requested.
  Stale-only wiki output is informational unless the current task touches that
  area.
- Dev-only helper agents live in `.claude/agents/`; runtime eval agents live in
  `agents/` and remain part of the packaged plugin surface.
- PreToolUse hooks block direct pushes to `main` and attempts to place real
  golden data under the repo tree.
- PostToolUse hooks enforce immutable plugin identity and runtime agent
  invariants (`tools: []`, pinned judge model).
- Stop hooks run proportional verification before ending a turn. Set
  `AISSERT_SKIP_STOP_VERIFY=1` only for emergency local debugging, never for CI.
- GitHub PR/issue comments can trigger `.github/workflows/claude.yml` with
  `@claude`; it uses `.claude/settings.json`, scoped Bash allowlists, and the
  `ANTHROPIC_API_KEY` secret.
- `.worktreeinclude` is intentionally empty. Do not copy `.env`, `golden-local/`,
  `eval-runs/`, or real datasets into Claude worktrees.

## Local dev loop

Add this repo directory as a local plugin marketplace, install `aissert` from it,
re-install after changes. `scripts/claude/reinstall_plugin.sh` does the whole
refresh in one command (schema check → forced uninstall+install → new session);
run it from a plain terminal — the in-session sandbox blocks `~/.claude/plugins`
writes, and `/plugin update` alone never re-copies an unchanged-version tree.
Test the slash command end-to-end against golden/example
before touching real datasets.

**Real datasets never go inside this repo's directory, gitignored or not** — a
directory-source marketplace install copies the whole working tree, `.gitignore`
included, into `~/.claude/plugins/cache/...`. Keep real golden sets fully outside
the repo tree (see README.md's Install section).

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

**Maintenance workflow** — run it when `python3 scripts/wiki/changed.py`
reports `significant_change: true`, or when asked for wiki lint/maintenance:

1. `python3 scripts/wiki/lint.py` and `python3 scripts/wiki/changed.py`.
2. Read only the pages flagged stale, broken, orphaned, or uncovered.
3. Re-check the raw files referenced by those pages' `source_paths`.
4. Update only the impacted pages; leave unaffected pages untouched.
5. Refresh `knowledge/index.md`; append a dated entry to `knowledge/log.md`.
6. Re-anchor `last_validated_commit` to a **fresh** `git rev-parse HEAD` in
   every page you touch — never retype a SHA from memory or earlier context.
7. Confirm `python3 scripts/wiki/lint.py` exits 0.

**Session-start, not commit-time.** The `SessionStart` hook
(`scripts/wiki/hook_session_start.py`, wired in `.claude/settings.json`)
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
