from pathlib import Path

from watcher import push_detection
from watcher.config import WatcherConfig
from watcher.github_client import GitHubClientError


def _config() -> WatcherConfig:
    return WatcherConfig(
        token="secret-token",
        repo="owner/repo",
        poll_interval_seconds=300,
        events_dir=Path("./events"),
    )


def _push_event(
    *,
    ref: str = "refs/heads/main",
    before: str = "a" * 40,
    head: str = "b" * 40,
    actor_login: str = "hoil-lim",
) -> dict:
    return {
        "type": "PushEvent",
        "actor": {"login": actor_login},
        "payload": {"ref": ref, "before": before, "head": head},
    }


def test_check_push_event_ignores_non_push_events() -> None:
    assert (
        push_detection.check_push_event(_config(), {"type": "PullRequestEvent"}) == []
    )


def test_check_push_event_detects_r01_when_no_merged_pr(monkeypatch) -> None:
    monkeypatch.setattr(
        push_detection.github_client, "list_pulls_for_commit", lambda cfg, sha: []
    )
    monkeypatch.setattr(
        push_detection.github_client,
        "compare_commits",
        lambda cfg, before, head: {"status": "ahead"},
    )

    violations = push_detection.check_push_event(_config(), _push_event())

    assert len(violations) == 1
    assert violations[0].rule_id == "R01"
    assert violations[0].severity == "high"
    assert violations[0].branch == "main"
    assert violations[0].member == "hoil-lim"


def test_check_push_event_skips_r01_when_pr_merge(monkeypatch) -> None:
    monkeypatch.setattr(
        push_detection.github_client,
        "list_pulls_for_commit",
        lambda cfg, sha: [
            {"base": {"ref": "main"}, "merged_at": "2026-11-16T00:00:00Z"}
        ],
    )
    monkeypatch.setattr(
        push_detection.github_client,
        "compare_commits",
        lambda cfg, before, head: {"status": "ahead"},
    )

    violations = push_detection.check_push_event(_config(), _push_event())

    assert violations == []


def test_check_push_event_ignores_unrelated_pr_on_commit(monkeypatch) -> None:
    monkeypatch.setattr(
        push_detection.github_client,
        "list_pulls_for_commit",
        lambda cfg, sha: [
            {"base": {"ref": "develop"}, "merged_at": "2026-11-16T00:00:00Z"}
        ],
    )
    monkeypatch.setattr(
        push_detection.github_client,
        "compare_commits",
        lambda cfg, before, head: {"status": "ahead"},
    )

    violations = push_detection.check_push_event(_config(), _push_event())

    assert len(violations) == 1
    assert violations[0].rule_id == "R01"


def test_check_push_event_does_not_check_r01_for_non_protected_branch(
    monkeypatch,
) -> None:
    calls = []
    monkeypatch.setattr(
        push_detection.github_client,
        "list_pulls_for_commit",
        lambda cfg, sha: calls.append(sha) or [],
    )
    monkeypatch.setattr(
        push_detection.github_client,
        "compare_commits",
        lambda cfg, before, head: {"status": "ahead"},
    )

    violations = push_detection.check_push_event(
        _config(), _push_event(ref="refs/heads/feature/cli-login-fix")
    )

    assert violations == []
    assert calls == []


def test_check_push_event_detects_r02_when_diverged(monkeypatch) -> None:
    monkeypatch.setattr(
        push_detection.github_client,
        "list_pulls_for_commit",
        lambda cfg, sha: [
            {"base": {"ref": "main"}, "merged_at": "2026-11-16T00:00:00Z"}
        ],
    )
    monkeypatch.setattr(
        push_detection.github_client,
        "compare_commits",
        lambda cfg, before, head: {"status": "diverged"},
    )

    violations = push_detection.check_push_event(_config(), _push_event())

    assert len(violations) == 1
    assert violations[0].rule_id == "R02"
    assert violations[0].severity == "high"


def test_check_push_event_skips_r02_when_ahead(monkeypatch) -> None:
    monkeypatch.setattr(
        push_detection.github_client,
        "list_pulls_for_commit",
        lambda cfg, sha: [
            {"base": {"ref": "main"}, "merged_at": "2026-11-16T00:00:00Z"}
        ],
    )
    monkeypatch.setattr(
        push_detection.github_client,
        "compare_commits",
        lambda cfg, before, head: {"status": "ahead"},
    )

    violations = push_detection.check_push_event(_config(), _push_event())

    assert violations == []


def test_check_push_event_skips_r02_for_new_branch(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        push_detection.github_client,
        "list_pulls_for_commit",
        lambda cfg, sha: [],
    )
    monkeypatch.setattr(
        push_detection.github_client,
        "compare_commits",
        lambda cfg, before, head: (
            calls.append((before, head)) or {"status": "diverged"}
        ),
    )

    violations = push_detection.check_push_event(
        _config(),
        _push_event(ref="refs/heads/feature/cli-x", before="0" * 40),
    )

    assert not any(v.rule_id == "R02" for v in violations)
    assert calls == []


def test_check_push_event_detects_both_r01_and_r02(monkeypatch) -> None:
    monkeypatch.setattr(
        push_detection.github_client, "list_pulls_for_commit", lambda cfg, sha: []
    )
    monkeypatch.setattr(
        push_detection.github_client,
        "compare_commits",
        lambda cfg, before, head: {"status": "diverged"},
    )

    violations = push_detection.check_push_event(_config(), _push_event())

    assert {v.rule_id for v in violations} == {"R01", "R02"}


def test_is_pr_merge_fails_open_on_api_error(monkeypatch) -> None:
    def raise_error(cfg, sha):
        raise GitHubClientError("boom")

    monkeypatch.setattr(
        push_detection.github_client, "list_pulls_for_commit", raise_error
    )

    assert push_detection._is_pr_merge(_config(), "sha", "main") is True


def test_is_force_push_fails_open_on_api_error(monkeypatch) -> None:
    def raise_error(cfg, before, head):
        raise GitHubClientError("boom")

    monkeypatch.setattr(push_detection.github_client, "compare_commits", raise_error)

    assert push_detection._is_force_push(_config(), "before", "head") is False


def test_run_filters_non_push_events_and_aggregates(monkeypatch) -> None:
    raw_events = [
        {"type": "WatchEvent"},
        _push_event(ref="refs/heads/feature/cli-x", before="0" * 40, head="c" * 40),
        _push_event(),
    ]
    monkeypatch.setattr(
        push_detection.github_client, "list_events", lambda cfg: raw_events
    )
    monkeypatch.setattr(
        push_detection.github_client, "list_pulls_for_commit", lambda cfg, sha: []
    )
    monkeypatch.setattr(
        push_detection.github_client,
        "compare_commits",
        lambda cfg, before, head: {"status": "ahead"},
    )

    violations = push_detection.run(_config())

    assert [v.rule_id for v in violations] == ["R01"]
