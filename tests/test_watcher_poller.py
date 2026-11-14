import logging

from watcher import poller
from watcher.config import WatcherConfig
from watcher.github_client import GitHubClientError


def _config(poll_interval_seconds: int = 7) -> WatcherConfig:
    return WatcherConfig(
        token="secret-token",
        repo="owner/repo",
        poll_interval_seconds=poll_interval_seconds,
    )


def test_poll_once_logs_default_branch(monkeypatch, caplog) -> None:
    monkeypatch.setattr(
        poller.github_client, "get_repo", lambda cfg: {"default_branch": "develop"}
    )
    with caplog.at_level(logging.INFO, logger="watcher"):
        poller.poll_once(_config())
    assert "owner/repo" in caplog.text
    assert "develop" in caplog.text


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
