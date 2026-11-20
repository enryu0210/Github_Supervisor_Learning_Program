from pathlib import Path

from watcher import pr_base_detection
from watcher.config import WatcherConfig


def _config() -> WatcherConfig:
    return WatcherConfig(
        token="secret-token",
        repo="owner/repo",
        poll_interval_seconds=300,
        events_dir=Path("./events"),
        prs_path=Path("./prs.json"),
    )


def _pr(*, number: int = 1, head: str, base: str, author: str = "hoil-lim") -> dict:
    return {
        "number": number,
        "head": {"ref": head},
        "base": {"ref": base},
        "user": {"login": author},
    }


def test_check_pr_base_flags_feature_branch_targeting_main() -> None:
    event = pr_base_detection.check_pr_base(
        "owner/repo", _pr(head="feature/cli-login-fix", base="main")
    )

    assert event is not None
    assert event.rule_id == "R08"
    assert event.severity == "low"
    assert event.branch == "feature/cli-login-fix"
    assert event.pr_number == 1
    assert event.member == "hoil-lim"
    assert "develop" in event.explanation


def test_check_pr_base_flags_fix_branch_targeting_main() -> None:
    event = pr_base_detection.check_pr_base(
        "owner/repo", _pr(head="fix/cli-typo", base="main")
    )

    assert event is not None
    assert event.rule_id == "R08"


def test_check_pr_base_allows_branch_targeting_develop() -> None:
    event = pr_base_detection.check_pr_base(
        "owner/repo", _pr(head="feature/cli-login-fix", base="develop")
    )

    assert event is None


def test_check_pr_base_exempts_release_branch_targeting_main() -> None:
    event = pr_base_detection.check_pr_base(
        "owner/repo", _pr(head="release/v0.2", base="main")
    )

    assert event is None


def test_run_aggregates_only_violations(monkeypatch) -> None:
    monkeypatch.setattr(
        pr_base_detection.github_client,
        "list_open_pulls",
        lambda cfg: [
            _pr(number=1, head="feature/cli-x", base="develop"),
            _pr(number=2, head="fix/cli-y", base="main"),
            _pr(number=3, head="release/v0.2", base="main"),
        ],
    )

    violations = pr_base_detection.run(_config())

    assert len(violations) == 1
    assert violations[0].pr_number == 2


def test_run_returns_empty_for_no_open_pulls(monkeypatch) -> None:
    monkeypatch.setattr(
        pr_base_detection.github_client, "list_open_pulls", lambda cfg: []
    )

    assert pr_base_detection.run(_config()) == []
