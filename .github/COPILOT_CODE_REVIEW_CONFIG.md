# Copilot Code Review Automation

This repository uses GitHub Copilot for automated code review on pull requests.

## Configuration

- **Enabled**: Yes
- **Review trigger**: Every pull request to `main`
- **Instructions file**: `.github/copilot-instructions.md`

## What Copilot Reviews

Copilot will check for:

1. **Code quality**: Type safety, logic correctness, determinism
2. **Testing**: Presence of unit tests for critical logic
3. **Documentation**: Changes to core logic should include wiki updates
4. **Dependencies**: No external packages (stdlib + pytest only)
5. **Exit codes**: Scripts have documented exit codes
6. **Data safety**: No corporate data in golden sets
7. **Schema validation**: Golden set and canary changes are validated
8. **Versioning**: Plugin manifests stay in sync

## How to Use

1. When you open a PR, Copilot will automatically run on the PR.
2. Review Copilot's feedback alongside other reviewers' comments.
3. Use the detailed instructions in `.github/copilot-instructions.md` for context.

## Disabling Copilot Review for a PR

Add the `[skip copilot]` label to skip this check (if needed for documentation-only changes, etc.).

---

For organization-level Copilot configuration, see: https://github.com/settings/copilot/setup
