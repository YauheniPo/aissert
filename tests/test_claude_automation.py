"""Tests for host-specific hook wiring and shared hook enforcement."""
import importlib.util
import io
import json
import os
import subprocess
import sys
import zipfile
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


def test_project_rules_have_separate_host_entrypoints_without_rule_duplication():
    project_rules = (REPO / "PROJECT_RULES.md").read_text(encoding="utf-8")
    agents = (REPO / "AGENTS.md").read_text(encoding="utf-8")
    claude = (REPO / "CLAUDE.md").read_text(encoding="utf-8")

    assert "All scoring math" in project_rules
    assert "Read `PROJECT_RULES.md`" in agents
    assert "Read `PROJECT_RULES.md`" in claude
    assert "All scoring math" not in agents
    assert "All scoring math" not in claude


def test_host_skill_entrypoints_delegate_to_neutral_project_skills():
    for name in ("verify", "wiki-maintenance"):
        canonical = REPO / "project-skills" / name / "SKILL.md"
        assert canonical.is_file()
        text = canonical.read_text(encoding="utf-8")
        assert "Claude" not in text
        assert "Codex" not in text

        for entrypoint in (
            REPO / ".claude" / "skills" / name / "SKILL.md",
            REPO / ".codex" / "skills" / name / "SKILL.md",
        ):
            assert entrypoint.is_file()
            assert f"project-skills/{name}/SKILL.md" in entrypoint.read_text(encoding="utf-8")


def test_shared_verify_covers_both_packaging_surfaces_and_wiki():
    verify = (REPO / "project-skills" / "verify" / "SKILL.md").read_text(encoding="utf-8")
    assert "scripts/build_claude_plugin_zip.py" in verify
    assert "scripts/build_codex_plugin_zip.py" in verify
    assert "scripts/wiki/lint.py" in verify


