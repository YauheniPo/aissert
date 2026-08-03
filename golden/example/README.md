# Local example evaluation

This directory is a project-local synthetic dataset for exercising aissert
without private data. It is kept with its target skill for repository checks
and is deliberately excluded from release plugin packages:

- `manifest.json` selects the project-only `example-bug-summarizer` target skill.
- `items/*.json` contain fictional bug reports and their reference facts.
- `skill/SKILL.md` defines the project-only skill under test.
- the matching runtime-agent canary is in `../../canary/`.

From the repository root, validate the dataset without making model calls:

```sh
python3 skills/aissert/scripts/validate_golden.py golden/example
```

For an end-to-end local Codex smoke run, provide the project-only target file
explicitly:

```sh
python3 skills/aissert/scripts/run_codex_eval.py \
  --golden-set golden/example \
  --target-skill-file golden/example/skill/SKILL.md \
  --run-dir eval-runs/local-example \
  --smoke
```

The manifest still supplies the target skill name. Run artifacts are written
below `eval-runs/`, which is gitignored.
