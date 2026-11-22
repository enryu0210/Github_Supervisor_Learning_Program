from pathlib import Path

from watcher import branch_naming
from watcher.config import WatcherConfig
from watcher.github_client import GitHubClientError


def _config() -> WatcherConfig:
    return WatcherConfig(
        token="secret-token",
        repo="owner/repo",
        poll_interval_seconds=300,
        events_dir=Path("./events"),
        prs_path=Path("./prs.json"),
        review_concentration_path=Path("./review_concentration.json"),
        pr_reviews_path=Path("./pr_reviews.json"),
    )


def _branch(name: str, sha: str = "a" * 40) -> dict:
    return {"name": name, "commit": {"sha": sha, "url": "..."}, "protected": False}


def test_check_branch_detects_violation_and_attributes_member(monkeypatch) -> None:
    monkeypatch.setattr(
        branch_naming.github_client,
        "get_commit",
        lambda cfg, sha: {"author": {"login": "Hoil-Lim"}},
    )

    event = branch_naming.check_branch(_config(), _branch("MyBranch"))

    assert event is not None
    assert event.rule_id == "R05"
    assert event.severity == "low"
    assert event.branch == "MyBranch"
    assert event.member == "hoil-lim"
    assert "MyBranch" in event.explanation
    assert "제안" in event.explanation


def test_check_branch_skips_valid_name(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        branch_naming.github_client,
        "get_commit",
        lambda cfg, sha: calls.append(sha) or {"author": {"login": "someone"}},
    )

    event = branch_naming.check_branch(_config(), _branch("feature/cli-login-fix"))

    assert event is None
    assert calls == []


def test_check_branch_skips_exempt_branches(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        branch_naming.github_client,
        "get_commit",
        lambda cfg, sha: calls.append(sha) or {"author": {"login": "someone"}},
    )

    assert branch_naming.check_branch(_config(), _branch("main")) is None
    assert branch_naming.check_branch(_config(), _branch("develop")) is None
    assert calls == []


def test_check_branch_member_fallback_on_api_error(monkeypatch) -> None:
    def raise_error(cfg, sha):
        raise GitHubClientError("boom")

    monkeypatch.setattr(branch_naming.github_client, "get_commit", raise_error)

    event = branch_naming.check_branch(_config(), _branch("BadName"))

    assert event is not None
    assert event.member == "unknown"


def test_check_branch_member_fallback_when_author_is_null(monkeypatch) -> None:
    monkeypatch.setattr(
        branch_naming.github_client, "get_commit", lambda cfg, sha: {"author": None}
    )

    event = branch_naming.check_branch(_config(), _branch("BadName"))

    assert event is not None
    assert event.member == "unknown"


def test_check_branch_without_commit_sha(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        branch_naming.github_client,
        "get_commit",
        lambda cfg, sha: calls.append(sha) or {"author": {"login": "someone"}},
    )
    branch = {"name": "BadName", "commit": {}, "protected": False}

    event = branch_naming.check_branch(_config(), branch)

    assert event is not None
    assert event.member == "unknown"
    assert calls == []


def test_run_aggregates_only_violations(monkeypatch) -> None:
    monkeypatch.setattr(
        branch_naming.github_client,
        "list_branches",
        lambda cfg: [
            _branch("main"),
            _branch("feature/cli-x"),
            _branch("BadName"),
        ],
    )
    monkeypatch.setattr(
        branch_naming.github_client,
        "get_commit",
        lambda cfg, sha: {"author": {"login": "someone"}},
    )

    violations = branch_naming.run(_config())

    assert len(violations) == 1
    assert violations[0].rule_id == "R05"
    assert violations[0].branch == "BadName"


def test_run_returns_empty_for_no_branches(monkeypatch) -> None:
    monkeypatch.setattr(branch_naming.github_client, "list_branches", lambda cfg: [])

    assert branch_naming.run(_config()) == []
