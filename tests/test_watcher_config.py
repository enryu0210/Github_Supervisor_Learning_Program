from pathlib import Path

import pytest

from watcher import config


def _clear_env(monkeypatch) -> None:
    monkeypatch.delenv(config.TOKEN_ENV, raising=False)
    monkeypatch.delenv(config.REPO_ENV, raising=False)
    monkeypatch.delenv(config.POLL_INTERVAL_ENV, raising=False)
    monkeypatch.delenv(config.REVIEW_CONCENTRATION_PATH_ENV, raising=False)
    monkeypatch.delenv(config.SUPABASE_URL_ENV, raising=False)
    monkeypatch.delenv(config.SUPABASE_SERVICE_KEY_ENV, raising=False)
    monkeypatch.delenv(config.OLLAMA_URL_ENV, raising=False)


def _set_required_env(monkeypatch) -> None:
    monkeypatch.setenv(config.TOKEN_ENV, "ghp_test")
    monkeypatch.setenv(config.REPO_ENV, "owner/repo")
    monkeypatch.setenv(config.SUPABASE_URL_ENV, "https://example.supabase.co")
    monkeypatch.setenv(config.SUPABASE_SERVICE_KEY_ENV, "service-key")


def test_load_config_raises_without_token(monkeypatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv(config.REPO_ENV, "Owner/Repo")
    monkeypatch.setenv(config.SUPABASE_URL_ENV, "https://example.supabase.co")
    monkeypatch.setenv(config.SUPABASE_SERVICE_KEY_ENV, "service-key")
    with pytest.raises(config.WatcherConfigError):
        config.load_config()


def test_load_config_raises_without_repo(monkeypatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv(config.TOKEN_ENV, "ghp_test")
    monkeypatch.setenv(config.SUPABASE_URL_ENV, "https://example.supabase.co")
    monkeypatch.setenv(config.SUPABASE_SERVICE_KEY_ENV, "service-key")
    with pytest.raises(config.WatcherConfigError):
        config.load_config()


def test_load_config_raises_on_malformed_repo(monkeypatch) -> None:
    _clear_env(monkeypatch)
    _set_required_env(monkeypatch)
    monkeypatch.setenv(config.REPO_ENV, "not-owner-slash-name")
    with pytest.raises(config.WatcherConfigError):
        config.load_config()


def test_load_config_raises_without_supabase_url(monkeypatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv(config.TOKEN_ENV, "ghp_test")
    monkeypatch.setenv(config.REPO_ENV, "owner/repo")
    monkeypatch.setenv(config.SUPABASE_SERVICE_KEY_ENV, "service-key")
    with pytest.raises(config.WatcherConfigError):
        config.load_config()


def test_load_config_raises_without_supabase_service_key(monkeypatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv(config.TOKEN_ENV, "ghp_test")
    monkeypatch.setenv(config.REPO_ENV, "owner/repo")
    monkeypatch.setenv(config.SUPABASE_URL_ENV, "https://example.supabase.co")
    with pytest.raises(config.WatcherConfigError):
        config.load_config()


def test_load_config_lowercases_repo(monkeypatch) -> None:
    _clear_env(monkeypatch)
    _set_required_env(monkeypatch)
    monkeypatch.setenv(config.REPO_ENV, "Enryu0210/Github_Supervisor_Learning_Program")
    cfg = config.load_config()
    assert cfg.repo == "enryu0210/github_supervisor_learning_program"


def test_load_config_reads_supabase_credentials(monkeypatch) -> None:
    _clear_env(monkeypatch)
    _set_required_env(monkeypatch)
    cfg = config.load_config()
    assert cfg.supabase_url == "https://example.supabase.co"
    assert cfg.supabase_service_key == "service-key"


def test_load_config_uses_default_poll_interval(monkeypatch) -> None:
    _clear_env(monkeypatch)
    _set_required_env(monkeypatch)
    cfg = config.load_config()
    assert cfg.poll_interval_seconds == config.DEFAULT_POLL_INTERVAL_SECONDS


def test_load_config_reads_custom_poll_interval(monkeypatch) -> None:
    _clear_env(monkeypatch)
    _set_required_env(monkeypatch)
    monkeypatch.setenv(config.POLL_INTERVAL_ENV, "30")
    cfg = config.load_config()
    assert cfg.poll_interval_seconds == 30


def test_load_config_raises_on_non_integer_poll_interval(monkeypatch) -> None:
    _clear_env(monkeypatch)
    _set_required_env(monkeypatch)
    monkeypatch.setenv(config.POLL_INTERVAL_ENV, "soon")
    with pytest.raises(config.WatcherConfigError):
        config.load_config()


def test_load_config_raises_on_non_positive_poll_interval(monkeypatch) -> None:
    _clear_env(monkeypatch)
    _set_required_env(monkeypatch)
    monkeypatch.setenv(config.POLL_INTERVAL_ENV, "0")
    with pytest.raises(config.WatcherConfigError):
        config.load_config()


def test_load_config_uses_default_review_concentration_path(monkeypatch) -> None:
    _clear_env(monkeypatch)
    _set_required_env(monkeypatch)
    cfg = config.load_config()
    assert cfg.review_concentration_path == Path(
        config.DEFAULT_REVIEW_CONCENTRATION_PATH
    )


def test_load_config_reads_custom_review_concentration_path(monkeypatch) -> None:
    _clear_env(monkeypatch)
    _set_required_env(monkeypatch)
    monkeypatch.setenv(
        config.REVIEW_CONCENTRATION_PATH_ENV, "/tmp/watcher-review-concentration.json"
    )
    cfg = config.load_config()
    assert cfg.review_concentration_path == Path(
        "/tmp/watcher-review-concentration.json"
    )


def test_load_config_uses_default_ollama_url(monkeypatch) -> None:
    _clear_env(monkeypatch)
    _set_required_env(monkeypatch)
    cfg = config.load_config()
    assert cfg.ollama_url == config.DEFAULT_OLLAMA_URL


def test_load_config_reads_custom_ollama_url(monkeypatch) -> None:
    _clear_env(monkeypatch)
    _set_required_env(monkeypatch)
    monkeypatch.setenv(config.OLLAMA_URL_ENV, "http://ollama:11434")
    cfg = config.load_config()
    assert cfg.ollama_url == "http://ollama:11434"
