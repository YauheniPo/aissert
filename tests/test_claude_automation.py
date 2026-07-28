"""Tests for repo-local Claude Code automation hooks and config."""
import importlib.util
import io
import json
import subprocess
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


def test_bump_golden_version_maps_item_path_to_manifest():
    hook = load_module("scripts/claude/hook_bump_golden_version.py")
    assert hook.golden_manifest_for_item(
        Path("golden/example/items/gs-001.json")
    ) == Path("golden/example/manifest.json")
    assert hook.golden_manifest_for_item(Path("golden/example/manifest.json")) is None
    assert hook.golden_manifest_for_item(Path("canary/items/cn-001.json")) is None


def test_bump_golden_version_treats_direct_manifest_edit_as_own_target():
    hook = load_module("scripts/claude/hook_bump_golden_version.py")
    assert hook.golden_manifest_for_edited_path(
        Path("golden/example/manifest.json")
    ) == Path("golden/example/manifest.json")
    assert hook.golden_manifest_for_edited_path(
        Path("golden/example/items/gs-001.json")
    ) == Path("golden/example/manifest.json")
    assert hook.golden_manifest_for_edited_path(Path("canary/manifest.json")) is None


def test_bump_golden_version_bumps_patch():
    hook = load_module("scripts/claude/hook_bump_golden_version.py")
    assert hook.bump_patch("1.0.0") == "1.0.1"
    assert hook.bump_patch("2.9.9") == "2.9.10"
    assert hook.bump_patch("not-a-version") is None


def _init_git_repo_with_manifest(tmp_path: Path, set_version: str) -> Path:
    manifest_dir = tmp_path / "golden" / "example"
    manifest_dir.mkdir(parents=True)
    manifest_path = manifest_dir / "manifest.json"
    manifest_path.write_text(json.dumps({"set_version": set_version}) + "\n", encoding="utf-8")
    for args in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Test"],
        ["git", "add", "-A"],
        ["git", "commit", "-q", "-m", "init"],
    ):
        subprocess.run(args, cwd=tmp_path, check=True)
    return manifest_path


def test_bump_golden_version_is_idempotent_until_next_commit(tmp_path, monkeypatch):
    manifest_path = _init_git_repo_with_manifest(tmp_path, "1.0.0")
    hook = load_module("scripts/claude/hook_bump_golden_version.py")
    monkeypatch.setattr(hook, "REPO_ROOT", tmp_path)

    rel_manifest = Path("golden/example/manifest.json")
    assert hook.maybe_bump(rel_manifest) == "1.0.1"
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["set_version"] == "1.0.1"

    # Same working-tree session, no new commit yet: must not bump again.
    assert hook.maybe_bump(rel_manifest) is None
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["set_version"] == "1.0.1"


def test_bump_golden_version_hook_main_bumps_on_item_write(tmp_path, monkeypatch, capsys):
    manifest_path = _init_git_repo_with_manifest(tmp_path, "1.0.0")
    (tmp_path / "golden" / "example" / "items").mkdir()
    item_path = tmp_path / "golden" / "example" / "items" / "gs-001.json"
    item_path.write_text("{}", encoding="utf-8")

    hook = load_module("scripts/claude/hook_bump_golden_version.py")
    monkeypatch.setattr(hook, "REPO_ROOT", tmp_path)

    payload = {"tool_name": "Write", "tool_input": {"file_path": str(item_path)}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    assert hook.main() == 0
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["set_version"] == "1.0.1"
    assert "bumped golden/example/manifest.json -> 1.0.1" in capsys.readouterr().out


def test_bump_golden_version_hook_main_bumps_on_direct_manifest_edit(tmp_path, monkeypatch, capsys):
    manifest_path = _init_git_repo_with_manifest(tmp_path, "1.0.0")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["defaults"] = {"min_supported_to_total_output_facts_ratio": 0.85, "min_covered_to_total_reference_facts_ratio": 0.70}
    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")

    hook = load_module("scripts/claude/hook_bump_golden_version.py")
    monkeypatch.setattr(hook, "REPO_ROOT", tmp_path)

    payload = {"tool_name": "Edit", "tool_input": {"file_path": str(manifest_path)}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    assert hook.main() == 0
    updated = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert updated["set_version"] == "1.0.1"
    assert updated["defaults"] == {"min_supported_to_total_output_facts_ratio": 0.85, "min_covered_to_total_reference_facts_ratio": 0.70}
    assert "bumped golden/example/manifest.json -> 1.0.1" in capsys.readouterr().out


def test_bump_golden_version_hook_ignores_unrelated_tools(tmp_path, monkeypatch):
    _init_git_repo_with_manifest(tmp_path, "1.0.0")
    hook = load_module("scripts/claude/hook_bump_golden_version.py")
    monkeypatch.setattr(hook, "REPO_ROOT", tmp_path)

    payload = {"tool_name": "Read", "tool_input": {"file_path": "golden/example/items/gs-001.json"}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    assert hook.main() == 0


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
