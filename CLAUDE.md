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
- Run artifacts: `eval-runs/` — gitignored, never commit
- CI: `.github/workflows/ci.yml` (schema lint + pytest per PR; canary eval is
  manual/scheduled only — it costs money)

## Local dev loop

Add this repo directory as a local plugin marketplace, install `aissert` from it,
re-install after changes. Test the slash command end-to-end against golden/example
before touching real datasets.
