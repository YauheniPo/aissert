"""Schema lint: plugin manifests, agent/skill/command frontmatter, version sync.

Runs as the fast "schema lint" CI step (DESIGN.md §8.1). stdlib only — the
frontmatter here is deliberately kept to simple `key: value` lines so a naive
parser is sufficient; if an agent file ever needs nested YAML, revisit.
"""
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
AGENT_FILES = ["fact-extractor.md", "judge-precision.md", "judge-recall.md"]


def parse_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, f"{path}: missing YAML frontmatter block"
    fields = {}
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        assert re.match(r"^[a-zA-Z_-]+: ", line), (
            f"{path}: frontmatter line not simple 'key: value': {line!r}"
        )
        key, _, value = line.partition(": ")
        fields[key] = value.strip()
    return fields


def load_json(relpath: str) -> dict:
    path = REPO / relpath
    assert path.is_file(), f"missing {relpath}"
    return json.loads(path.read_text(encoding="utf-8"))


# -------------------------------------------------------------- manifests


def test_plugin_json():
    plugin = load_json(".claude-plugin/plugin.json")
    assert plugin["name"] == "aissert", "plugin name is immutable (CLAUDE.md hard rule)"
    assert re.fullmatch(r"\d+\.\d+\.\d+", plugin["version"])
    assert plugin["description"].strip()


def test_marketplace_json():
    marketplace = load_json(".claude-plugin/marketplace.json")
    assert marketplace["name"]
    assert marketplace["owner"]["name"]
    entries = [p for p in marketplace["plugins"] if p["name"] == "aissert"]
    assert len(entries) == 1, "marketplace must list exactly one 'aissert' plugin"
    assert entries[0]["source"] == "./", "repo is its own single-plugin marketplace"


def test_version_sync_between_manifests():
    plugin = load_json(".claude-plugin/plugin.json")
    marketplace = load_json(".claude-plugin/marketplace.json")
    entry = next(p for p in marketplace["plugins"] if p["name"] == "aissert")
    assert entry["version"] == plugin["version"], (
        "plugin.json and marketplace.json versions must match"
    )


# ----------------------------------------------------------------- agents


@pytest.mark.parametrize("filename", AGENT_FILES)
def test_agent_frontmatter(filename):
    path = REPO / "agents" / filename
    assert path.is_file(), f"missing agents/{filename}"
    fm = parse_frontmatter(path)
    assert fm["name"] == path.stem, "agent name must match filename stem"
    assert fm["description"].strip()
    assert fm["tools"] == "[]", (
        "aissert agents must declare tools: [] — they never read/write files "
        "(CLAUDE.md hard rule; also mitigates prompt injection)"
    )
    assert "model" not in fm, (
        "judge/extractor model is deliberately not pinned (DESIGN.md §3); "
        "pinning requires invalidating the canary baseline"
    )


def test_no_unexpected_agent_files():
    found = sorted(p.name for p in (REPO / "agents").glob("*.md"))
    assert found == sorted(AGENT_FILES)


# ---------------------------------------------------------- skill, command


def test_skill_frontmatter():
    fm = parse_frontmatter(REPO / "skills" / "aissert" / "SKILL.md")
    assert fm["name"] == "aissert"
    assert fm["description"].strip()


def test_command_frontmatter():
    fm = parse_frontmatter(REPO / "commands" / "eval.md")
    assert fm["description"].strip()
    assert fm["argument-hint"].strip()


def test_contracts_exist():
    refs = REPO / "skills" / "aissert" / "references"
    assert (refs / "golden-set-schema.md").is_file()
    assert (refs / "results-schema.md").is_file()