def test_codex_plugin_omits_unsupported_lifecycle_hook_declaration():
    plugin = json.loads((REPO / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert "hooks" not in plugin
    assert not (REPO / "hooks" / "hooks.codex.json").exists()


def test_claude_entrypoints_delegate_to_shared_hook_implementations():
    for name in (
        "hook_pre_tool_guard.py",
        "hook_post_tool_invariants.py",
        "hook_bump_golden_version.py",
        "hook_stop_verify.py",
    ):
        text = (REPO / "scripts" / "claude" / name).read_text(encoding="utf-8")
        assert "scripts.hooks" in text


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


def test_snapshot_builds_claude_and_codex_in_separate_jobs_without_ci_duplication():
    snapshot = (REPO / ".github" / "workflows" / "snapshot.yml").read_text(encoding="utf-8")
    ci = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "build-claude-plugin:" in snapshot
    assert "build-codex-plugin:" in snapshot
    assert "publish-snapshot:" in snapshot
    assert "needs: [prepare-snapshot, build-claude-plugin, build-codex-plugin]" in snapshot
    assert "python3 scripts/build_claude_plugin_zip.py" in snapshot
    assert "python3 scripts/build_codex_plugin_zip.py" in snapshot
    assert "actions/download-artifact@v8" in snapshot
    assert "build-codex-plugin:" not in ci


def test_managed_claude_review_config_documents_external_setup():
    text = (REPO / ".github" / "CLAUDE_CODE_REVIEW_CONFIG.md").read_text(encoding="utf-8")
    assert "Claude GitHub app" in text
    assert "not in a workflow file" in text
    assert "agents/*.md" in text


def test_claude_dev_automation_is_not_packaged_runtime_content():
    build_zip = load_module("scripts/build_claude_plugin_zip.py")
    include_paths = set(build_zip.INCLUDE_PATHS)
    assert ".claude" not in include_paths
    assert ".github" not in include_paths
    assert "scripts/claude" not in include_paths


def test_claude_package_allowlist_excludes_project_fixtures_and_codex_only_content():
    build_zip = load_module("scripts/build_claude_plugin_zip.py")
    include_paths = set(build_zip.INCLUDE_PATHS)

    assert "skills" not in include_paths
    assert "skills/aissert/scripts/run_codex_eval.py" not in include_paths
    assert "skills/aissert/scripts/run_target.py" not in include_paths
    assert "skills/example-bug-summarizer" not in include_paths
    assert "golden/example" not in include_paths
    assert "PROJECT_RULES.md" not in include_paths
    assert "AGENTS.md" not in include_paths
    assert "CLAUDE.md" not in include_paths
    assert not {
        "CHANGELOG.md",
        "CODE_OF_CONDUCT.md",
        "CONTRIBUTING.md",
        "ROADMAP.md",
        "SECURITY.md",
    } & include_paths

    assert {
        "skills/aissert/SKILL.md",
        "skills/aissert-workflow/SKILL.md",
        "skills/aissert/references",
        "skills/aissert/scripts/aggregate.py",
        "skills/aissert/scripts/check_canary.py",
        "skills/aissert/scripts/validate_golden.py",
    } <= include_paths


def test_built_claude_archive_excludes_project_and_codex_only_content(tmp_path):
    build_zip = load_module("scripts/build_claude_plugin_zip.py")
    archive_path = tmp_path / "aissert.zip"
    assert build_zip.main(["--output", str(archive_path)]) == 0

    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        names = set(archive.namelist())

    assert "skills/aissert/scripts/run_codex_eval.py" not in names
    assert "skills/aissert/scripts/run_target.py" not in names
    assert not any(name.startswith("skills/example-bug-summarizer/") for name in names)
    assert not any(name.startswith("golden/example/") for name in names)
    assert not {
        "AGENTS.md",
        "CLAUDE.md",
        "PROJECT_RULES.md",
        "CHANGELOG.md",
        "CODE_OF_CONDUCT.md",
        "CONTRIBUTING.md",
        "ROADMAP.md",
        "SECURITY.md",
    } & names


def test_codex_package_contains_only_supported_runtime_content():
    build_zip = load_module("scripts/build_codex_plugin_zip.py")
    include_paths = set(build_zip.INCLUDE_PATHS)
    assert "hooks" not in include_paths
    assert "scripts/hooks" not in include_paths
    assert "skills/aissert-codex/SKILL.md" in include_paths
    assert "skills/example-bug-summarizer" not in include_paths
    assert "golden/example" not in include_paths


def test_built_codex_archive_excludes_unsupported_hooks_and_project_files(tmp_path):
    build_zip = load_module("scripts/build_codex_plugin_zip.py")
    archive_path = tmp_path / "aissert-codex.zip"
    assert build_zip.main(["--output", str(archive_path)]) == 0

    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(tmp_path / "plugin")

    plugin_root = tmp_path / "plugin"
    assert not (plugin_root / ".claude-plugin").exists()
    assert not (plugin_root / "hooks").exists()
    assert not (plugin_root / "scripts" / "hooks").exists()
    assert not (plugin_root / "scripts" / "wiki").exists()
    assert not (plugin_root / "knowledge").exists()
    assert not (plugin_root / "skills" / "example-bug-summarizer").exists()
    assert not (plugin_root / "golden" / "example").exists()


def test_codex_reinstall_helper_refreshes_cache_and_starts_a_fresh_session(tmp_path):
    script = REPO / "scripts" / "codex" / "reinstall_plugin.sh"
    assert script.is_file()
    assert subprocess.run(["bash", "-n", str(script)], check=False).returncode == 0

    codex_home = tmp_path / "codex-home"
    cachebuster = (
        codex_home
        / "skills"
        / ".system"
        / "plugin-creator"
        / "scripts"
        / "update_plugin_cachebuster.py"
    )
    cachebuster.parent.mkdir(parents=True)
    cachebuster.write_text(
        "import sys\nprint('cachebuster', sys.argv[1])\n", encoding="utf-8"
    )

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_python = bin_dir / "python"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$1 $2\" == '-m pytest' ]]; then\n"
        "  printf '%s\\n' 'schema checks passed'\n"
        "  exit 0\n"
        "fi\n"
        f"exec '{sys.executable}' \"$@\"\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)

    fake_codex = bin_dir / "codex"
    fake_codex.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$1 $2\" == 'plugin marketplace' ]]; then\n"
        "  printf '%s\\n' 'Marketplace `aissert`'\n"
        f"  printf '%s\\n' '{REPO}/.agents/plugins/marketplace.json'\n"
        "elif [[ \"$1 $2\" == 'plugin list' ]]; then\n"
        "  printf '%s\\n' 'aissert@aissert  installed, enabled'\n"
        "elif [[ \"$1 $2\" == 'plugin add' ]]; then\n"
        "  printf 'plugin add: %s\\n' \"$*\"\n"
        "else\n"
        "  printf '%s\\n' 'fresh codex session'\n"
        "fi\n",
        encoding="utf-8",
    )
    fake_codex.chmod(0o755)

    env = os.environ | {
        "AISSERT_PYTHON": str(fake_python),
        "CODEX_HOME": str(codex_home),
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
    }
    completed = subprocess.run(
        ["bash", str(script)],
        cwd=REPO,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "cachebuster" in completed.stdout
    assert "plugin add: plugin add aissert@aissert --json" in completed.stdout
    assert "fresh codex session" in completed.stdout


def test_pre_tool_guard_detects_main_push():
    guard = load_module("scripts/hooks/pre_tool_guard.py")
    assert guard.command_pushes_main("git push origin main")
    assert guard.command_pushes_main("git push origin HEAD:main")
    assert not guard.command_pushes_main("git push origin feature/ci-fix")


def test_pre_tool_guard_detects_real_data_paths():
    guard = load_module("scripts/hooks/pre_tool_guard.py")
    assert guard.command_writes_real_data_inside_repo("cp -R /tmp/data golden-local/set")
    assert guard.command_writes_real_data_inside_repo("mv sample real-golden/demo")
    assert not guard.command_writes_real_data_inside_repo("python3 scripts/build_claude_plugin_zip.py")


def test_post_tool_invariants_hold_for_current_repo():
    invariants = load_module("scripts/hooks/post_tool_invariants.py")
    assert invariants.validate() == []


def test_wiki_stale_only_is_not_structural_stop_failure():
    stop_verify = load_module("scripts/hooks/stop_verify.py")
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
    hook = load_module("scripts/hooks/bump_golden_version.py")
    assert hook.golden_manifest_for_item(
        Path("golden/example/items/gs-001.json")
    ) == Path("golden/example/manifest.json")
    assert hook.golden_manifest_for_item(Path("golden/example/manifest.json")) is None
    assert hook.golden_manifest_for_item(Path("canary/items/cn-001.json")) is None


def test_bump_golden_version_treats_direct_manifest_edit_as_own_target():
    hook = load_module("scripts/hooks/bump_golden_version.py")
    assert hook.golden_manifest_for_edited_path(
        Path("golden/example/manifest.json")
    ) == Path("golden/example/manifest.json")
    assert hook.golden_manifest_for_edited_path(
        Path("golden/example/items/gs-001.json")
    ) == Path("golden/example/manifest.json")
    assert hook.golden_manifest_for_edited_path(Path("canary/manifest.json")) is None


def test_bump_golden_version_bumps_patch():
    hook = load_module("scripts/hooks/bump_golden_version.py")
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
    hook = load_module("scripts/hooks/bump_golden_version.py")
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

    hook = load_module("scripts/hooks/bump_golden_version.py")
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

    hook = load_module("scripts/hooks/bump_golden_version.py")
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
    hook = load_module("scripts/hooks/bump_golden_version.py")
    monkeypatch.setattr(hook, "REPO_ROOT", tmp_path)

    payload = {"tool_name": "Read", "tool_input": {"file_path": "golden/example/items/gs-001.json"}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    assert hook.main() == 0


def test_wiki_structural_issue_blocks_stop():
    stop_verify = load_module("scripts/hooks/stop_verify.py")
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
