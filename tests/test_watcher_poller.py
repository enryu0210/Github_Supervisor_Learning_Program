import json
import logging
from pathlib import Path

from gitcoach.models import Event
from watcher import poller
from watcher.config import WatcherConfig
from watcher.github_client import GitHubClientError


def _config(
    poll_interval_seconds: int = 7,
    events_dir: Path | None = None,
    prs_path: Path | None = None,
    review_concentration_path: Path | None = None,
) -> WatcherConfig:
    return WatcherConfig(
        token="secret-token",
        repo="owner/repo",
        poll_interval_seconds=poll_interval_seconds,
        events_dir=events_dir or Path("./events"),
        prs_path=prs_path or Path("./prs.json"),
        review_concentration_path=review_concentration_path
        or Path("./review_concentration.json"),
    )


def _event(rule_id: str = "R01") -> Event:
    return Event(
        id=f"11111111-1111-1111-1111-{rule_id.lower():0>12}",
        schema_version=1,
        occurred_at="2026-11-16T00:00:00+09:00",
        source="github",
        repo="owner/repo",
        member="hoil-lim",
        rule_id=rule_id,
        severity="high",
        action="detected",
        command_summary=None,
        branch="main",
        explanation="테스트용 감지 이벤트",
    )


def test_poll_once_logs_default_branch(monkeypatch, caplog) -> None:
    monkeypatch.setattr(
        poller.github_client, "get_repo", lambda cfg: {"default_branch": "develop"}
    )
    monkeypatch.setattr(poller.push_detection, "run", lambda cfg: [])
    monkeypatch.setattr(poller.branch_naming, "run", lambda cfg: [])
    monkeypatch.setattr(poller.pr_base_detection, "run", lambda cfg: [])
    monkeypatch.setattr(poller.commit_message, "run", lambda cfg: [])
    monkeypatch.setattr(poller.stale_prs, "run", lambda cfg: [])
    monkeypatch.setattr(poller.stale_prs, "write_snapshot", lambda records, path: path)
    monkeypatch.setattr(poller.review_concentration, "run", lambda cfg: [])
    monkeypatch.setattr(
        poller.review_concentration, "write_snapshot", lambda records, path: path
    )
    with caplog.at_level(logging.INFO, logger="watcher"):
        poller.poll_once(_config())
    assert "owner/repo" in caplog.text
    assert "develop" in caplog.text


def test_poll_once_writes_detected_events(monkeypatch, caplog, tmp_path) -> None:
    monkeypatch.setattr(
        poller.github_client, "get_repo", lambda cfg: {"default_branch": "main"}
    )
    monkeypatch.setattr(poller.push_detection, "run", lambda cfg: [_event()])
    monkeypatch.setattr(poller.branch_naming, "run", lambda cfg: [])
    monkeypatch.setattr(poller.pr_base_detection, "run", lambda cfg: [])
    monkeypatch.setattr(poller.commit_message, "run", lambda cfg: [])
    monkeypatch.setattr(poller.stale_prs, "run", lambda cfg: [])
    monkeypatch.setattr(poller.stale_prs, "write_snapshot", lambda records, path: path)
    monkeypatch.setattr(poller.review_concentration, "run", lambda cfg: [])
    monkeypatch.setattr(
        poller.review_concentration, "write_snapshot", lambda records, path: path
    )

    with caplog.at_level(logging.INFO, logger="watcher"):
        poller.poll_once(_config(events_dir=tmp_path))

    written = list(tmp_path.iterdir())
    assert len(written) == 1
    assert "R01" in caplog.text


def test_poll_once_writes_no_file_when_no_violations(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        poller.github_client, "get_repo", lambda cfg: {"default_branch": "main"}
    )
    monkeypatch.setattr(poller.push_detection, "run", lambda cfg: [])
    monkeypatch.setattr(poller.branch_naming, "run", lambda cfg: [])
    monkeypatch.setattr(poller.pr_base_detection, "run", lambda cfg: [])
    monkeypatch.setattr(poller.commit_message, "run", lambda cfg: [])
    monkeypatch.setattr(poller.stale_prs, "run", lambda cfg: [])
    monkeypatch.setattr(poller.stale_prs, "write_snapshot", lambda records, path: path)
    monkeypatch.setattr(poller.review_concentration, "run", lambda cfg: [])
    monkeypatch.setattr(
        poller.review_concentration, "write_snapshot", lambda records, path: path
    )

    poller.poll_once(_config(events_dir=tmp_path))

    assert list(tmp_path.iterdir()) == []


