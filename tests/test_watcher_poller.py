import logging
from pathlib import Path

from gitcoach.models import Event
from watcher import poller
from watcher.config import WatcherConfig
from watcher.github_client import GitHubClientError


def _config(
    poll_interval_seconds: int = 7, events_dir: Path | None = None
) -> WatcherConfig:
    return WatcherConfig(
        token="secret-token",
        repo="owner/repo",
        poll_interval_seconds=poll_interval_seconds,
        events_dir=events_dir or Path("./events"),
    )


def _event(rule_id: str = "R01") -> Event:
    return Event(
        id="11111111-1111-1111-1111-111111111111",
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
    with caplog.at_level(logging.INFO, logger="watcher"):
        poller.poll_once(_config())
    assert "owner/repo" in caplog.text
    assert "develop" in caplog.text


def test_poll_once_writes_detected_events(monkeypatch, caplog, tmp_path) -> None:
    monkeypatch.setattr(
        poller.github_client, "get_repo", lambda cfg: {"default_branch": "main"}
    )
    monkeypatch.setattr(poller.push_detection, "run", lambda cfg: [_event()])

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

    poller.poll_once(_config(events_dir=tmp_path))

    assert list(tmp_path.iterdir()) == []


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
