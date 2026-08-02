# Copilot Code Review Instructions for aissert
#
# This project is an LLM-as-judge eval harness for Claude Code skills.
# Focus code review on:

## General Rules

1. **Type Safety & Correctness**: Python 3.12, stdlib only. No external deps except pytest (dev).
2. **Determinism**: All logic must be deterministic. No randomness, no API calls in scripts (only in orchestrator).
3. **Testing**: All `aggregate.py` behavior gets unit tests. Schema validation required.
4. **Docs**: Changes to core logic need corresponding wiki updates (knowledge/). Keep DESIGN.md §1-10 in sync.

## Domain-Specific Rules

### aggregate.py (the math engine)
- Verdict logic (fact-level binary gates) must be mathematically sound.
- min_supported_to_total_output_facts_ratio/min_covered_to_total_reference_facts_ratio thresholds: check DESIGN.md §10 for calibration status.
- Exit codes: 0 = gate passed, 1 = gate failed, 2 = pipeline error.
- Changes require unit tests in `tests/test_aggregate.py`.

### Scripts (bump_version.py, build_claude_plugin_zip.py, etc.)
- **No external dependencies**. Use stdlib only.
- Deterministic: same input → same output always.
- Exit codes matter: 0 = success, 2 = pipeline error, 3 = no-op (not an error).
- Fully document exit codes in docstrings.

### Workflows (.github/workflows/*.yml)
- `auto-release.yml`: Merge to main → version bump + release tag.
- `release.yml`: Release tag → build zip + publish GitHub Release.
- `snapshot-release.yml`: Push to branch → snapshot tag + pre-release.
- `ci.yml`: Schema lint + tests + wiki lint (on every PR/push to main).

### Golden sets & canary
- Golden sets: Never commit corporate data. Use `golden/example/` (synthetic) for CI.
- Canary: Hand-reviewed judge verdicts. Changes require `reviewed: true` flip.
- `golden-local/` is gitignored for a reason — real datasets stay outside the repo tree.

### Plugin packaging
- Allowlist only: `.claude-plugin/`, `agents/`, `skills/`, `commands/`, `golden/example/`, `canary/`, `README.md`, `LICENSE`.
- `plugin.json` version must match `marketplace.json` entry version.
- Fails (exit 2) if versions disagree or allowlisted paths are missing.

## Code Review Checklist for Reviewers

- [ ] No external dependencies added (stdlib + pytest only)
- [ ] Exit codes documented and correct
- [ ] Changes to `aggregate.py` have unit tests
- [ ] Wiki/DESIGN.md updates match code changes
- [ ] No corporate data in golden sets (use synthetic example sets only)
- [ ] Conventional commit format: `type(scope): message` (for auto-release)
- [ ] Schema changes validated with `scripts/validate_golden.py` or schema tests
- [ ] Plugin manifest versions (plugin.json + marketplace.json) are in sync

## Key Files to Watch

- `skills/aissert/scripts/aggregate.py` — the judge verdict math
- `scripts/bump_version.py` — version bumping logic
- `scripts/build_claude_plugin_zip.py` — Claude packaging/allowlist
- `.claude-plugin/plugin.json` & `.claude-plugin/marketplace.json` — versions must match
- `DESIGN.md` — source of truth for architecture
- `PROJECT_RULES.md` — shared hard rules for agents working in this repo

## Contact & Questions

For deep dives:
- `DESIGN.md` §1-2: core idea and contract
- `knowledge/domains/eval-pipeline.md`: data flow
- `knowledge/hotspots/aggregate-py.md`: the math details
