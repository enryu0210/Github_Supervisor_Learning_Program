import httpx
import pytest

from watcher import github_client
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


def _config() -> WatcherConfig:
    return WatcherConfig(
        token="secret-token", repo="owner/repo", poll_interval_seconds=300
    )


def test_get_sends_auth_header_and_base_url(monkeypatch) -> None:
    calls = []

    def fake_get(url, *, headers, timeout):
        calls.append((url, headers))
        return _FakeResponse({})

    monkeypatch.setattr(httpx, "get", fake_get)
    github_client.get(_config(), "/repos/owner/repo")

    assert calls == [
        (
            "https://api.github.com/repos/owner/repo",
            {
                "Authorization": "Bearer secret-token",
                "Accept": "application/vnd.github+json",
            },
        )
    ]


def test_get_raises_on_http_error(monkeypatch) -> None:
    def raise_error(*a, **k):
        raise httpx.ConnectError("no network")

    monkeypatch.setattr(httpx, "get", raise_error)
    with pytest.raises(github_client.GitHubClientError):
        github_client.get(_config(), "/repos/owner/repo")


def test_get_raises_on_http_status_error(monkeypatch) -> None:
    monkeypatch.setattr(
        httpx, "get", lambda *a, **k: _FakeResponse({}, status_code=404)
    )
    with pytest.raises(github_client.GitHubClientError):
        github_client.get(_config(), "/repos/owner/repo")


def test_get_repo_returns_parsed_json(monkeypatch) -> None:
    monkeypatch.setattr(
        httpx, "get", lambda *a, **k: _FakeResponse({"default_branch": "develop"})
    )
    assert github_client.get_repo(_config()) == {"default_branch": "develop"}
