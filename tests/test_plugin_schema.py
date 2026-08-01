"""Schema lint: plugin manifests, agent/skill/command frontmatter, version sync.

Runs as the fast "schema lint" CI step (DESIGN.md §8.1). stdlib only — the
frontmatter here is deliberately kept to simple `key: value` lines so a naive
parser is sufficient; if an agent file ever needs nested YAML, revisit.
"""
import importlib.util
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
AGENT_FILES = [
    "fact-extractor.md",
    "judge-supported-output-facts.md",
    "judge-expected-output-facts.md",
]


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
    codex_plugin = load_json(".codex-plugin/plugin.json")
    entry = next(p for p in marketplace["plugins"] if p["name"] == "aissert")
    assert entry["version"] == plugin["version"], (
        "plugin.json and marketplace.json versions must match"
    )
    assert codex_plugin["version"].split("+", 1)[0] == plugin["version"], (
        "Codex's release version must match Claude's; a local Codex cachebuster "
        "suffix is allowed for development reinstalls"
    )


def test_codex_marketplace_and_manifest():
    marketplace = load_json(".agents/plugins/marketplace.json")
    plugin = load_json(".codex-plugin/plugin.json")
    assert marketplace["name"] == "aissert"
    assert marketplace["interface"]["displayName"] == "aissert"
    assert plugin["name"] == "aissert"
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?", plugin["version"])
    assert plugin["skills"] == "./skills/"
    assert "hooks" not in plugin
    entry = next(p for p in marketplace["plugins"] if p["name"] == "aissert")
    assert entry["source"] == {"source": "local", "path": "./"}
    assert entry["policy"] == {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL",
    }


def test_codex_package_uses_shared_runtime_sources_only():
    script_path = REPO / "scripts" / "build_codex_plugin_zip.py"
    spec = importlib.util.spec_from_file_location("build_codex_plugin_zip", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    include_paths = set(module.INCLUDE_PATHS)
    assert "agents" in include_paths
    assert "skills/aissert/SKILL.md" in include_paths
    assert "skills/aissert-codex/SKILL.md" in include_paths
    assert "skills/aissert-workflow/SKILL.md" in include_paths
    assert "skills/aissert/scripts/run_codex_eval.py" in include_paths
    assert "skills/aissert/scripts/run_target.py" not in include_paths
    assert "commands" not in include_paths
    assert "hooks" not in include_paths
    assert "scripts/hooks" not in include_paths


def test_codex_package_accepts_snapshot_prerelease_versions(tmp_path, monkeypatch):
    script_path = REPO / "scripts" / "build_codex_plugin_zip.py"
    spec = importlib.util.spec_from_file_location("build_codex_plugin_zip", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    for version in ("0.11.1", "0.11.1-SNAPSHOT-pr42", "0.11.1+codex.local", "0.11.1-rc.1+build.7"):
        assert module.SEMVER_RE.fullmatch(version)

    snapshot_manifest = tmp_path / "plugin.json"
    manifest = load_json(".codex-plugin/plugin.json")
    manifest["version"] = "0.11.1-SNAPSHOT-pr42"
    snapshot_manifest.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(module, "MANIFEST_PATH", snapshot_manifest)
    assert module.load_version() == "0.11.1-SNAPSHOT-pr42"


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
    assert fm["model"] == "inherit", (
        "agents must use the current Claude Code session model rather than a "
        "stale hard-coded model ID"
    )


def test_no_unexpected_agent_files():
    found = sorted(p.name for p in (REPO / "agents").glob("*.md"))
    assert found == sorted(AGENT_FILES)


def test_extractor_prompt_has_qualified_outcome_dedup_regression_example():
    prompt = (REPO / "agents" / "fact-extractor.md").read_text(encoding="utf-8")
    assert "Repeated qualified outcome" in prompt
    assert "do not turn the scope qualifier into a second fact" in prompt


def test_shared_skills_are_platform_neutral():
    for path in (REPO / "skills" / "aissert" / "SKILL.md", REPO / "skills" / "aissert-workflow" / "SKILL.md"):
        skill = path.read_text(encoding="utf-8")
        assert "Claude" not in skill
        assert "Codex" not in skill


def test_codex_execution_adapter_reaches_the_isolated_runner():
    adapter = (REPO / "skills" / "aissert-codex" / "SKILL.md").read_text(encoding="utf-8")
    assert "run_codex_eval.py" in adapter
    assert "isolated `codex exec` workers" in adapter
    assert "--smoke" in adapter


def test_platform_specific_execution_rules_live_outside_shared_skills():
    commands = "\n".join((REPO / "commands" / name).read_text(encoding="utf-8") for name in ("eval.md", "smoke.md"))
    runner = (REPO / "skills" / "aissert" / "scripts" / "run_codex_eval.py").read_text(encoding="utf-8")
    assert "Claude Code agents" in commands
    assert "Codex CLI" in runner


def test_codex_runner_requires_modern_python_for_strict_contract_validation():
    runner = (REPO / "skills" / "aissert" / "scripts" / "run_codex_eval.py").read_text(encoding="utf-8")
    assert "sys.version_info < (3, 10)" in runner
    assert "if not has_text(output):" in runner
    assert "if not has_valid_facts(output):" in runner
    assert runner.count("if not has_json_object(output):") == 3


def test_example_bug_summarizer_keeps_failed_mitigations_and_avoids_inference():
    skill = (REPO / "skills" / "example-bug-summarizer" / "SKILL.md").read_text(encoding="utf-8")
    normalized_skill = " ".join(skill.split())
    assert "observed behavior persists despite that action" in normalized_skill
    assert "Do not infer unstated procedural steps" in skill


# ---------------------------------------------------------- skill, command


@pytest.mark.parametrize("skill_name", ["aissert", "aissert-codex", "aissert-workflow", "example-bug-summarizer"])
def test_skill_frontmatter(skill_name):
    fm = parse_frontmatter(REPO / "skills" / skill_name / "SKILL.md")
    assert fm["name"] == skill_name
    assert fm["description"].strip()


def test_golden_target_skills_are_packaged():
    for manifest_path in sorted((REPO / "golden").glob("*/manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        target_skill = manifest["target_skill"]
        skill_path = REPO / "skills" / target_skill / "SKILL.md"
        assert skill_path.is_file(), (
            f"{manifest_path.relative_to(REPO)} targets missing packaged skill "
            f"{target_skill!r}"
        )
        assert parse_frontmatter(skill_path)["name"] == target_skill


@pytest.mark.parametrize("command_name", ["eval", "smoke"])
def test_command_frontmatter(command_name):
    fm = parse_frontmatter(REPO / "commands" / f"{command_name}.md")
    assert fm["description"].strip()
    assert fm["argument-hint"].strip()


def test_eval_and_smoke_commands_have_distinct_entry_points():
    eval_text = (REPO / "commands" / "eval.md").read_text(encoding="utf-8")
    smoke_text = (REPO / "commands" / "smoke.md").read_text(encoding="utf-8")

    assert "$ARGUMENTS" in eval_text
    assert "$ARGUMENTS" in smoke_text
    assert "--smoke" not in eval_text
    assert "--smoke" in smoke_text
    assert "iterations=N" in parse_frontmatter(REPO / "commands" / "eval.md")[
        "argument-hint"
    ]
    assert "iterations=N" not in parse_frontmatter(
        REPO / "commands" / "smoke.md"
    )["argument-hint"]


def test_contracts_exist():
    refs = REPO / "skills" / "aissert" / "references"
    assert (refs / "golden-set-schema.md").is_file()
    assert (refs / "results-schema.md").is_file()
