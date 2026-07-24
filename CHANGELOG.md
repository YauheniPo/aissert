# Changelog

This project uses conventional commits and automated GitHub Releases.

## Unreleased

### Added

- Open-source project docs: contributing guide, security policy, roadmap, issue
  templates, and PR checklist.
- Golden-set preflight validation that checks the command target skill against
  `manifest.json`.
- Compact `report.md` output from `aggregate.py`.

### Changed

- Release automation now creates stable GitHub Releases in the same workflow
  that performs the version bump.
- Snapshot releases are PR-specific and update their release asset on each PR
  synchronization.
- Golden and canary manifest validation is stricter.

### Removed

- Bootstrap-only release tag helper script.
- Temporary snapshot trigger files.

## Release Notes

Published releases are available at:

https://github.com/YauheniPo/aissert/releases
