---
title: Repo structure
kind: repo
summary: Directory layout and file-by-file map of the aissert plugin repo.
source_paths:
  - .claude/settings.json
  - .claude/skills
  - .claude/agents
  - .codex/skills
  - .claude-plugin/plugin.json
  - .claude-plugin/marketplace.json
  - .codex-plugin/plugin.json
  - agents
  - skills
  - commands
  - golden
  - canary
  - tests
  - scripts/claude
  - scripts/codex
  - scripts/hooks
  - project-skills
  - DESIGN.md
  - PROJECT_RULES.md
  - AGENTS.md
  - CLAUDE.md
  - README.md
  - .worktreeinclude
related_pages:
  - ../index.md
  - ../domains/eval-pipeline.md
  - build-test-and-ci.md
last_validated_commit: 966557e7ce41bf0565e705c7a7d365197790b61f
---

```
aissert/
├── .claude/                   # dev-time Claude Code settings, skills, agents, hooks wiring
│   ├── settings.json           # SessionStart/PreToolUse/PostToolUse/Stop hooks
│   ├── skills/                 # reusable dev procedures (verify, wiki-maintenance)
│   └── agents/                 # dev-only review/audit/wiki helper agents
├── .codex/skills/              # Codex entry points for the shared project workflows
├── project-skills/             # neutral verify/wiki-maintenance workflow sources
├── .claude-plugin/
│   ├── plugin.json            # name "aissert" — IMMUTABLE, checked by tests/test_plugin_schema.py
│   └── marketplace.json       # repo = its own single-plugin marketplace
├── .codex-plugin/
│   └── plugin.json            # Codex manifest; points at packaged skills
├── scripts/codex/
│   └── reinstall_plugin.sh    # local cachebuster, reinstall, and fresh Codex session
├── agents/                    # subagent prompts (Task tool, clean context, tools: [])
│   ├── fact-extractor.md
│   ├── judge-supported-output-facts.md
│   └── judge-expected-output-facts.md
├── skills/
│   ├── aissert/
│   │   ├── SKILL.md             # neutral entry skill
│   ├── aissert-codex/
│   │   └── SKILL.md             # Codex-only isolated-worker execution adapter
│   ├── aissert-workflow/
│   │   └── SKILL.md             # neutral orchestration runbook
│   │   ├── references/          # JSON contracts — single source of truth for formats
│   │   │   ├── golden-set-schema.md
│   │   │   ├── results-schema.md
│   │   │   └── canary-schema.md
│   │   └── scripts/             # all deterministic logic
│   │       ├── validate_golden.py
│   │       ├── run_target.py     # CI-only headless `claude -p` runner
│   │       ├── run_codex_eval.py # Codex-only isolated-worker runner
│   │       ├── aggregate.py      # math, verdict, results.json — see hotspots/aggregate-py.md
│   │       └── check_canary.py   # strict grouped runtime-agent regression check
├── commands/
│   ├── eval.md                  # full-eval wrapper over SKILL.md
│   └── smoke.md                 # fixed 3-item × 2-iteration wrapper
├── golden/example/               # synthetic demo set + project-only target + local-run README
├── canary/                       # runtime-agent regression set — never tests the target skill
│   ├── items/                    # frozen precision/recall judge inputs
│   └── extractor-items/          # synthetic raw outputs + tolerant fact anchors
├── knowledge/                     # this wiki
├── scripts/
│   ├── claude/                    # deterministic hook scripts used by .claude/settings.json
│   ├── hooks/                     # shared hook rules used by both host integrations
│   ├── wiki/                      # wiki tooling (git diff, lint, significant-change, read-plan)
│   ├── build_claude_plugin_zip.py # packages the Claude plugin into dist/aissert-<version>.zip
│   └── bump_version.py            # conventional-commit version bump, called by auto-release.yml
├── tests/                          # pytest: aggregate.py units + schema lint + wiki lint
├── .github/workflows/
│   ├── ci.yml                      # schema-lint + tests + wiki-lint (non-blocking), every PR/push to main
│   ├── claude.yml                  # @claude PR/issue helper, scoped tools + repo hooks
│   ├── auto-release.yml            # push to main -> bump version -> commit + tag
│   └── release.yml                 # tag push (aissert--v*) -> build zip -> GitHub Release
├── .worktreeinclude                 # intentionally empty; don't copy secrets or real datasets
├── DESIGN.md                       # source of truth: why, architecture, milestones
├── PROJECT_RULES.md                # one source of shared engineering rules
├── AGENTS.md                       # Codex entry point and Codex-specific integration rules
├── CLAUDE.md                       # Claude Code entry point and Claude-specific integration rules
└── README.md                       # quickstart
```

`eval-runs/` — run artifacts, gitignored, appears locally after
`/aissert:eval`. Never committed.

`golden-local/` — same idea as `eval-runs/`, for real/corporate golden sets a
developer is testing against locally: gitignored, but see
[golden-and-canary.md](../domains/golden-and-canary.md) for why gitignore
alone isn't sufficient and a path fully outside the repo is the safer default.

## Reading order for a first pass

1. `DESIGN.md` §1-2 — the core idea and invocation contract.
2. `skills/aissert-workflow/SKILL.md` — the platform-neutral orchestration runbook.
3. `skills/aissert/SKILL.md` — the neutral entry skill.
4. `agents/*.md` — what each subagent does and doesn't see.
5. `skills/aissert/references/*.md` — the JSON contracts everything obeys.

For a self-contained local run, `golden/example/README.md` ties the example
manifest to its project-only `skill/SKILL.md` target. The fixture directory is
excluded from Claude and Codex release packages.

Deeper dives: [eval-pipeline.md](../domains/eval-pipeline.md) (data flow),
[golden-and-canary.md](../domains/golden-and-canary.md) (test data layers),
[aggregate-py.md](../hotspots/aggregate-py.md) (the math).

`.claude/` is Claude-only development automation and delegates to
`scripts/hooks/`. Codex plugin manifests do not support lifecycle-hook
registration, so the Codex archive contains only evaluation runtime files.
Both packages are allowlist-built by `scripts/build_claude_plugin_zip.py` and
`scripts/build_codex_plugin_zip.py`.

`project-skills/` owns the neutral `verify` and `wiki-maintenance` procedures.
The `.claude/skills/` and `.codex/skills/` files are discovery adapters only;
they point back to those canonical workflows rather than copying them.
