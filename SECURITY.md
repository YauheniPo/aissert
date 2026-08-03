# Security Policy

aissert is an evaluation harness for Claude Code skills. Its main security
concerns are data leakage, prompt-injection resistance, and safe plugin
packaging.

## Supported Versions

Security fixes target the latest released `0.x` version.

## Reporting a Vulnerability

Please do not open a public issue for a vulnerability or data exposure report.
Use GitHub private vulnerability reporting if it is enabled for the repository,
or contact the maintainer through the GitHub profile linked from the project.

Include:

- affected version or commit SHA;
- a minimal reproduction;
- whether sensitive data may have been exposed;
- logs or artifacts with secrets and proprietary data removed.

## Data Boundary

Do not put real golden sets, Jira snapshots, Confluence exports, customer data,
or proprietary work-system data inside this repository directory.

This includes ignored folders. Directory-source plugin installs copy the whole
working tree into the Claude plugin cache, including ignored files. Keep real
golden sets outside the repo, for example:

```text
~/golden-sets/<skill>/
```

The public repository should contain only synthetic fixtures such as
`golden/example/` and the synthetic canary set.

## Prompt Injection Model

Evaluated skill outputs and golden snapshots are untrusted input.

aissert mitigates this by:

- keeping judge agents on `tools: []`;
- requiring the orchestrator to pass content into prompts instead of allowing
  agents to read files;
- treating malformed agent JSON as a pipeline error;
- computing all metrics in Python, not in an LLM;
- running canary checks to detect judge behavior drift.

## Packaging Model

Claude release zips are built from an allowlist in
`scripts/build_claude_plugin_zip.py`.
Development directories such as `tests/`, `knowledge/`, `.venv/`, `.idea/`,
and local golden-set folders are excluded by construction.

If a new runtime path is needed, add it to the allowlist deliberately and verify
the archive contents before release.
