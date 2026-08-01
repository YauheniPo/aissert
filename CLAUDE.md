# aissert — Claude Code instructions

Read `PROJECT_RULES.md` and `DESIGN.md` before any non-trivial change. They
are the shared source of project rules and architecture.

## Claude Code integration

- Use `.claude/skills/verify/` and `.claude/skills/wiki-maintenance/` as the
  project-skill entry points; their canonical workflows live in
  `project-skills/`.
- Keep Claude wiring in `.claude/settings.json`; its entry points in
  `scripts/claude/` delegate to the shared rules in `scripts/hooks/`.
- Dev-only helper agents live in `.claude/agents/`; runtime evaluation agents
  stay in `agents/` with `tools: []` and `model: inherit`.
- GitHub PR/issue comments use `.github/workflows/claude.yml` and require the
  `ANTHROPIC_API_KEY` secret.
- `.worktreeinclude` is intentionally empty: never copy `.env`,
  `golden-local/`, `eval-runs/`, or real datasets into a worktree.
- Use `scripts/claude/reinstall_plugin.sh` only from a plain terminal when a
  local Claude plugin refresh is requested.

Do not duplicate project rules or workflow steps here. Update the canonical
files instead.
