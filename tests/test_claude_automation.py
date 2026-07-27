"""Tests for repo-local Claude Code automation hooks and config."""
import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def load_module(relpath: str):
    path = REPO / relpath
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_claude_settings_wires_hooks_and_skills():
    settings = json.loads((REPO / ".claude" / "settings.json").read_text(encoding="utf-8"))
    hooks = settings["hooks"]
    assert {"PreToolUse", "PostToolUse", "SessionStart", "Stop"} <= set(hooks)
    assert (REPO / ".claude" / "skills" / "verify" / "SKILL.md").is_file()
    assert (REPO / ".claude" / "skills" / "wiki-maintenance" / "SKILL.md").is_file()


def test_worktreeinclude_does_not_copy_sensitive_or_real_data_paths():
    text = (REPO / ".worktreeinclude").read_text(encoding="utf-8")
    active_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert active_lines == []
    assert ".env" in text
    assert "golden-local/" in text


def test_claude_github_action_uses_repo_settings_and_scoped_tools():
    workflow = (REPO / ".github" / "workflows" / "claude.yml").read_text(encoding="utf-8")
    assert "actions/checkout@v7" in workflow
    assert "actions/setup-python@v7" in workflow
    assert "pip install pytest" in workflow
    assert "anthropics/claude-code-action@v1" in workflow
    assert 'settings: ".claude/settings.json"' in workflow
    assert 'trigger_phrase: "@claude"' in workflow
    assert "--permission-mode dontAsk" in workflow
    assert "--allowedTools" in workflow
    assert "Bash(pytest tests/ -q)" in workflow


def test_managed_claude_review_config_documents_external_setup():
    text = (REPO / ".github" / "CLAUDE_CODE_REVIEW_CONFIG.md").read_text(encoding="utf-8")
    assert "Claude GitHub app" in text
    assert "not in a workflow file" in text
    assert "agents/*.md" in text


def test_claude_dev_automation_is_not_packaged_runtime_content():
    build_zip = load_module("scripts/build_plugin_zip.py")
    include_paths = set(build_zip.INCLUDE_PATHS)
    assert ".claude" not in include_paths
    assert ".github" not in include_paths
    assert "scripts/claude" not in include_paths


def test_pre_tool_guard_detects_main_push():
    guard = load_module("scripts/claude/hook_pre_tool_guard.py")
    assert guard.command_pushes_main("git push origin main")
    assert guard.command_pushes_main("git push origin HEAD:main")
    assert not guard.command_pushes_main("git push origin feature/ci-fix")


def test_pre_tool_guard_detects_real_data_paths():
    guard = load_module("scripts/claude/hook_pre_tool_guard.py")
    assert guard.command_writes_real_data_inside_repo("cp -R /tmp/data golden-local/set")
    assert guard.command_writes_real_data_inside_repo("mv sample real-golden/demo")
    assert not guard.command_writes_real_data_inside_repo("python3 scripts/build_plugin_zip.py")


def test_post_tool_invariants_hold_for_current_repo():
    invariants = load_module("scripts/claude/hook_post_tool_invariants.py")
    assert invariants.validate() == []


def test_wiki_stale_only_is_not_structural_stop_failure():
    stop_verify = load_module("scripts/claude/hook_stop_verify.py")
    payload = {
        "summary": {
            "stale_pages": ["knowledge/repo/structure.md"],
            "missing_index_entries": 0,
            "orphan_pages": 0,
            "invalid_validated_commits": 0,
            "broken_source_paths": 0,
            "broken_links": 0,
            "frontmatter_errors": 0,
        }
    }
    assert not stop_verify.wiki_lint_structural_failure(json.dumps(payload))


def test_wiki_structural_issue_blocks_stop():
    stop_verify = load_module("scripts/claude/hook_stop_verify.py")
    payload = {
        "summary": {
            "stale_pages": [],
            "missing_index_entries": 1,
            "orphan_pages": 0,
            "invalid_validated_commits": 0,
            "broken_source_paths": 0,
            "broken_links": 0,
            "frontmatter_errors": 0,
        }
    }
    assert stop_verify.wiki_lint_structural_failure(json.dumps(payload))
