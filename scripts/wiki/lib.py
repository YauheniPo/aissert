"""Core logic for the repo-local LLM wiki under knowledge/.

Ported from a sibling project's scripts/wiki/lib.js (git helpers, frontmatter
parsing, lint checks, significant-change detection, read-plan resolution).
Same design; adapted to this repo's shape (no src/ tree, GitHub Actions
instead of GitLab MRs) and to Python/stdlib per this repo's conventions.

Deliberately NOT reused by aggregate.py or any eval-pipeline script: this is
documentation tooling, kept fully separate from the scoring pipeline.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from config import (
    INDEX_PATH,
    KNOWLEDGE_DIR,
    OPTIONAL_FRONTMATTER_FIELDS,
    READ_PLAN_RULES,
    REPO_ROOT,
    REQUIRED_FRONTMATTER_FIELDS,
    SIGNIFICANT_ANCHORS,
    SIGNIFICANT_PREFIXES,
    CHANGED_FILE_THRESHOLD,
    VALID_KINDS,
)

LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


# ------------------------------------------------------------------- git


def safe_exec_git(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return ""


def git_ref_exists(ref: str) -> bool:
    return bool(safe_exec_git(["rev-parse", "--verify", "--quiet", ref]))


def git_commit_ref_exists(ref: str | None) -> bool:
    if not ref:
        return False
    return bool(safe_exec_git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"]))


def git_path_is_tracked(repo_path: str) -> bool:
    if not repo_path:
        return False
    return bool(safe_exec_git(["ls-files", "--error-unmatch", "--", repo_path]))


def _collect_git_output_lines(output: str, files: set[str]) -> None:
    if not output:
        return
    for line in output.split("\n"):
        value = normalize_repo_path(line.strip())
        if value:
            files.add(value)


def get_remote_default_branch_ref() -> str:
    symbolic_ref = safe_exec_git(["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"])
    if symbolic_ref:
        return re.sub(r"^refs/remotes/", "", symbolic_ref)
    for candidate in ("origin/main", "origin/master"):
        if git_ref_exists(candidate):
            return candidate
    return ""


def get_target_branch_ref() -> str:
    """CI target branch. GitHub Actions sets GITHUB_BASE_REF on pull_request."""
    base_ref = os.environ.get("GITHUB_BASE_REF")
    if base_ref:
        for candidate in (f"origin/{base_ref}", base_ref):
            if git_ref_exists(candidate):
                return candidate
    return get_remote_default_branch_ref()


def get_branch_diff_base_ref() -> str:
    target_branch_ref = get_target_branch_ref()
    if not target_branch_ref:
        return ""
    return safe_exec_git(["merge-base", "HEAD", target_branch_ref])


def get_branch_diff_files() -> list[str]:
    files: set[str] = set()
    merge_base = get_branch_diff_base_ref()
    if not merge_base:
        return []
    _collect_git_output_lines(
        safe_exec_git(["diff", "--name-only", merge_base, "HEAD"]), files
    )
    return sorted(files)


def get_working_tree_changed_files() -> list[str]:
    files: set[str] = set()
    for output in (
        safe_exec_git(["diff", "--name-only"]),
        safe_exec_git(["diff", "--name-only", "--cached"]),
        safe_exec_git(["ls-files", "--others", "--exclude-standard"]),
    ):
        _collect_git_output_lines(output, files)
    return sorted(files)


def get_changed_files() -> list[str]:
    files: set[str] = set()
    files.update(get_branch_diff_files())
    files.update(get_working_tree_changed_files())
    return sorted(files)


def git_diff_since_commit(commit: str | None, paths: list[str]) -> list[str]:
    if not commit or not paths:
        return []
    output = safe_exec_git(["diff", "--name-only", commit, "--", *paths])
    if not output:
        return []
    return [line.strip() for line in output.split("\n") if line.strip()]


def split_tracked_and_untracked(
    changed_files: list[str],
    tracked_files: list[str] | None = None,
    untracked_files: list[str] | None = None,
) -> dict[str, list[str]]:
    if tracked_files is not None or untracked_files is not None:
        return {
            "tracked": sorted({normalize_repo_path(f) for f in (tracked_files or []) if f}),
            "untracked": sorted({normalize_repo_path(f) for f in (untracked_files or []) if f}),
        }

    tracked: list[str] = []
    untracked: list[str] = []
    for file in changed_files:
        (tracked if git_path_is_tracked(file) else untracked).append(file)
    return {"tracked": sorted(set(tracked)), "untracked": sorted(set(untracked))}


# ------------------------------------------------------------------- paths


def to_repo_path(full_path: Path) -> str:
    return full_path.resolve().relative_to(REPO_ROOT).as_posix()


def normalize_repo_path(value: str) -> str:
    value = value.replace("\\", "/")
    value = re.sub(r"^\./+", "", value)
    value = re.sub(r"^/+", "", value)
    return value


def file_or_dir_exists(repo_path: str) -> bool:
    return (REPO_ROOT / repo_path).exists()


def walk_markdown_files(directory: Path) -> list[Path]:
    return sorted(directory.rglob("*.md"))


# ------------------------------------------------------------ frontmatter


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_frontmatter(content: str) -> tuple[dict | None, str]:
    """Deliberately simple: flat `key: value` lines + `key:` block-array of
    `- item` lines. No nested structures — same constraint as the source
    project's parser, and the same reason: keep pages hand-editable and the
    parser dependency-free.
    """
    if not content.startswith("---\n"):
        return None, content

    end_index = content.find("\n---\n", 4)
    if end_index == -1:
        return None, content

    raw = content[4:end_index]
    body = content[end_index + 5 :]
    data: dict = {}
    current_array_key: str | None = None

    for line in raw.split("\n"):
        if not line.strip():
            continue

        if line.startswith("  - ") or line.startswith("- "):
            if not current_array_key:
                continue
            value = re.sub(r"^\s*-\s*", "", line).strip()
            data[current_array_key].append(_strip_quotes(value))
            continue

        current_array_key = None
        if ":" not in line:
            continue
        key, _, raw_value = line.partition(":")
        key = key.strip()
        raw_value = raw_value.strip()

        if not raw_value:
            data[key] = []
            current_array_key = key
            continue

        data[key] = _strip_quotes(raw_value)

    return data, body


# --------------------------------------------------------------- pages


def collect_internal_links(page_path: Path, body: str) -> list[str]:
    directory = page_path.parent
    links = []
    for match in LINK_PATTERN.finditer(body):
        target = match.group(1).strip()
        if target.startswith(("http://", "https://", "#")):
            continue
        without_anchor = target.split("#")[0]
        if not without_anchor.endswith(".md"):
            continue
        resolved = (directory / without_anchor).resolve()
        if KNOWLEDGE_DIR not in resolved.parents and resolved != KNOWLEDGE_DIR:
            continue
        links.append(to_repo_path(resolved))
    return links


def read_index_content() -> str:
    return INDEX_PATH.read_text(encoding="utf-8") if INDEX_PATH.is_file() else ""


def get_index_link_targets() -> set[str]:
    targets: set[str] = set()
    for match in LINK_PATTERN.finditer(read_index_content()):
        target = match.group(1).strip()
        if target.startswith(("http://", "https://", "#")):
            continue
        without_anchor = target.split("#")[0]
        if not without_anchor.endswith(".md"):
            continue
        resolved = (KNOWLEDGE_DIR / without_anchor).resolve()
        if KNOWLEDGE_DIR not in resolved.parents and resolved != KNOWLEDGE_DIR:
            continue
        targets.add(to_repo_path(resolved))
    return targets


def load_wiki_pages() -> list[dict]:
    pages = []
    for full_path in walk_markdown_files(KNOWLEDGE_DIR):
        repo_path = to_repo_path(full_path)
        content = full_path.read_text(encoding="utf-8")
        data, body = parse_frontmatter(content)
        pages.append(
            {
                "full_path": full_path,
                "repo_path": repo_path,
                "content": content,
                "body": body,
                "frontmatter": data,
                "has_frontmatter": data is not None,
                "links": collect_internal_links(full_path, body),
            }
        )
    return pages


def _is_exempt(repo_path: str) -> bool:
    return repo_path in ("knowledge/index.md", "knowledge/log.md")


def validate_frontmatter(page: dict) -> list[dict]:
    errors: list[dict] = []
    if _is_exempt(page["repo_path"]):
        return errors

    if not page["has_frontmatter"]:
        errors.append({"type": "missing_frontmatter", "page": page["repo_path"]})
        return errors

    fm = page["frontmatter"]
    for field in REQUIRED_FRONTMATTER_FIELDS:
        if field not in fm:
            errors.append(
                {"type": "missing_frontmatter_field", "page": page["repo_path"], "field": field}
            )

    for key in fm:
        if key not in REQUIRED_FRONTMATTER_FIELDS and key not in OPTIONAL_FRONTMATTER_FIELDS:
            errors.append(
                {"type": "unknown_frontmatter_field", "page": page["repo_path"], "field": key}
            )

    if fm.get("kind") and fm["kind"] not in VALID_KINDS:
        errors.append(
            {"type": "invalid_kind", "page": page["repo_path"], "value": fm["kind"]}
        )

    for array_field in ("source_paths", "related_pages"):
        if array_field in fm and not isinstance(fm[array_field], list):
            errors.append(
                {
                    "type": "frontmatter_array_expected",
                    "page": page["repo_path"],
                    "field": array_field,
                }
            )

    return errors


def resolve_repo_target(page: dict, target: str) -> str:
    target_path = normalize_repo_path(target)
    absolute = (page["full_path"].parent / target_path).resolve()
    return to_repo_path(absolute)


def find_broken_source_paths(pages: list[dict]) -> list[dict]:
    problems = []
    for page in pages:
        fm = page["frontmatter"]
        if not page["has_frontmatter"] or not isinstance(fm.get("source_paths"), list):
            continue
        for source_path in fm["source_paths"]:
            repo_path = normalize_repo_path(source_path)
            if not file_or_dir_exists(repo_path):
                problems.append(
                    {
                        "type": "broken_source_path",
                        "page": page["repo_path"],
                        "source_path": repo_path,
                    }
                )
    return problems


def find_broken_links(pages: list[dict]) -> list[dict]:
    page_set = {page["repo_path"] for page in pages}
    problems = []
    for page in pages:
        for link in page["links"]:
            if link not in page_set:
                problems.append(
                    {"type": "broken_internal_link", "page": page["repo_path"], "target": link}
                )

        fm = page["frontmatter"]
        if not page["has_frontmatter"] or not isinstance(fm.get("related_pages"), list):
            continue
        for related in fm["related_pages"]:
            resolved = resolve_repo_target(page, related)
            if resolved not in page_set:
                problems.append(
                    {
                        "type": "broken_related_page",
                        "page": page["repo_path"],
                        "target": resolved,
                    }
                )
    return problems


def find_missing_index_entries(pages: list[dict]) -> list[dict]:
    index_targets = get_index_link_targets()
    problems = []
    for page in pages:
        if _is_exempt(page["repo_path"]):
            continue
        if page["repo_path"] not in index_targets:
            problems.append({"type": "missing_index_entry", "page": page["repo_path"]})
    return problems


def find_orphans(pages: list[dict]) -> list[dict]:
    inbound: dict[str, int] = {page["repo_path"]: 0 for page in pages}
    index_targets = get_index_link_targets()

    for page in pages:
        if page["repo_path"] == "knowledge/index.md":
            continue
        if page["repo_path"] in index_targets:
            inbound[page["repo_path"]] = inbound.get(page["repo_path"], 0) + 1

    for page in pages:
        for link in page["links"]:
            inbound[link] = inbound.get(link, 0) + 1

        fm = page["frontmatter"]
        if not page["has_frontmatter"] or not isinstance(fm.get("related_pages"), list):
            continue
        for related in fm["related_pages"]:
            resolved = resolve_repo_target(page, related)
            inbound[resolved] = inbound.get(resolved, 0) + 1

    return [
        {"type": "orphan_page", "page": page["repo_path"]}
        for page in pages
        if page["repo_path"] not in ("knowledge/index.md", "knowledge/log.md")
        and inbound.get(page["repo_path"], 0) == 0
    ]


def find_invalid_validated_commits(pages: list[dict]) -> list[dict]:
    problems = []
    for page in pages:
        if not page["has_frontmatter"]:
            continue
        commit = page["frontmatter"].get("last_validated_commit")
        if not commit:
            continue
        if not git_commit_ref_exists(commit):
            problems.append(
                {"type": "invalid_last_validated_commit", "page": page["repo_path"], "commit": commit}
            )
    return problems


def find_stale_pages(pages: list[dict]) -> list[dict]:
    stale = []
    changed_files = set(get_changed_files())
    invalid_commit_pages = {p["page"] for p in find_invalid_validated_commits(pages)}

    for page in pages:
        fm = page["frontmatter"]
        if not page["has_frontmatter"] or not isinstance(fm.get("source_paths"), list):
            continue
        if page["repo_path"] in changed_files:
            continue
        if page["repo_path"] in invalid_commit_pages:
            continue

        commit = fm.get("last_validated_commit")
        normalized_paths = [normalize_repo_path(p) for p in fm["source_paths"]]
        changed_since_validation = git_diff_since_commit(commit, normalized_paths)
        if changed_since_validation:
            stale.append(
                {
                    "type": "stale_page",
                    "page": page["repo_path"],
                    "changed_paths": changed_since_validation,
                }
            )
    return stale


def collect_coverage(pages: list[dict]) -> list[dict]:
    covered = []
    for page in pages:
        fm = page["frontmatter"]
        if not page["has_frontmatter"] or not isinstance(fm.get("source_paths"), list):
            continue
        for source_path in fm["source_paths"]:
            covered.append({"page": page["repo_path"], "source_path": normalize_repo_path(source_path)})
    return covered


def is_covered_by_wiki(repo_path: str, coverage_entries: list[dict]) -> bool:
    return any(
        repo_path == entry["source_path"] or repo_path.startswith(f"{entry['source_path']}/")
        for entry in coverage_entries
    )


# ------------------------------------------------------- significant change


def analyze_significant_change(
    changed_files: list[str],
    pages: list[dict],
    tracked_files: list[str] | None = None,
    untracked_files: list[str] | None = None,
) -> dict:
    reasons = []
    coverage = collect_coverage(pages)
    all_changed_files = sorted(
        {normalize_repo_path(f) for f in changed_files if f}
        - {"knowledge/queries/.gitkeep"}
    )
    split = split_tracked_and_untracked(all_changed_files, tracked_files, untracked_files)
    tracked_changed_files = split["tracked"]
    untracked_changed_files = split["untracked"]
    significant_input_files = all_changed_files

    # Wiki pages don't count toward the threshold: otherwise wiki maintenance
    # itself re-triggers significant_change on the very next session.
    threshold_files = [f for f in tracked_changed_files if not f.startswith("knowledge/")]
    if len(threshold_files) >= CHANGED_FILE_THRESHOLD:
        reasons.append({"type": "changed_file_threshold", "count": len(threshold_files)})

    touched_anchors = [
        f
        for f in significant_input_files
        if f in SIGNIFICANT_ANCHORS or any(f.startswith(p) for p in SIGNIFICANT_PREFIXES)
    ]
    if touched_anchors:
        reasons.append({"type": "architectural_anchor_changed", "paths": sorted(set(touched_anchors))})

    def is_high_signal(file: str) -> bool:
        if file.startswith(("knowledge/", "eval-runs/")):
            return False
        return (
            file.startswith((
                ".claude/",
                "agents/",
                "skills/",
                "commands/",
                "golden/",
                "canary/",
                "scripts/claude/",
                "scripts/codex/",
                "scripts/wiki/",
            ))
            or file in ("README.md", "DESIGN.md", "PROJECT_RULES.md", "AGENTS.md", "CLAUDE.md")
        )

    uncovered_paths = [
        f
        for f in significant_input_files
        if is_high_signal(f) and not is_covered_by_wiki(f, coverage)
    ]
    if uncovered_paths:
        reasons.append({"type": "uncovered_high_signal_path", "paths": sorted(set(uncovered_paths))})

    return {
        "significant_change": len(reasons) > 0,
        "changed_files": sorted(significant_input_files),
        "tracked_changed_files": tracked_changed_files,
        "untracked_changed_files": untracked_changed_files,
        "reasons": reasons,
    }


def get_read_plan(changed_files: list[str]) -> list[str]:
    pages = {"knowledge/index.md", "knowledge/status.md"}
    for file in changed_files:
        for rule in READ_PLAN_RULES:
            if any(file == pattern or file.startswith(pattern) for pattern in rule["patterns"]):
                pages.update(rule["pages"])

    if len(pages) == 2 and changed_files:
        pages.add("knowledge/repo/structure.md")

    return sorted(pages)


# ------------------------------------------------------------------ health


def collect_wiki_health() -> dict:
    pages = load_wiki_pages()
    frontmatter_errors = [err for page in pages for err in validate_frontmatter(page)]
    invalid_validated_commits = find_invalid_validated_commits(pages)
    broken_source_paths = find_broken_source_paths(pages)
    broken_links = find_broken_links(pages)
    missing_index_entries = find_missing_index_entries(pages)
    orphan_pages = find_orphans(pages)
    stale_pages = find_stale_pages(pages)

    return {
        "pages": pages,
        "issues": {
            "frontmatter": frontmatter_errors,
            "invalid_validated_commits": invalid_validated_commits,
            "broken_source_paths": broken_source_paths,
            "broken_links": broken_links,
            "missing_index_entries": missing_index_entries,
            "orphan_pages": orphan_pages,
            "stale_pages": stale_pages,
        },
    }


def summarize_health(health: dict) -> dict:
    stale_pages = [item["page"] for item in health["issues"]["stale_pages"]]
    return {
        "total_pages": len([p for p in health["pages"] if p["repo_path"].endswith(".md")]),
        "stale_pages": sorted(set(stale_pages)),
        "missing_index_entries": len(health["issues"]["missing_index_entries"]),
        "orphan_pages": len(health["issues"]["orphan_pages"]),
        "invalid_validated_commits": len(health["issues"]["invalid_validated_commits"]),
        "broken_source_paths": len(health["issues"]["broken_source_paths"]),
        "broken_links": len(health["issues"]["broken_links"]),
        "frontmatter_errors": len(health["issues"]["frontmatter"]),
    }
