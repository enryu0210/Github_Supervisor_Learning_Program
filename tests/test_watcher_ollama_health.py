from pathlib import Path

import httpx

from watcher import ollama_health
from watcher.config import WatcherConfig


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=None, response=self)

    def json(self) -> dict:
        return self._payload


def _config(ollama_url: str = "http://ollama:11434") -> WatcherConfig:
    return WatcherConfig(
        token="secret-token",
        repo="owner/repo",
        poll_interval_seconds=300,
        review_concentration_path=Path("./review_concentration.json"),
        supabase_url="https://example.supabase.co",
        supabase_service_key="service-key",
        ollama_url=ollama_url,
    )


def test_check_reports_success_with_models(monkeypatch) -> None:
    def fake_get(url, *, timeout):
        assert url == "http://ollama:11434/api/tags"
        return _FakeResponse({"models": [{"name": "gemma4:e2b"}]})

    monkeypatch.setattr(httpx, "get", fake_get)
    ok, message = ollama_health.check(_config())

    assert ok is True
    assert "gemma4:e2b" in message


def test_check_reports_success_without_models(monkeypatch) -> None:
    monkeypatch.setattr(httpx, "get", lambda url, *, timeout: _FakeResponse({}))
    ok, message = ollama_health.check(_config())

    assert ok is True
    assert "없음" in message


def test_check_reports_failure_on_http_error(monkeypatch) -> None:
    def fake_get(url, *, timeout):
        return _FakeResponse({}, status_code=500)

    monkeypatch.setattr(httpx, "get", fake_get)
    ok, message = ollama_health.check(_config())

    assert ok is False
    assert "http://ollama:11434" in message


def test_check_reports_failure_on_connect_error(monkeypatch) -> None:
    def fake_get(url, *, timeout):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "get", fake_get)
    ok, _message = ollama_health.check(_config())

    assert ok is False
