# Roadmap

aissert is usable as an early plugin today. The roadmap focuses on making it
easier to adopt, easier to debug, and harder to misuse.

## Near Term

- Quickstart examples for creating a golden set from scratch.
- Better `report.md` sections for worst unsupported facts and worst missing
  golden facts.
- Deterministic golden-set quality lint:
  - duplicate or near-duplicate golden facts;
  - overly broad facts;
  - missing owner or stale metadata;
  - snapshots that are too short to evaluate.
- Scheduled canary workflow example for repositories with API credentials.
- A baseline workflow that runs report-only and proposes min_supported_to_total_output_facts_ratio/min_covered_to_total_reference_facts_ratio thresholds from
  observed precision/recall distributions.

## Mid Term

- `aissert init-golden` helper for scaffolding `manifest.json` and item files.
- JUnit or Allure export for CI systems.
- Markdown report sections that link every metric row back to raw artifacts.
- Meta-eval helper for hand-labeling random verdict samples.
- Better local developer loop for testing prompt changes against frozen canary
  inputs.

## Not Planned

- Holistic LLM scoring.
- Live fetching from Jira, Confluence, or other external systems during eval.
- Storing real corporate golden sets in the public plugin repository.
- Letting judge agents use filesystem or network tools.
