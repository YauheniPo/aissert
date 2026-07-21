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
last_validated_commit: 2ea2ad69e142faeae395e4f9105cfed1c2d84969
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
├── scripts/wiki/                  # wiki tooling (git diff, lint, significant-change, read-plan)
├── tests/                          # pytest: aggregate.py units + schema lint + wiki lint
├── .github/workflows/ci.yml
├── DESIGN.md                       # source of truth: why, architecture, milestones
├── CLAUDE.md                       # hard rules for agents working in this repo
└── README.md                       # quickstart
```

`eval-runs/` — run artifacts, gitignored, appears locally after
`/aissert:eval`. Never committed.

## Reading order for a first pass

1. `DESIGN.md` §1-2 — the core idea and invocation contract.
2. `skills/aissert/SKILL.md` — the actual orchestration runbook.
3. `agents/*.md` — what each subagent does and doesn't see.
4. `skills/aissert/references/*.md` — the JSON contracts everything obeys.

Deeper dives: [eval-pipeline.md](../domains/eval-pipeline.md) (data flow),
[golden-and-canary.md](../domains/golden-and-canary.md) (test data layers),
[aggregate-py.md](../hotspots/aggregate-py.md) (the math).
