# Local example evaluation

This directory is a self-contained synthetic dataset for exercising aissert
without private data:

- `manifest.json` selects the bundled `example-bug-summarizer` target skill.
- `items/*.json` contain fictional bug reports and their reference facts.
- `../../skills/example-bug-summarizer/SKILL.md` defines the skill under test.
- the matching runtime-agent canary is in `../../canary/`.

From the repository root, validate the dataset without making model calls:

```sh
python3 skills/aissert/scripts/validate_golden.py golden/example
```

For an end-to-end local smoke run, start Claude Code with the working tree
loaded as a plugin:

```sh
claude --plugin-dir .
```

Then run:

```text
/aissert:eval golden_set=golden/example --smoke
```

`target_skill` may be omitted because the manifest already names
`example-bug-summarizer`. Run artifacts are written below `eval-runs/`, which
is gitignored.
