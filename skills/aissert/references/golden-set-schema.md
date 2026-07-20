# Golden Set Schema

Contract for golden dataset directories consumed by the aissert eval harness.
This file is the single source of truth for the golden set format; agent prompts
and scripts must reference it, never restate a diverging copy.

Schema version: **1**

## Directory layout

```
golden/<target-skill>/
├── manifest.json
└── items/
    ├── gs-001.json
    └── gs-002.json
```

One set per target skill. Every item is a single JSON file under `items/`;
the filename (without `.json`) must equal the item's `id`.

## manifest.json

```json
{
  "schema_version": 1,
  "target_skill": "test-cases-writer",
  "set_version": "1.0.0",
  "owner": "epopovich",
  "defaults": {
    "k1": 0.80,
    "k2": 0.70
  }
}
```

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema_version` | int | yes | Must be `1`. |
| `target_skill` | string | yes | Skill this set evaluates. Recorded in results.json. |
| `set_version` | string | yes | Bump on any content change. Changing the set invalidates old trends. |
| `owner` | string | yes | Person responsible for staleness review (DESIGN.md §7.6). |
| `defaults.k1` | number in [0, 1] | yes | Default min mean precision gate. CLI value overrides. |
| `defaults.k2` | number in [0, 1] | yes | Default min mean recall gate. CLI value overrides. |

## Item file (`items/<id>.json`)

```json
{
  "id": "gs-001",
  "input": {
    "type": "jira",
    "key": "SYN-123",
    "snapshot": "full frozen input text the target skill receives"
  },
  "reference": {
    "golden_facts": [
      {"id": "gf1", "text": "one atomic, verifiable claim"},
      {"id": "gf2", "text": "another atomic claim"}
    ]
  },
  "weights": {}
}
```

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Unique across the set. Must equal the filename stem. |
| `input.type` | string | yes | Input kind, e.g. `jira`, `text`. Open vocabulary. |
| `input.key` | string | no | Source identifier (e.g. issue key), informational only. |
| `input.snapshot` | non-empty string | yes | The complete frozen input. No live fetches at eval time — live inputs make the set nondeterministic. |
| `reference.golden_facts` | non-empty array | yes | Human-reviewed atomic facts. Extracted once at set creation time, never re-extracted at eval time. |
| `golden_facts[].id` | string | yes | Unique within the item. |
| `golden_facts[].text` | non-empty string | yes | One fact = one verifiable claim. |
| `weights` | object | yes | Per-golden-fact recall weights. See below. |

### Weights semantics

`weights` maps golden fact id → weight and affects **recall (m2) only**:

- Empty object `{}` — uniform weighting: `m2 = covered / total_golden`.
- Non-empty — keys must be exactly the set of golden fact ids of this item, values
  must be numbers in (0, 1], and must sum to 1.0 (tolerance 1e-9). Then
  `m2 = sum of weights of covered golden facts`.

Weights never apply to precision (m1): extracted facts vary per run and have no
stable identity to weight.

## Set hash

The set hash links a results.json to the exact data it was computed on.
Algorithm: SHA-256 over the concatenation, for `manifest.json` followed by
`items/*.json` sorted by relative POSIX path, of:

```
<relative path bytes> NUL <file bytes> NUL
```

Rendered as `sha256:<hex>`. Any byte change in any file changes the hash =
new baseline.

## Data boundary (hard rule)

No corporate data (real Jira/Confluence/test-case snapshots) in this repository —
only the synthetic `golden/example/` set. Real sets live in internal GitLab and
are passed by path via the `golden_set` parameter. See DESIGN.md §9.
