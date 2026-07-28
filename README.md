# aissert

[![CI](https://github.com/YauheniPo/aissert/actions/workflows/ci.yml/badge.svg)](https://github.com/YauheniPo/aissert/actions/workflows/ci.yml)
[![Auto Release](https://github.com/YauheniPo/aissert/actions/workflows/auto-release.yml/badge.svg)](https://github.com/YauheniPo/aissert/actions/workflows/auto-release.yml)
[![Snapshot](https://github.com/YauheniPo/aissert/actions/workflows/snapshot.yml/badge.svg)](https://github.com/YauheniPo/aissert/actions/workflows/snapshot.yml)
[![GitHub Release](https://img.shields.io/github/v/release/YauheniPo/aissert?sort=semver&display_name=tag)](https://github.com/YauheniPo/aissert/releases)
[![Downloads](https://img.shields.io/github/downloads/YauheniPo/aissert/total.svg)](https://github.com/YauheniPo/aissert/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Claude Code Plugin](https://img.shields.io/badge/Claude_Code-plugin-111111)](.claude-plugin/plugin.json)
[![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg)](CONTRIBUTING.md)

![LLM as Judge](https://img.shields.io/badge/LLM--as--judge-fact--level-7c3aed)
![Deterministic Gates](https://img.shields.io/badge/gates-deterministic%20Python-2563eb)
![Golden Sets](https://img.shields.io/badge/eval-golden%20sets-f59e0b)
![Canary Checked](https://img.shields.io/badge/judges-canary%20checked-16a34a)
![Stdlib Only](https://img.shields.io/badge/runtime-stdlib%20only-374151)

Eval harness for Claude Code skills: golden sets, fact-level LLM judges,
precision/recall gates. Packaged as a Claude Code plugin.

Instead of high-variance holistic 0–100 LLM scores: decompose the skill's output
into atomic facts, get binary per-fact verdicts from two isolated judges
(precision: is each claim grounded? recall: is each golden fact covered?), and
compute all numbers and the pass/fail verdict in deterministic Python.
Full rationale and architecture: [DESIGN.md](DESIGN.md).

## Project links

- [Latest release](https://github.com/YauheniPo/aissert/releases/latest)
- [Design](DESIGN.md)
- [Roadmap](ROADMAP.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)
- [Changelog](CHANGELOG.md)

## Why try it

- Fact-level precision and recall instead of fragile holistic LLM scores.
- Deterministic Python gates, hashes, exit codes, and resumable artifacts.
- Isolated judge agents with no tools, plus canary checks for judge drift.
- Synthetic fixtures in the public repo; real golden sets stay outside the repo.
- Packaged as a Claude Code plugin with local dev, snapshot, and release flows.

## Quickstart

Clone the repo and run the deterministic checks:

```
git clone https://github.com/YauheniPo/aissert.git
cd aissert
pytest tests/ -q
python3 scripts/build_plugin_zip.py
python3 skills/aissert/scripts/validate_golden.py golden/example --target-skill example-bug-summarizer
```

Install the plugin in Claude Code:

```
/plugin marketplace add /path/to/aissert
/plugin install aissert@aissert
```

Run a smoke eval against a skill:

```
/aissert:eval golden_set=golden/example target_skill=<skill> --smoke
```

## Install (for users)

Simplest path — no clone, no zip download. This repo is itself a marketplace
(`.claude-plugin/marketplace.json`), so any Claude Code user can point at it
directly on GitHub:

```
/plugin marketplace add YauheniPo/aissert
/plugin install aissert@aissert
```

Claude Code resolves `owner/repo` and installs from the current default
branch. To pick up a new release later: reinstall, or
`/plugin marketplace update aissert` if your Claude Code version supports it.

This is the right option for sharing the plugin with other users/teams — they
just need those two commands, nothing to build or host.

## Install (local dev loop)

For normal use, download the plugin zip from the
[latest GitHub Release](https://github.com/YauheniPo/aissert/releases/latest).
Release assets are the distribution channel for this plugin; GitHub Packages is
not required.

**Never run this against a working tree that has a real (corporate) golden set
in it, even gitignored.** A directory-source marketplace add copies the whole
tree — `.gitignore` included — into `~/.claude/plugins/cache/...`. Real golden
sets must live fully outside this repo's directory (e.g. `~/golden-sets/<skill>/`),
never merely gitignored inside it. See `knowledge/domains/golden-and-canary.md`.

```
/plugin marketplace add /path/to/aissert
/plugin install aissert@aissert
```

After editing agents or manifests: `/reload-plugins`. Skill edits apply immediately.

Alternative for a single session, no persistent install (CLI only):

```
claude --plugin-dir /path/to/aissert
```

Loads the plugin fresh every session start — picks up any edit automatically,
nothing to reinstall. Doesn't work for Claude Desktop, which has no
`--plugin-dir` flag; Desktop needs the packaged zip (see Packaging below) or
the marketplace install above.

## Usage

```
/aissert:eval golden_set=golden/example iterations=3
/aissert:eval golden_set=golden/example --smoke   # 3 items x 2 iterations
```

`target_skill` is optional: if omitted, the skill to evaluate comes from the
golden set's own `manifest.json`. Pass `target_skill=<skill>` explicitly only
when you want the preflight validator to double-check you're pointing at the
right dataset — it then fails before any LLM calls if the two disagree.

Thresholds default from the set's `manifest.json` (`min_supported_to_total_output_facts_ratio`
= min mean precision, `min_covered_to_total_reference_facts_ratio` = min mean recall); pass
`min_supported_to_total_output_facts_ratio=` / `min_covered_to_total_reference_facts_ratio=` to override.

Exit codes from `aggregate.py`: `0` gate passed, `1` gate failed, `2` pipeline
error (harness broke — numbers not trustworthy).

## Golden sets

Contract: [skills/aissert/references/golden-set-schema.md](skills/aissert/references/golden-set-schema.md).
Validate with:

```
python3 skills/aissert/scripts/validate_golden.py <set-dir>
python3 skills/aissert/scripts/validate_golden.py <set-dir> --target-skill <skill>
```

`golden/example/` is a synthetic demo set (fictional app) that doubles as the CI
fixture. **No corporate data in this repo, ever** — real sets live in internal
storage and are passed by path.

## Canary (judge regression set)

`canary/` freezes judge inputs with hand-labeled expected verdicts
(contract: [skills/aissert/references/canary-schema.md](skills/aissert/references/canary-schema.md)).
The orchestrator re-runs judges on them before every eval;
`skills/aissert/scripts/check_canary.py` compares. Divergence = invalid run.

Items are drafted from pilot judge output with `reviewed: false` and are
**refused by the checker until a human verifies each `expected` verdict and
flips `reviewed: true`**. Borderline items are marked.

## Packaging & releases

Build a distributable plugin zip (for Claude Desktop's "Upload local plugin",
or any offline install):

```
python3 scripts/build_plugin_zip.py            # -> dist/aissert-<version>.zip
python3 scripts/build_plugin_zip.py --output /custom/path.zip
```

Allowlist, not a denylist: only `.claude-plugin/`, `agents/`, `skills/`,
`commands/`, `golden/example/`, `canary/`, public top-level docs, and `LICENSE`
are included. Every other repo dir (`tests/`, `knowledge/`, `scripts/`,
`.venv/`, `golden-local/`, ...) is excluded by construction, so a new dev file
never ships by accident.
Fails (exit 2) if `plugin.json` and `marketplace.json` versions disagree, or
if an allowlisted path is missing.

Releases are fully automatic on every push to `main`:

- `auto-release.yml` reads commit subjects since the last stable
  `aissert--vX.Y.Z` tag, picks a bump level (`feat!:`/`type!:` → major,
  `feat:` → minor, everything else → patch), bumps both manifest files,
  commits, pushes a matching tag, builds the zip, and publishes the GitHub
  Release in the same workflow. Every merged PR to `main` produces a new
  version.
- `release.yml` remains for manually pushed stable tags. Snapshot tags are
  excluded from stable releases.

Requires `main` to accept direct pushes from the default `GITHUB_TOKEN`
(no branch protection blocking the Actions bot) — the bump commit is pushed
straight to `main`, not through a PR.

## Status

Milestones 1–4 done (contracts, deterministic aggregation, plugin scaffold,
agent prompts, example set, canary set built and hand-reviewed). Milestone 5:
baseline-derived thresholds — until that calibration is done for a given
golden set, its min_supported_to_total_output_facts_ratio/min_covered_to_total_reference_facts_ratio defaults are uncalibrated placeholders (DESIGN.md §10).

## Development

```
pytest tests/ -q
```

Python 3.12, stdlib only. CI runs schema lint + tests per PR; canary eval is
manual/scheduled only (costs API money).

### Claude Code automation

This repo includes development-time Claude Code automation under `.claude/`:

- `verify` skill — run after edits to inspect the diff and execute relevant
  deterministic checks.
- `wiki-maintenance` skill — scoped procedure for `knowledge/` upkeep.
- PreToolUse/PostToolUse/Stop hooks — block direct pushes to `main`, keep real
  golden data out of the repo tree, enforce runtime agent/plugin invariants, and
  run proportional verification before a Claude turn ends.
- Dev-only agents in `.claude/agents/` for repository review, release auditing,
  and wiki maintenance. Runtime plugin agents remain in `agents/`.
- `.worktreeinclude` is intentionally empty; do not copy `.env`, `golden-local/`,
  `eval-runs/`, or real datasets into parallel Claude worktrees.

GitHub comments can trigger Claude with `@claude` via
`.github/workflows/claude.yml`. Configure the repository secret
`ANTHROPIC_API_KEY` before using it. Managed Claude Code Review is configured
outside workflows through the Claude GitHub app; see
`.github/CLAUDE_CODE_REVIEW_CONFIG.md` for the intended repo settings.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and
[ROADMAP.md](ROADMAP.md). The highest-value areas right now are better reports,
golden-set quality linting, scheduled canary/baseline workflows, and examples
for creating a new golden set from scratch.

Before opening a PR:

```
pytest tests/ -q
python3 scripts/build_plugin_zip.py
```

Use conventional commit subjects (`fix:`, `feat:`, `docs:`, `test:`, `ci:`).
Release automation uses breaking/`feat:` subjects for major/minor bumps;
all other merged PRs publish a patch release.
