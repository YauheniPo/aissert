# aissert

Eval harness for Claude Code skills: golden sets, fact-level LLM judges,
precision/recall gates. Packaged as a Claude Code plugin.

Instead of high-variance holistic 0–100 LLM scores: decompose the skill's output
into atomic facts, get binary per-fact verdicts from two isolated judges
(precision: is each claim grounded? recall: is each golden fact covered?), and
compute all numbers and the pass/fail verdict in deterministic Python.
Full rationale and architecture: [DESIGN.md](DESIGN.md).

## Install (local dev loop)

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
`k2` = min mean recall); pass `k1=` / `k2=` to override.

Exit codes from `aggregate.py`: `0` gate passed, `1` gate failed, `2` pipeline
error (harness broke — numbers not trustworthy).

## Golden sets

Contract: [skills/aissert/references/golden-set-schema.md](skills/aissert/references/golden-set-schema.md).
Validate with:

```
python3 skills/aissert/scripts/validate_golden.py <set-dir>
```

`golden/example/` is a synthetic demo set (fictional app) that doubles as the CI
fixture. **No corporate data in this repo, ever** — real sets live in internal
storage and are passed by path.

## Canary (judge regression set)

`canary/` freezes judge inputs with hand-labeled expected verdicts
(contract: [skills/aissert/references/canary-schema.md](skills/aissert/references/canary-schema.md)).
The orchestrator re-runs judges on them before every eval;
`scripts/check_canary.py` compares. Divergence = invalid run.

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
  `aissert--v*` tag, picks a bump level (`feat!:`/`type!:` → major, `feat:` →
  minor, `fix:` → patch, nothing else → no release), bumps both manifest
  files, commits, and pushes a matching tag.
- That tag push triggers `release.yml`, which runs `build_plugin_zip.py` and
  publishes the zip as a GitHub Release asset.

Requires `main` to accept direct pushes from the default `GITHUB_TOKEN`
(no branch protection blocking the Actions bot) — the bump commit is pushed
straight to `main`, not through a PR.

## Status

Milestones 1–3 done (contracts, deterministic aggregation, plugin scaffold,
agent prompts, example set). Milestone 4: pilot ran end-to-end; canary draft
awaits hand review. Then: baseline-derived thresholds — until calibration is
done, verdicts are uncalibrated (DESIGN.md §10).

## Development

```
pytest tests/ -q
```

Python 3.12, stdlib only. CI runs schema lint + tests per PR; canary eval is
manual/scheduled only (costs API money).
