# aissert

[![CI](https://github.com/YauheniPo/aissert/actions/workflows/ci.yml/badge.svg)](https://github.com/YauheniPo/aissert/actions/workflows/ci.yml)
[![Auto Release](https://github.com/YauheniPo/aissert/actions/workflows/auto-release.yml/badge.svg)](https://github.com/YauheniPo/aissert/actions/workflows/auto-release.yml)
[![Snapshot](https://github.com/YauheniPo/aissert/actions/workflows/snapshot.yml/badge.svg)](https://github.com/YauheniPo/aissert/actions/workflows/snapshot.yml)
[![GitHub Release](https://img.shields.io/github/v/release/YauheniPo/aissert?sort=semver&display_name=tag)](https://github.com/YauheniPo/aissert/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Claude Code Plugin](https://img.shields.io/badge/Claude_Code-plugin-111111)](.claude-plugin/plugin.json)
[![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg)](#contributing)

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

## Why try it

- Fact-level precision and recall instead of fragile holistic LLM scores.
- Deterministic Python gates, hashes, exit codes, and resumable artifacts.
- Isolated judge agents with no tools, plus canary checks for judge drift.
- Synthetic fixtures in the public repo; real golden sets stay outside the repo.
- Packaged as a Claude Code plugin with local dev, snapshot, and release flows.

## Install (local dev loop)

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
/aissert:eval golden_set=golden/example target_skill=<skill> iterations=3
/aissert:eval golden_set=golden/example target_skill=<skill> --smoke   # 3 items x 2 iterations
```

Thresholds default from the set's `manifest.json` (`k1` = min mean precision,
`k2` = min mean recall); pass `k1=` / `k2=` to override. The golden set's
`manifest.json` must name the same `target_skill` passed to `/aissert:eval`;
the preflight validator fails before any LLM calls if they differ.

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
`commands/`, `golden/example/`, `canary/`, `README.md`, `LICENSE` — every
other repo dir (`tests/`, `knowledge/`, `scripts/`, `.venv/`, `golden-local/`,
...) is excluded by construction, so a new dev file never ships by accident.
Fails (exit 2) if `plugin.json` and `marketplace.json` versions disagree, or
if an allowlisted path is missing.

Releases are fully automatic on every push to `main`:

- `auto-release.yml` reads conventional-commit subjects since the last
  stable `aissert--vX.Y.Z` tag, picks a bump level (`feat!:`/`type!:` → major,
  `feat:` → minor, `fix:` → patch, nothing else → no release), bumps both
  manifest files, commits, pushes a matching tag, builds the zip, and publishes
  the GitHub Release in the same workflow.
- `release.yml` remains for manually pushed stable tags. Snapshot tags are
  excluded from stable releases.

Requires `main` to accept direct pushes from the default `GITHUB_TOKEN`
(no branch protection blocking the Actions bot) — the bump commit is pushed
straight to `main`, not through a PR.

## Status

Milestones 1–4 done (contracts, deterministic aggregation, plugin scaffold,
agent prompts, example set, canary set built and hand-reviewed). Milestone 5:
baseline-derived thresholds — until that calibration is done for a given
golden set, its K1/K2 defaults are uncalibrated placeholders (DESIGN.md §10).

## Development

```
pytest tests/ -q
```

Python 3.12, stdlib only. CI runs schema lint + tests per PR; canary eval is
manual/scheduled only (costs API money).

## Contributing

Contributions are welcome. The highest-value areas right now are:

- better report rendering and failure clustering from `results.json`;
- more deterministic linters for golden-set quality and duplicate facts;
- CI workflows for scheduled canary/baseline runs;
- docs and examples for creating a new golden set from scratch;
- small fixes that keep the plugin zip lean and safe to publish.

Before opening a PR:

```
pytest tests/ -q
python3 scripts/build_plugin_zip.py
```

Use conventional commit subjects (`fix:`, `feat:`, `docs:`, `test:`, `ci:`).
Release automation uses them to decide whether to publish a patch, minor, or
major release.
