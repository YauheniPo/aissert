# Changelog

This project uses conventional commits and automated GitHub Releases.

## Unreleased

### Added

- One-command local plugin refresh: `scripts/claude/reinstall_plugin.sh` runs
  the plugin schema check, force-reinstalls the directory-source plugin
  (`/plugin update` is version-gated and never re-copies an unchanged-version
  working tree), and launches a fresh Claude Code session.
- Open-source project docs: contributing guide, security policy, roadmap, issue
  templates, and PR checklist.
- Golden-set preflight validation that checks the command target skill against
  `manifest.json`.
- Compact `report.md` output from `aggregate.py`.

### Changed

- Eval result metrics now use `supported_to_total_output_facts_ratio` and
  `covered_to_total_reference_facts_ratio` instead of the opaque `m1` and
  `m2`; verdict artifacts use the matching judge names. The shared schema is
  now version 6.
- Release automation now creates stable GitHub Releases in the same workflow
  that performs the version bump.
- Snapshot releases are PR-specific and update their release asset on each PR
  synchronization.
- Golden and canary manifest validation is stricter.

### Fixed

- Recall judge (`judge-expected-output-facts`) refused to credit a reference
  fact whose definition was fully expressed across several extracted facts
  (e.g. "a 4.0 regression" stated as bug-present-in-4.0 plus
  correct-in-3.x) unless the literal label appeared — caught live by canary
  item `cn-012`. The rubric now has a "definitional label composition" rule
  with a covered/missing anchored example pair.

### Removed

- Bootstrap-only release tag helper script.
- Temporary snapshot trigger files.

## Release Notes

Published releases are available at:

https://github.com/YauheniPo/aissert/releases
