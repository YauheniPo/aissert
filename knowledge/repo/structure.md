---
title: Repo structure
kind: repo
summary: Directory layout and file-by-file map of the aissert plugin repo.
source_paths:
  - .claude-plugin/plugin.json
  - .claude-plugin/marketplace.json
  - agents
  - skills
  - commands
  - golden
  - canary
  - tests
  - DESIGN.md
  - README.md
related_pages:
  - ../index.md
  - ../domains/eval-pipeline.md
  - build-test-and-ci.md
last_validated_commit: ca8ccd58befefbf93978a8b8de609aeedf85f1ac
---

```
aissert/
├── .claude-plugin/
│   ├── plugin.json            # name "aissert" — IMMUTABLE, checked by tests/test_plugin_schema.py
│   └── marketplace.json       # repo = its own single-plugin marketplace
├── agents/                    # subagent prompts (Task tool, clean context, tools: [])
│   ├── fact-extractor.md
│   ├── judge-precision.md
│   └── judge-recall.md
├── skills/aissert/
│   ├── SKILL.md                # orchestrator: dispatch only, never evaluates
│   ├── references/             # JSON contracts — single source of truth for formats
│   │   ├── golden-set-schema.md
│   │   ├── results-schema.md
│   │   └── canary-schema.md
│   └── scripts/                 # all deterministic logic
│       ├── validate_golden.py
│       ├── run_target.py        # CI-only headless `claude -p` runner
│       ├── aggregate.py         # math, verdict, results.json — see hotspots/aggregate-py.md
│       └── check_canary.py      # judge regression check
├── commands/eval.md             # thin slash-command wrapper over SKILL.md
├── golden/example/               # synthetic demo set, doubles as CI fixture
├── canary/                       # judge regression set — tests judges, NOT the skill
├── knowledge/                     # this wiki
├── scripts/
│   ├── wiki/                      # wiki tooling (git diff, lint, significant-change, read-plan)
│   ├── build_plugin_zip.py        # packages the plugin into dist/aissert-<version>.zip
│   └── bump_version.py            # conventional-commit version bump, called by auto-release.yml
├── tests/                          # pytest: aggregate.py units + schema lint + wiki lint
├── .github/workflows/
│   ├── ci.yml                      # schema-lint + tests + wiki-lint (non-blocking), every PR/push to main
│   ├── auto-release.yml            # push to main -> bump version -> commit + tag
│   └── release.yml                 # tag push (aissert--v*) -> build zip -> GitHub Release
├── DESIGN.md                       # source of truth: why, architecture, milestones
├── CLAUDE.md                       # hard rules for agents working in this repo
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
2. `skills/aissert/SKILL.md` — the actual orchestration runbook.
3. `agents/*.md` — what each subagent does and doesn't see.
4. `skills/aissert/references/*.md` — the JSON contracts everything obeys.

Deeper dives: [eval-pipeline.md](../domains/eval-pipeline.md) (data flow),
[golden-and-canary.md](../domains/golden-and-canary.md) (test data layers),
[aggregate-py.md](../hotspots/aggregate-py.md) (the math).
