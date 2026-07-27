# Claude Code Review

This repository is prepared for Anthropic managed Claude Code Review, but the
actual enablement lives in Claude Code admin settings and the Claude GitHub app,
not in a workflow file.

Recommended configuration:

- Repositories: `YauheniPo/aissert`
- Trigger: PR opened and every push to an open PR
- Optional manual trigger: `@claude review`
- Review scope: diff against full repository context
- Behavior: comment findings only; never auto-approve or block a PR

Review focus:

- deterministic Python scoring and exit-code behavior;
- `agents/*.md` runtime agents keeping `tools: []` and contract isolation;
- canary drift and `reviewed: true` changes;
- plugin zip allowlist and real-data boundary;
- workflow changes, release automation, and snapshot publishing;
- tests weakened to pass.

Use `.claude/agents/repo-reviewer.md` or local `/code-review` for a second
manual pass. Use `.github/workflows/claude.yml` only when Claude should make
or investigate changes from an `@claude` comment.
