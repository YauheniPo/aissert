# aissert — Codex instructions

Read `PROJECT_RULES.md` and `DESIGN.md` before any non-trivial change. They
are the shared source of project rules and architecture.

## Codex integration

- Use `.codex/skills/verify/` and `.codex/skills/wiki-maintenance/` as the
  project-skill entry points; their canonical workflows live in
  `project-skills/`.
- Keep Codex wiring in `.codex-plugin/plugin.json` and
  `hooks/hooks.codex.json`. Keep enforcement only in `scripts/hooks/`.
- Runtime agents keep `model: inherit`; the active Codex session chooses the
  model. Do not add a plugin-level model pin.
- After changing the locally installed plugin, use
  `scripts/codex/reinstall_plugin.sh` only when the user asks to refresh the
  local Codex installation. It updates the cachebuster and starts a fresh
  session.
- Start a fresh Codex session after changing plugin hooks; lifecycle hooks are
  loaded at session start.

Do not duplicate project rules or workflow steps here. Update the canonical
files instead.