def test_poll_once_writes_events_from_both_detectors(
    monkeypatch, caplog, tmp_path
) -> None:
    monkeypatch.setattr(
        poller.github_client, "get_repo", lambda cfg: {"default_branch": "main"}
    )
    monkeypatch.setattr(
        poller.push_detection, "run", lambda cfg: [_event(rule_id="R01")]
    )
    monkeypatch.setattr(
        poller.branch_naming, "run", lambda cfg: [_event(rule_id="R05")]
    )
    monkeypatch.setattr(poller.pr_base_detection, "run", lambda cfg: [])
    monkeypatch.setattr(poller.commit_message, "run", lambda cfg: [])
    monkeypatch.setattr(poller.stale_prs, "run", lambda cfg: [])
    monkeypatch.setattr(poller.stale_prs, "write_snapshot", lambda records, path: path)
    monkeypatch.setattr(poller.review_concentration, "run", lambda cfg: [])
    monkeypatch.setattr(
        poller.review_concentration, "write_snapshot", lambda records, path: path
    )

    with caplog.at_level(logging.INFO, logger="watcher"):
        poller.poll_once(_config(events_dir=tmp_path))

    assert len(list(tmp_path.iterdir())) == 2
    assert "R01" in caplog.text
    assert "R05" in caplog.text


def test_poll_once_writes_branch_naming_events_only(
    monkeypatch, caplog, tmp_path
) -> None:
    monkeypatch.setattr(
        poller.github_client, "get_repo", lambda cfg: {"default_branch": "main"}
    )
    monkeypatch.setattr(poller.push_detection, "run", lambda cfg: [])
    monkeypatch.setattr(
        poller.branch_naming, "run", lambda cfg: [_event(rule_id="R05")]
    )
    monkeypatch.setattr(poller.pr_base_detection, "run", lambda cfg: [])
    monkeypatch.setattr(poller.commit_message, "run", lambda cfg: [])
    monkeypatch.setattr(poller.stale_prs, "run", lambda cfg: [])
    monkeypatch.setattr(poller.stale_prs, "write_snapshot", lambda records, path: path)
    monkeypatch.setattr(poller.review_concentration, "run", lambda cfg: [])
    monkeypatch.setattr(
        poller.review_concentration, "write_snapshot", lambda records, path: path
    )

    with caplog.at_level(logging.INFO, logger="watcher"):
        poller.poll_once(_config(events_dir=tmp_path))

    written = list(tmp_path.iterdir())
    assert len(written) == 1
    assert "R05" in caplog.text


def test_poll_once_writes_pr_base_events_only(monkeypatch, caplog, tmp_path) -> None:
    monkeypatch.setattr(
        poller.github_client, "get_repo", lambda cfg: {"default_branch": "main"}
    )
    monkeypatch.setattr(poller.push_detection, "run", lambda cfg: [])
    monkeypatch.setattr(poller.branch_naming, "run", lambda cfg: [])
    monkeypatch.setattr(
        poller.pr_base_detection, "run", lambda cfg: [_event(rule_id="R08")]
    )
    monkeypatch.setattr(poller.commit_message, "run", lambda cfg: [])
    monkeypatch.setattr(poller.stale_prs, "run", lambda cfg: [])
    monkeypatch.setattr(poller.stale_prs, "write_snapshot", lambda records, path: path)
    monkeypatch.setattr(poller.review_concentration, "run", lambda cfg: [])
    monkeypatch.setattr(
        poller.review_concentration, "write_snapshot", lambda records, path: path
    )

    with caplog.at_level(logging.INFO, logger="watcher"):
        poller.poll_once(_config(events_dir=tmp_path))

    written = list(tmp_path.iterdir())
    assert len(written) == 1
    assert "R08" in caplog.text


