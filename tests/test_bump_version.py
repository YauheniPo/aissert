import importlib.util
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
BUMP_VERSION_PATH = REPO / "scripts" / "bump_version.py"

spec = importlib.util.spec_from_file_location("bump_version", BUMP_VERSION_PATH)
bump_version = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(bump_version)


def test_latest_release_tag_ignores_snapshot_tags(monkeypatch):
    def fake_run_git(*args):
        assert args == ("tag", "-l", "aissert--v*")
        return "\n".join(
            [
                "aissert--v0.8.0-SNAPSHOT",
                "aissert--v0.7.0",
                "aissert--v0.9.0-SNAPSHOT-feature",
                "aissert--v0.6.2",
            ]
        )

    monkeypatch.setattr(bump_version, "run_git", fake_run_git)

    assert bump_version.latest_release_tag() == "aissert--v0.7.0"


def test_latest_release_tag_returns_none_when_only_snapshot_tags(monkeypatch):
    def fake_run_git(*args):
        assert args == ("tag", "-l", "aissert--v*")
        return "\n".join(["aissert--v0.8.0-SNAPSHOT", "aissert--v0.9.0-SNAPSHOT-feature"])

    monkeypatch.setattr(bump_version, "run_git", fake_run_git)

    assert bump_version.latest_release_tag() is None
