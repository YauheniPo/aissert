# aissert

[![CI](https://github.com/YauheniPo/aissert/actions/workflows/ci.yml/badge.svg)](https://github.com/YauheniPo/aissert/actions/workflows/ci.yml)
[![Auto Release](https://github.com/YauheniPo/aissert/actions/workflows/auto-release.yml/badge.svg)](https://github.com/YauheniPo/aissert/actions/workflows/auto-release.yml)
[![Snapshot](https://github.com/YauheniPo/aissert/actions/workflows/snapshot.yml/badge.svg)](https://github.com/YauheniPo/aissert/actions/workflows/snapshot.yml)
[![GitHub Release](https://img.shields.io/github/v/release/YauheniPo/aissert?sort=semver&display_name=tag)](https://github.com/YauheniPo/aissert/releases)
[![Downloads](https://img.shields.io/github/downloads/YauheniPo/aissert/total.svg)](https://github.com/YauheniPo/aissert/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Claude Code Plugin](https://img.shields.io/badge/Claude_Code-plugin-111111)](.claude-plugin/plugin.json)
[![Codex Plugin](https://img.shields.io/badge/Codex-plugin-10a37f)](.codex-plugin/plugin.json)
[![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg)](CONTRIBUTING.md)

![LLM as Judge](https://img.shields.io/badge/LLM--as--judge-fact--level-7c3aed)
![Deterministic Gates](https://img.shields.io/badge/gates-deterministic%20Python-2563eb)
![Golden Sets](https://img.shields.io/badge/eval-golden%20sets-f59e0b)
![Canary Checked](https://img.shields.io/badge/judges-canary%20checked-16a34a)
![Stdlib Only](https://img.shields.io/badge/runtime-stdlib%20only-374151)

Eval harness for agent skills: golden sets, fact-level LLM judges,
precision/recall gates. Packaged as both a Claude Code and Codex plugin.

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
- Packaged as Claude Code and Codex plugins with local dev, snapshot, and release flows.

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

Install the plugin in Codex:

```
codex plugin marketplace add YauheniPo/aissert --ref main
codex plugin add aissert@aissert
```

Run a smoke evaluation of the bundled skill against the synthetic example set:

```
/aissert:smoke golden_set=golden/example
```

The example manifest selects the included `example-bug-summarizer` skill, so
this command works without a separate target skill installation.

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

### Codex

This repository also contains a Codex marketplace
(`.agents/plugins/marketplace.json`). Install directly from GitHub:

```
codex plugin marketplace add YauheniPo/aissert --ref main
codex plugin add aissert@aissert
```

To update the marketplace snapshot later, run:

```
codex plugin marketplace upgrade aissert
codex plugin add aissert@aissert
```

### Models

The runtime-agent definitions are shared by both platforms. Claude Code uses
`model: inherit`, so the judges and extractor follow the active parent-session
model instead of a stale pinned ID. Codex has no plugin-level model override:
it uses the model selected for the Codex session. For comparable eval history,
pass the exact active model only when it is visible as `model_id=…`; otherwise
leave it unset and `results.json` records `null`.

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

One-command refresh from a plain terminal — schema check, forced reinstall,
then a fresh Claude Code session:

```
scripts/claude/reinstall_plugin.sh
```

`/plugin update` alone is not enough here: it is version-gated, so with an
unchanged `plugin.json` version it never re-copies the working tree — hence
the forced uninstall+install. Run the script outside a Claude Code session:
the in-session command sandbox blocks writes to `~/.claude/plugins`.

Alternative for a single session, no persistent install (CLI only):

```
claude --plugin-dir /path/to/aissert
```

Loads the plugin fresh every session start — picks up any edit automatically,
nothing to reinstall. Doesn't work for Claude Desktop, which has no
`--plugin-dir` flag; Desktop needs the packaged zip (see Packaging below) or
the marketplace install above.

For an installed local Codex plugin, use the one-command refresh from a plain
terminal after changing a skill, agent, or hook:

```
scripts/codex/reinstall_plugin.sh
```

It validates the Codex package, ensures the local marketplace is registered,
updates the temporary `+codex.<timestamp>` cachebuster, reinstalls the plugin,
and opens a fresh Codex session. Run it outside an existing sandboxed Codex
turn because that turn cannot update the Codex plugin cache. It uses
`.venv/bin/python` when present (otherwise `python3`); override it with
`AISSERT_PYTHON=/path/to/python` if necessary. Release automation rewrites the
local suffix to the same plain version as the Claude plugin before publishing.

Codex runs use the Codex-only `aissert-codex` adapter, which invokes
`skills/aissert/scripts/run_codex_eval.py`. It starts isolated headless
`codex exec` workers, writes their artifacts itself, and then runs the same
canary and aggregation scripts as Claude Code. This avoids relying on a
named-agent feature that Codex CLI does not provide. Run it with Python 3.12
(for example `.venv/bin/python`), not macOS's legacy system `python3`.
For an external target skill, pass its source explicitly as
`--target-skill-file /path/to/SKILL.md`; the runner embeds the source in each
isolated worker. It also accepts both gate overrides and `--model-id`, which
is recorded in `results.json`.

The Codex plugin also registers `SessionStart`, `PreToolUse`, `PostToolUse`,
and `Stop` hooks. They use the same host-neutral enforcement scripts as the
Claude integration: wiki context, direct-`main` push/data guards, invariant
checks plus golden-set versioning, and proportional verification. The host
configuration files are deliberately separate; the rule implementation is not.

## Usage

```
/aissert:eval golden_set=golden/example iterations=3
/aissert:smoke golden_set=golden/example          # 3 items x 2 iterations
```

`target_skill` is optional: if omitted, the skill to evaluate comes from the
golden set's own `manifest.json`. Pass `target_skill=<skill>` explicitly only
when you want the preflight validator to double-check you're pointing at the
right dataset — it then fails before any LLM calls if the two disagree.

For the complete local example setup and commands, see
[`golden/example/README.md`](golden/example/README.md).

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
fixture. Its target, `skills/example-bug-summarizer/`, is bundled solely as a
stable local test subject. **No corporate data in this repo, ever** — real sets
live in internal storage and are passed by path.

## Canary (runtime-agent regression set)

`canary/` freezes judge inputs with hand-labeled expected verdicts and includes
small synthetic raw-output cases for `fact-extractor`
(contract: [skills/aissert/references/canary-schema.md](skills/aissert/references/canary-schema.md)).
The orchestrator re-runs judges on them before every eval;
`skills/aissert/scripts/check_canary.py` compares. Divergence = invalid run.

Judge items are drafted from pilot judge output with `reviewed: false` and are
**refused by the checker until a human verifies each `expected` verdict and
flips `reviewed: true`**. Borderline items are marked. Precision, recall,
non-borderline, and extractor agreement have separate gates so stability in
one group cannot hide drift in another.

## Packaging & releases

Build distributable plugin zips:

```
python3 scripts/build_plugin_zip.py            # -> dist/aissert-<version>.zip
python3 scripts/build_plugin_zip.py --output /custom/path.zip
python3 scripts/build_codex_plugin_zip.py      # -> dist/aissert-codex-<version>.zip
```

The Claude archive is for Claude Desktop's “Upload local plugin” and contains
only its runtime allowlist. The Codex archive has
`.codex-plugin/plugin.json` at its root and contains the same shared runtime
files. Both builders fail with exit 2 for missing or version-inconsistent
runtime content.

Releases are fully automatic on every push to `main`:

- `auto-release.yml` reads commit subjects since the last stable
  `aissert--vX.Y.Z` tag, picks a bump level (`feat!:`/`type!:` → major,
  `feat:` → minor, everything else → patch), bumps the Claude manifest,
  Claude marketplace, and Codex manifest,
  commits, pushes a matching tag, builds the zip, and publishes the GitHub
  Release in the same workflow. Every merged PR to `main` produces a new
  version and publishes both plugin ZIPs.
- `release.yml` remains for manually pushed stable tags. Snapshot tags are
  excluded from stable releases. `snapshot.yml` separately builds the Claude
  and Codex ZIPs for each PR, then publishes those exact artifacts in the
  snapshot release.

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

Python 3.12, stdlib only. CI runs schema lint + tests per PR; live canary is
mandatory inside `/aissert:eval` but has no standalone scheduled workflow yet
(model calls cost API money).

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

### Codex runtime

The Codex plugin manifest contains only supported plugin fields and runtime
skills. Codex does not accept plugin-level lifecycle hook registration, so the
ZIP deliberately excludes development `hooks/`, `scripts/hooks/`, wiki, and
project instructions. Codex-specific execution lives in the
`aissert-codex` skill; Claude-only development enforcement remains under
`.claude/` and delegates to `scripts/hooks/`.

### Project instructions

`PROJECT_RULES.md` is the shared source of repository rules. `AGENTS.md`
contains Codex-specific integration guidance and `CLAUDE.md` contains
Claude-specific guidance; neither repeats the shared rules. The `verify` and
`wiki-maintenance` workflows live once under `project-skills/`, with local
discovery adapters under `.codex/skills/` and `.claude/skills/`.

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