def test_poll_once_writes_commit_message_events_only(
    monkeypatch, caplog, tmp_path
) -> None:
    monkeypatch.setattr(
        poller.github_client, "get_repo", lambda cfg: {"default_branch": "main"}
    )
    monkeypatch.setattr(poller.push_detection, "run", lambda cfg: [])
    monkeypatch.setattr(poller.branch_naming, "run", lambda cfg: [])
    monkeypatch.setattr(poller.pr_base_detection, "run", lambda cfg: [])
    monkeypatch.setattr(
        poller.commit_message, "run", lambda cfg: [_event(rule_id="R06")]
    )
    monkeypatch.setattr(poller.stale_prs, "run", lambda cfg: [])
    monkeypatch.setattr(poller.stale_prs, "write_snapshot", lambda records, path: path)
    monkeypatch.setattr(poller.review_concentration, "run", lambda cfg: [])
    monkeypatch.setattr(
        poller.review_concentration, "write_snapshot", lambda records, path: path
    )

    with caplog.at_level(logging.INFO, logger="watcher"):
        poller.poll_once(_config(events_dir=tmp_path))

    written = list(tmp_path.iterdir())
    assert len(written) == 1
    assert "R06" in caplog.text


def test_poll_once_writes_events_from_all_detectors(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        poller.github_client, "get_repo", lambda cfg: {"default_branch": "main"}
    )
    monkeypatch.setattr(
        poller.push_detection, "run", lambda cfg: [_event(rule_id="R01")]
    )
    monkeypatch.setattr(
        poller.branch_naming, "run", lambda cfg: [_event(rule_id="R05")]
    )
    monkeypatch.setattr(
        poller.pr_base_detection, "run", lambda cfg: [_event(rule_id="R08")]
    )
    monkeypatch.setattr(
        poller.commit_message, "run", lambda cfg: [_event(rule_id="R06")]
    )
    monkeypatch.setattr(poller.stale_prs, "run", lambda cfg: [])
    monkeypatch.setattr(poller.stale_prs, "write_snapshot", lambda records, path: path)
    monkeypatch.setattr(poller.review_concentration, "run", lambda cfg: [])
    monkeypatch.setattr(
        poller.review_concentration, "write_snapshot", lambda records, path: path
    )

    poller.poll_once(_config(events_dir=tmp_path))

    assert len(list(tmp_path.iterdir())) == 4


def test_poll_once_writes_prs_snapshot(monkeypatch, caplog, tmp_path) -> None:
    monkeypatch.setattr(
        poller.github_client, "get_repo", lambda cfg: {"default_branch": "main"}
    )
    monkeypatch.setattr(poller.push_detection, "run", lambda cfg: [])
    monkeypatch.setattr(poller.branch_naming, "run", lambda cfg: [])
    monkeypatch.setattr(poller.pr_base_detection, "run", lambda cfg: [])
    monkeypatch.setattr(poller.commit_message, "run", lambda cfg: [])
    pr_record = {"repo": "owner/repo", "number": 1, "state": "open"}
    monkeypatch.setattr(poller.stale_prs, "run", lambda cfg: [pr_record])
    monkeypatch.setattr(poller.review_concentration, "run", lambda cfg: [])
    monkeypatch.setattr(
        poller.review_concentration, "write_snapshot", lambda records, path: path
    )

    prs_path = tmp_path / "prs.json"
    with caplog.at_level(logging.INFO, logger="watcher"):
        poller.poll_once(_config(events_dir=tmp_path / "events", prs_path=prs_path))

    assert json.loads(prs_path.read_text(encoding="utf-8")) == [pr_record]
    assert "1건" in caplog.text


def test_poll_once_overwrites_prs_snapshot_when_empty(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        poller.github_client, "get_repo", lambda cfg: {"default_branch": "main"}
    )
    monkeypatch.setattr(poller.push_detection, "run", lambda cfg: [])
    monkeypatch.setattr(poller.branch_naming, "run", lambda cfg: [])
    monkeypatch.setattr(poller.pr_base_detection, "run", lambda cfg: [])
    monkeypatch.setattr(poller.commit_message, "run", lambda cfg: [])
    monkeypatch.setattr(poller.stale_prs, "run", lambda cfg: [])
    monkeypatch.setattr(poller.review_concentration, "run", lambda cfg: [])
    monkeypatch.setattr(
        poller.review_concentration, "write_snapshot", lambda records, path: path
    )

    prs_path = tmp_path / "prs.json"
    prs_path.write_text(json.dumps([{"number": 1}]), encoding="utf-8")

    poller.poll_once(_config(events_dir=tmp_path / "events", prs_path=prs_path))

    assert json.loads(prs_path.read_text(encoding="utf-8")) == []


