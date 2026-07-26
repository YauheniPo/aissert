"""Unit tests for scripts/wiki/lib.py: frontmatter parsing, significant-change
heuristics, and lint checks (frontmatter errors, broken links/source paths,
missing index entries, orphans, stale pages, invalid commits).

Deterministic logic, same bar as aggregate.py (CLAUDE.md): every behavior
gets a test against a synthetic fixture, not the real knowledge/ tree (which
would make tests depend on live wiki content).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

WIKI_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts" / "wiki"
sys.path.insert(0, str(WIKI_SCRIPTS_DIR))

import lib  # noqa: E402


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    """A throwaway git repo with a knowledge/ dir, wired as lib's REPO_ROOT."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "test")

    knowledge = repo / "knowledge"
    knowledge.mkdir()
    (repo / "some_source.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "README.md").write_text("hi\n", encoding="utf-8")

    monkeypatch.setattr(lib, "REPO_ROOT", repo)
    monkeypatch.setattr(lib, "KNOWLEDGE_DIR", knowledge)
    monkeypatch.setattr(lib, "INDEX_PATH", knowledge / "index.md")
    return repo


def _commit_all(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _write_page(knowledge: Path, relpath: str, frontmatter: str, body: str = "content\n") -> Path:
    path = knowledge / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}\n---\n{body}", encoding="utf-8")
    return path


# ---------------------------------------------------------------- frontmatter


def test_parse_frontmatter_flat_and_array_fields():
    content = (
        "---\n"
        "title: Example\n"
        "kind: domain\n"
        "source_paths:\n"
        "  - a.py\n"
        "  - b.py\n"
        "---\n"
        "body text\n"
    )
    data, body = lib.parse_frontmatter(content)
    assert data == {
        "title": "Example",
        "kind": "domain",
        "source_paths": ["a.py", "b.py"],
    }
    assert body == "body text\n"


def test_parse_frontmatter_missing_block_returns_none():
    data, body = lib.parse_frontmatter("no frontmatter here\n")
    assert data is None
    assert body == "no frontmatter here\n"


def test_parse_frontmatter_strips_quotes():
    data, _ = lib.parse_frontmatter('---\ntitle: "Quoted Title"\n---\nbody\n')
    assert data["title"] == "Quoted Title"


# --------------------------------------------------------------- lint: pages


def test_validate_frontmatter_missing_required_field():
    page = {
        "repo_path": "knowledge/domains/x.md",
        "has_frontmatter": True,
        "frontmatter": {"title": "X", "kind": "domain"},
    }
    errors = lib.validate_frontmatter(page)
    fields = {e["field"] for e in errors if e["type"] == "missing_frontmatter_field"}
    assert fields == {"summary", "source_paths", "related_pages", "last_validated_commit"}


def test_validate_frontmatter_invalid_kind():
    page = {
        "repo_path": "knowledge/domains/x.md",
        "has_frontmatter": True,
        "frontmatter": {
            "title": "X",
            "kind": "not-a-real-kind",
            "summary": "s",
            "source_paths": ["a"],
            "related_pages": [],
            "last_validated_commit": "abc",
        },
    }
    errors = lib.validate_frontmatter(page)
    assert any(e["type"] == "invalid_kind" for e in errors)


def test_validate_frontmatter_exempt_pages_skip_all_checks():
    page = {"repo_path": "knowledge/index.md", "has_frontmatter": False, "frontmatter": {}}
    assert lib.validate_frontmatter(page) == []


def test_find_broken_source_paths(fake_repo):
    _write_page(
        fake_repo / "knowledge",
        "domains/x.md",
        "title: X\nkind: domain\nsummary: s\n"
        "source_paths:\n  - does_not_exist.py\nrelated_pages: []\n"
        "last_validated_commit: deadbeef\n",
    )
    pages = lib.load_wiki_pages()
    problems = lib.find_broken_source_paths(pages)
    assert problems == [
        {
            "type": "broken_source_path",
            "page": "knowledge/domains/x.md",
            "source_path": "does_not_exist.py",
        }
    ]


def test_find_broken_links_and_related_pages(fake_repo):
    _write_page(
        fake_repo / "knowledge",
        "domains/a.md",
        "title: A\nkind: domain\nsummary: s\nsource_paths:\n  - README.md\n"
        "related_pages:\n  - ../hotspots/missing.md\nlast_validated_commit: deadbeef\n",
        body="see [ghost page](../repo/ghost.md) for details\n",
    )
    pages = lib.load_wiki_pages()
    problems = lib.find_broken_links(pages)
    types = {(p["type"], p["target"]) for p in problems}
    assert ("broken_internal_link", "knowledge/repo/ghost.md") in types
    assert ("broken_related_page", "knowledge/hotspots/missing.md") in types


def test_find_missing_index_entries_and_orphans(fake_repo):
    knowledge = fake_repo / "knowledge"
    _write_page(
        knowledge,
        "index.md",
        "",
        body="# Index\n\n[Linked page](domains/linked.md)\n",
    )
    (knowledge / "index.md").write_text("# Index\n\n[Linked page](domains/linked.md)\n", encoding="utf-8")
    _write_page(
        knowledge,
        "domains/linked.md",
        "title: Linked\nkind: domain\nsummary: s\nsource_paths:\n  - README.md\n"
        "related_pages: []\nlast_validated_commit: deadbeef\n",
    )
    _write_page(
        knowledge,
        "domains/unlinked.md",
        "title: Unlinked\nkind: domain\nsummary: s\nsource_paths:\n  - README.md\n"
        "related_pages: []\nlast_validated_commit: deadbeef\n",
    )
    pages = lib.load_wiki_pages()

    missing = lib.find_missing_index_entries(pages)
    assert [m["page"] for m in missing] == ["knowledge/domains/unlinked.md"]

    orphans = lib.find_orphans(pages)
    assert [o["page"] for o in orphans] == ["knowledge/domains/unlinked.md"]


def test_stale_and_invalid_commit_pages(fake_repo):
    knowledge = fake_repo / "knowledge"
    page_path = _write_page(
        knowledge,
        "hotspots/h.md",
        "title: H\nkind: hotspot\nsummary: s\nsource_paths:\n  - some_source.py\n"
        "related_pages: []\nlast_validated_commit: PLACEHOLDER\n",
    )
    first_commit = _commit_all(fake_repo, "initial")
    content = page_path.read_text(encoding="utf-8").replace("PLACEHOLDER", first_commit)
    page_path.write_text(content, encoding="utf-8")
    _commit_all(fake_repo, "anchor page to first commit")

    # source_paths unchanged since last_validated_commit -> not stale.
    pages = lib.load_wiki_pages()
    assert lib.find_stale_pages(pages) == []
    assert lib.find_invalid_validated_commits(pages) == []

    # Now change the tracked source and commit -> page becomes stale.
    (fake_repo / "some_source.py").write_text("x = 2\n", encoding="utf-8")
    _commit_all(fake_repo, "change source")
    pages = lib.load_wiki_pages()
    stale = lib.find_stale_pages(pages)
    assert [s["page"] for s in stale] == ["knowledge/hotspots/h.md"]

    # A page with a bogus commit is reported invalid, not stale.
    bogus = _write_page(
        knowledge,
        "hotspots/bogus.md",
        "title: Bogus\nkind: hotspot\nsummary: s\nsource_paths:\n  - some_source.py\n"
        "related_pages: []\nlast_validated_commit: 0000000000000000000000000000000000000000\n",
    )
    pages = lib.load_wiki_pages()
    invalid = lib.find_invalid_validated_commits(pages)
    assert any(i["page"] == "knowledge/hotspots/bogus.md" for i in invalid)
    stale_pages = {s["page"] for s in lib.find_stale_pages(pages)}
    assert "knowledge/hotspots/bogus.md" not in stale_pages
    bogus.unlink()


# --------------------------------------------------------- significant change


def _page(source_paths):
    return {"has_frontmatter": True, "frontmatter": {"source_paths": source_paths}, "repo_path": "p"}


def test_significant_change_none_below_threshold():
    # A single change outside every anchor/prefix/high-signal bucket
    # (tests/ isn't high-signal — only .claude/, agents/, skills/, commands/,
    # golden/, canary/, scripts/claude/, scripts/wiki/,
    # README/DESIGN/CLAUDE.md are).
    result = lib.analyze_significant_change(
        ["tests/fixtures/example.json"],
        [],
        tracked_files=["tests/fixtures/example.json"],
        untracked_files=[],
    )
    assert result["significant_change"] is False
    assert result["reasons"] == []


def test_significant_change_threshold_excludes_knowledge_pages():
    tracked = [f"knowledge/domains/d{i}.md" for i in range(10)]
    result = lib.analyze_significant_change(tracked, [], tracked_files=tracked, untracked_files=[])
    assert result["significant_change"] is False


def test_significant_change_threshold_counts_non_knowledge_files():
    tracked = [f"tests/test_{i}.py" for i in range(lib.CHANGED_FILE_THRESHOLD)]
    result = lib.analyze_significant_change(tracked, [], tracked_files=tracked, untracked_files=[])
    assert result["significant_change"] is True
    assert result["reasons"][0]["type"] == "changed_file_threshold"


def test_significant_change_architectural_anchor():
    result = lib.analyze_significant_change(
        ["agents/judge-precision.md"],
        [],
        tracked_files=["agents/judge-precision.md"],
        untracked_files=[],
    )
    assert result["significant_change"] is True
    assert result["reasons"][0]["type"] == "architectural_anchor_changed"
    assert result["reasons"][0]["paths"] == ["agents/judge-precision.md"]


def test_significant_change_claude_automation_anchor():
    result = lib.analyze_significant_change(
        [".claude/settings.json"],
        [],
        tracked_files=[".claude/settings.json"],
        untracked_files=[],
    )
    reason_types = [r["type"] for r in result["reasons"]]
    assert "architectural_anchor_changed" in reason_types


def test_significant_change_uncovered_high_signal_path():
    pages = [_page(["agents/fact-extractor.md"])]
    result = lib.analyze_significant_change(
        ["agents/new-agent.md"],
        pages,
        tracked_files=["agents/new-agent.md"],
        untracked_files=[],
    )
    reason_types = [r["type"] for r in result["reasons"]]
    assert "uncovered_high_signal_path" in reason_types


def test_significant_change_covered_high_signal_path_is_not_flagged():
    pages = [_page(["agents/fact-extractor.md"])]
    result = lib.analyze_significant_change(
        ["agents/fact-extractor.md"],
        pages,
        tracked_files=["agents/fact-extractor.md"],
        untracked_files=[],
    )
    reason_types = [r["type"] for r in result["reasons"]]
    # still architectural_anchor_changed (agents/ prefix) but not uncovered
    assert "uncovered_high_signal_path" not in reason_types


# ---------------------------------------------------------------- read plan


def test_get_read_plan_always_includes_baseline_pages():
    plan = lib.get_read_plan([])
    assert plan == ["knowledge/index.md", "knowledge/status.md"]


def test_get_read_plan_matches_rule_pages():
    plan = lib.get_read_plan(["agents/judge-recall.md"])
    assert "knowledge/domains/eval-pipeline.md" in plan
    assert "knowledge/hotspots/judges-and-canary.md" in plan


def test_get_read_plan_matches_claude_automation():
    plan = lib.get_read_plan(["scripts/claude/hook_stop_verify.py"])
    assert "knowledge/repo/build-test-and-ci.md" in plan


def test_get_read_plan_falls_back_to_structure_for_unmatched_changes():
    plan = lib.get_read_plan(["some/totally/unmatched/path.txt"])
    assert "knowledge/repo/structure.md" in plan


# ------------------------------------------------------------------ coverage


def test_is_covered_by_wiki_prefix_match():
    coverage = [{"page": "p", "source_path": "agents"}]
    assert lib.is_covered_by_wiki("agents/fact-extractor.md", coverage)
    assert not lib.is_covered_by_wiki("golden/example", coverage)


def test_normalize_repo_path_strips_leading_dot_and_slash():
    assert lib.normalize_repo_path("./agents/x.md") == "agents/x.md"
    assert lib.normalize_repo_path("/agents/x.md") == "agents/x.md"
    assert lib.normalize_repo_path("agents\\x.md") == "agents/x.md"
