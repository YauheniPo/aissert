"""Static configuration for the repo-local LLM wiki under knowledge/.

Ported from a sibling project's scripts/wiki/config.js — same design, values
adapted to aissert's actual file layout (agents/, skills/aissert/scripts/,
skills/aissert/references/, golden/, canary/) instead of a src/ tree.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIR = REPO_ROOT / "knowledge"
INDEX_PATH = KNOWLEDGE_DIR / "index.md"
LOG_PATH = KNOWLEDGE_DIR / "log.md"

REQUIRED_FRONTMATTER_FIELDS = [
    "title",
    "kind",
    "summary",
    "source_paths",
    "related_pages",
    "last_validated_commit",
]

OPTIONAL_FRONTMATTER_FIELDS = ["stale_when", "owner_scope", "confidence"]

VALID_KINDS = {"repo", "domain", "hotspot", "query", "meta"}

# Files whose content IS the architecture — any change here is significant
# regardless of line count (DESIGN.md is the source of truth for rationale;
# these are the files that implement or gate it).
SIGNIFICANT_ANCHORS = [
    "DESIGN.md",
    "CLAUDE.md",
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    "skills/aissert/SKILL.md",
    "commands/eval.md",
    "commands/smoke.md",
    "golden/example/manifest.json",
    "canary/manifest.json",
]

# Directories where any change is architecturally significant: judge/extractor
# behavior, deterministic math, and the JSON contracts everything else obeys.
SIGNIFICANT_PREFIXES = [
    ".claude/",
    "agents/",
    "scripts/claude/",
    "skills/aissert/scripts/",
    "skills/aissert/references/",
]

# A run this small (~35 tracked files, no src/ tree) doesn't need the source
# project's threshold of 12 — 8 touched files here is already a broad change.
CHANGED_FILE_THRESHOLD = 8

# changed-file pattern -> wiki pages to read before touching that area.
# Prefix match: a rule matches if the changed path equals or starts with the
# pattern.
READ_PLAN_RULES = [
    {
        "patterns": ["DESIGN.md"],
        "pages": [
            "knowledge/repo/structure.md",
            "knowledge/domains/eval-pipeline.md",
        ],
    },
    {
        "patterns": ["CLAUDE.md"],
        "pages": ["knowledge/meta/lint-rules.md"],
    },
    {
        "patterns": ["agents/"],
        "pages": [
            "knowledge/domains/eval-pipeline.md",
            "knowledge/hotspots/judges-and-canary.md",
        ],
    },
    {
        "patterns": [
            "skills/aissert/scripts/aggregate.py",
            "skills/aissert/scripts/validate_golden.py",
        ],
        "pages": ["knowledge/hotspots/aggregate-py.md"],
    },
    {
        "patterns": ["skills/aissert/scripts/check_canary.py"],
        "pages": [
            "knowledge/hotspots/judges-and-canary.md",
            "knowledge/hotspots/aggregate-py.md",
        ],
    },
    {
        "patterns": ["skills/aissert/scripts/"],
        "pages": [
            "knowledge/hotspots/aggregate-py.md",
            "knowledge/repo/build-test-and-ci.md",
        ],
    },
    {
        "patterns": ["skills/aissert/references/"],
        "pages": [
            "knowledge/hotspots/aggregate-py.md",
            "knowledge/domains/eval-pipeline.md",
        ],
    },
    {
        "patterns": [
            "skills/aissert/SKILL.md",
            "commands/eval.md",
            "commands/smoke.md",
        ],
        "pages": ["knowledge/domains/eval-pipeline.md"],
    },
    {
        "patterns": ["golden/"],
        "pages": ["knowledge/domains/golden-and-canary.md"],
    },
    {
        "patterns": ["canary/"],
        "pages": [
            "knowledge/domains/golden-and-canary.md",
            "knowledge/hotspots/judges-and-canary.md",
        ],
    },
    {
        "patterns": ["tests/", ".github/workflows/", ".claude/", "scripts/claude/"],
        "pages": ["knowledge/repo/build-test-and-ci.md"],
    },
    {
        "patterns": ["scripts/wiki/"],
        "pages": [
            "knowledge/meta/lint-rules.md",
            "knowledge/meta/source-inventory.md",
        ],
    },
    {
        "patterns": ["knowledge/meta/"],
        "pages": [
            "knowledge/meta/lint-rules.md",
            "knowledge/meta/source-inventory.md",
            "knowledge/index.md",
            "knowledge/status.md",
        ],
    },
    {
        "patterns": [
            "knowledge/index.md",
            "knowledge/status.md",
            "knowledge/log.md",
        ],
        "pages": ["knowledge/index.md", "knowledge/status.md"],
    },
]