def test_poll_once_writes_review_concentration_snapshot(
    monkeypatch, caplog, tmp_path
) -> None:
    monkeypatch.setattr(
        poller.github_client, "get_repo", lambda cfg: {"default_branch": "main"}
    )
    monkeypatch.setattr(poller.push_detection, "run", lambda cfg: [])
    monkeypatch.setattr(poller.branch_naming, "run", lambda cfg: [])
    monkeypatch.setattr(poller.pr_base_detection, "run", lambda cfg: [])
    monkeypatch.setattr(poller.commit_message, "run", lambda cfg: [])
    monkeypatch.setattr(poller.stale_prs, "run", lambda cfg: [])
    monkeypatch.setattr(poller.stale_prs, "write_snapshot", lambda records, path: path)
    summary = [{"reviewer": "hoil-lim", "review_count": 3, "share": 1.0}]
    monkeypatch.setattr(poller.review_concentration, "run", lambda cfg: summary)

    review_path = tmp_path / "review_concentration.json"
    with caplog.at_level(logging.INFO, logger="watcher"):
        poller.poll_once(
            _config(
                events_dir=tmp_path / "events",
                review_concentration_path=review_path,
            )
        )

    assert json.loads(review_path.read_text(encoding="utf-8")) == summary
    assert "1명" in caplog.text


def test_poll_once_overwrites_review_concentration_snapshot_when_empty(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(
        poller.github_client, "get_repo", lambda cfg: {"default_branch": "main"}
    )
    monkeypatch.setattr(poller.push_detection, "run", lambda cfg: [])
    monkeypatch.setattr(poller.branch_naming, "run", lambda cfg: [])
    monkeypatch.setattr(poller.pr_base_detection, "run", lambda cfg: [])
    monkeypatch.setattr(poller.commit_message, "run", lambda cfg: [])
    monkeypatch.setattr(poller.stale_prs, "run", lambda cfg: [])
    monkeypatch.setattr(poller.stale_prs, "write_snapshot", lambda records, path: path)
    monkeypatch.setattr(poller.review_concentration, "run", lambda cfg: [])

    review_path = tmp_path / "review_concentration.json"
    review_path.write_text(json.dumps([{"reviewer": "old"}]), encoding="utf-8")

    poller.poll_once(
        _config(events_dir=tmp_path / "events", review_concentration_path=review_path)
    )

    assert json.loads(review_path.read_text(encoding="utf-8")) == []


def test_run_forever_sleeps_between_ticks(monkeypatch) -> None:
    monkeypatch.setattr(poller, "poll_once", lambda cfg: None)
    sleeps = []
    poller.run_forever(
        _config(poll_interval_seconds=42), sleep=sleeps.append, max_iterations=3
    )
    assert sleeps == [42, 42, 42]


def test_run_forever_continues_after_poll_failure(monkeypatch, caplog) -> None:
    calls = []

    def fake_poll_once(cfg):
        calls.append(cfg)
        raise GitHubClientError("boom")

    monkeypatch.setattr(poller, "poll_once", fake_poll_once)
    with caplog.at_level(logging.WARNING, logger="watcher"):
        poller.run_forever(_config(), sleep=lambda s: None, max_iterations=2)

    assert len(calls) == 2
    assert "boom" in caplog.text


def test_run_forever_continues_after_unexpected_error(monkeypatch, caplog) -> None:
    calls = []

    def fake_poll_once(cfg):
        calls.append(cfg)
        raise ValueError("unexpected")

    monkeypatch.setattr(poller, "poll_once", fake_poll_once)
    with caplog.at_level(logging.ERROR, logger="watcher"):
        poller.run_forever(_config(), sleep=lambda s: None, max_iterations=2)

    assert len(calls) == 2
    assert "unexpected" in caplog.text
