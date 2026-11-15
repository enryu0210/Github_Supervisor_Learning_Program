import pytest

from watcher import config


def _clear_env(monkeypatch) -> None:
    monkeypatch.delenv(config.TOKEN_ENV, raising=False)
    monkeypatch.delenv(config.REPO_ENV, raising=False)
    monkeypatch.delenv(config.POLL_INTERVAL_ENV, raising=False)


def test_load_config_raises_without_token(monkeypatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv(config.REPO_ENV, "Owner/Repo")
    with pytest.raises(config.WatcherConfigError):
        config.load_config()


def test_load_config_raises_without_repo(monkeypatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv(config.TOKEN_ENV, "ghp_test")
    with pytest.raises(config.WatcherConfigError):
        config.load_config()


def test_load_config_raises_on_malformed_repo(monkeypatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv(config.TOKEN_ENV, "ghp_test")
    monkeypatch.setenv(config.REPO_ENV, "not-owner-slash-name")
    with pytest.raises(config.WatcherConfigError):
        config.load_config()


def test_load_config_lowercases_repo(monkeypatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv(config.TOKEN_ENV, "ghp_test")
    monkeypatch.setenv(config.REPO_ENV, "Enryu0210/Github_Supervisor_Learning_Program")
    cfg = config.load_config()
    assert cfg.repo == "enryu0210/github_supervisor_learning_program"


def test_load_config_uses_default_poll_interval(monkeypatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv(config.TOKEN_ENV, "ghp_test")
    monkeypatch.setenv(config.REPO_ENV, "owner/repo")
    cfg = config.load_config()
    assert cfg.poll_interval_seconds == config.DEFAULT_POLL_INTERVAL_SECONDS


def test_load_config_reads_custom_poll_interval(monkeypatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv(config.TOKEN_ENV, "ghp_test")
    monkeypatch.setenv(config.REPO_ENV, "owner/repo")
    monkeypatch.setenv(config.POLL_INTERVAL_ENV, "30")
    cfg = config.load_config()
    assert cfg.poll_interval_seconds == 30


def test_load_config_raises_on_non_integer_poll_interval(monkeypatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv(config.TOKEN_ENV, "ghp_test")
    monkeypatch.setenv(config.REPO_ENV, "owner/repo")
    monkeypatch.setenv(config.POLL_INTERVAL_ENV, "soon")
    with pytest.raises(config.WatcherConfigError):
        config.load_config()


def test_load_config_raises_on_non_positive_poll_interval(monkeypatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv(config.TOKEN_ENV, "ghp_test")
    monkeypatch.setenv(config.REPO_ENV, "owner/repo")
    monkeypatch.setenv(config.POLL_INTERVAL_ENV, "0")
    with pytest.raises(config.WatcherConfigError):
        config.load_config()
