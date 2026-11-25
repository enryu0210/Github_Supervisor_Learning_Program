from pathlib import Path

import httpx
import pytest

from watcher import github_client
from watcher.config import WatcherConfig


class _FakeResponse:
    def __init__(
        self,
        payload: dict,
        status_code: int = 200,
        links: dict | None = None,
    ) -> None:
        self._payload = payload
        self.status_code = status_code
        self.links = links or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=None, response=self)

    def json(self) -> dict:
        return self._payload


def _config() -> WatcherConfig:
    return WatcherConfig(
        token="secret-token",
        repo="owner/repo",
        poll_interval_seconds=300,
        review_concentration_path=Path("./review_concentration.json"),
        supabase_url="https://example.supabase.co",
        supabase_service_key="service-key",
    )


def test_get_sends_auth_header_and_base_url(monkeypatch) -> None:
    calls = []

    def fake_get(url, *, headers, timeout):
        calls.append((url, headers))
        return _FakeResponse({})

    monkeypatch.setattr(github_client._client, "get", fake_get)
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

    monkeypatch.setattr(github_client._client, "get", raise_error)
    with pytest.raises(github_client.GitHubClientError):
        github_client.get(_config(), "/repos/owner/repo")


def test_get_raises_on_http_status_error(monkeypatch) -> None:
    monkeypatch.setattr(
        github_client._client, "get", lambda *a, **k: _FakeResponse({}, status_code=404)
    )
    with pytest.raises(github_client.GitHubClientError):
        github_client.get(_config(), "/repos/owner/repo")


def test_get_repo_returns_parsed_json(monkeypatch) -> None:
    monkeypatch.setattr(
        github_client._client,
        "get",
        lambda *a, **k: _FakeResponse({"default_branch": "develop"}),
    )
    assert github_client.get_repo(_config()) == {"default_branch": "develop"}


def test_get_repo_raises_client_error_on_invalid_json(monkeypatch) -> None:
    class _BadJsonResponse(_FakeResponse):
        def json(self) -> dict:
            raise ValueError("not json")

    monkeypatch.setattr(
        github_client._client, "get", lambda *a, **k: _BadJsonResponse({})
    )
    with pytest.raises(github_client.GitHubClientError):
        github_client.get_repo(_config())


def test_list_events_calls_events_endpoint(monkeypatch) -> None:
    calls = []

    def fake_get(url, *, headers, timeout):
        calls.append(url)
        return _FakeResponse([{"type": "PushEvent"}])

    monkeypatch.setattr(github_client._client, "get", fake_get)
    result = github_client.list_events(_config())

    assert calls == ["https://api.github.com/repos/owner/repo/events"]
    assert result == [{"type": "PushEvent"}]


def test_compare_commits_calls_compare_endpoint(monkeypatch) -> None:
    calls = []

    def fake_get(url, *, headers, timeout):
        calls.append(url)
        return _FakeResponse({"status": "diverged"})

    monkeypatch.setattr(github_client._client, "get", fake_get)
    result = github_client.compare_commits(_config(), "abc111", "def222")

    assert calls == ["https://api.github.com/repos/owner/repo/compare/abc111...def222"]
    assert result == {"status": "diverged"}


def test_list_pulls_for_commit_calls_pulls_endpoint(monkeypatch) -> None:
    calls = []

    def fake_get(url, *, headers, timeout):
        calls.append(url)
        return _FakeResponse([{"number": 1}])

    monkeypatch.setattr(github_client._client, "get", fake_get)
    result = github_client.list_pulls_for_commit(_config(), "abc111")

    assert calls == ["https://api.github.com/repos/owner/repo/commits/abc111/pulls"]
    assert result == [{"number": 1}]


def test_list_open_pulls_calls_pulls_endpoint_with_state_open(monkeypatch) -> None:
    calls = []

    def fake_get(url, *, headers, timeout):
        calls.append(url)
        return _FakeResponse([{"number": 1}])

    monkeypatch.setattr(github_client._client, "get", fake_get)
    result = github_client.list_open_pulls(_config())

    assert calls == [
        (
            "https://api.github.com/repos/owner/repo/pulls"
            "?state=open&sort=updated&direction=desc&per_page=100"
        )
    ]
    assert result == [{"number": 1}]


def test_list_all_pulls_calls_pulls_endpoint_with_state_all(monkeypatch) -> None:
    calls = []

    def fake_get(url, *, headers, timeout):
        calls.append(url)
        return _FakeResponse([{"number": 1}])

    monkeypatch.setattr(github_client._client, "get", fake_get)
    result = github_client.list_all_pulls(_config())

    assert calls == [
        (
            "https://api.github.com/repos/owner/repo/pulls"
            "?state=all&sort=updated&direction=desc&per_page=100"
        )
    ]
    assert result == [{"number": 1}]


def test_list_all_pulls_follows_link_header_pagination(monkeypatch) -> None:
    calls = []
    next_url = (
        "https://api.github.com/repos/owner/repo/pulls"
        "?state=all&sort=updated&direction=desc&per_page=100&page=2"
    )

    def fake_get(url, *, headers, timeout):
        calls.append(url)
        if url == next_url:
            return _FakeResponse([{"number": 101}])
        return _FakeResponse([{"number": 1}], links={"next": {"url": next_url}})

    monkeypatch.setattr(github_client._client, "get", fake_get)
    result = github_client.list_all_pulls(_config())

    assert calls == [
        (
            "https://api.github.com/repos/owner/repo/pulls"
            "?state=all&sort=updated&direction=desc&per_page=100"
        ),
        next_url,
    ]
    assert result == [{"number": 1}, {"number": 101}]


def test_list_all_pulls_stops_when_no_next_link(monkeypatch) -> None:
    calls = []

    def fake_get(url, *, headers, timeout):
        calls.append(url)
        return _FakeResponse([{"number": 1}], links={})

    monkeypatch.setattr(github_client._client, "get", fake_get)
    result = github_client.list_all_pulls(_config())

    assert len(calls) == 1
    assert result == [{"number": 1}]


def test_list_branches_calls_branches_endpoint(monkeypatch) -> None:
    calls = []

    def fake_get(url, *, headers, timeout):
        calls.append(url)
        return _FakeResponse([{"name": "main"}])

    monkeypatch.setattr(github_client._client, "get", fake_get)
    result = github_client.list_branches(_config())

    assert calls == ["https://api.github.com/repos/owner/repo/branches"]
    assert result == [{"name": "main"}]


def test_list_pull_commits_calls_commits_endpoint(monkeypatch) -> None:
    calls = []

    def fake_get(url, *, headers, timeout):
        calls.append(url)
        return _FakeResponse([{"sha": "abc111"}])

    monkeypatch.setattr(github_client._client, "get", fake_get)
    result = github_client.list_pull_commits(_config(), 1)

    assert calls == ["https://api.github.com/repos/owner/repo/pulls/1/commits"]
    assert result == [{"sha": "abc111"}]


def test_get_commit_calls_commit_endpoint(monkeypatch) -> None:
    calls = []

    def fake_get(url, *, headers, timeout):
        calls.append(url)
        return _FakeResponse({"author": {"login": "someone"}})

    monkeypatch.setattr(github_client._client, "get", fake_get)
    result = github_client.get_commit(_config(), "abc111")

    assert calls == ["https://api.github.com/repos/owner/repo/commits/abc111"]
    assert result == {"author": {"login": "someone"}}


def test_list_pull_reviews_calls_reviews_endpoint(monkeypatch) -> None:
    calls = []

    def fake_get(url, *, headers, timeout):
        calls.append(url)
        return _FakeResponse([{"user": {"login": "someone"}, "state": "APPROVED"}])

    monkeypatch.setattr(github_client._client, "get", fake_get)
    result = github_client.list_pull_reviews(_config(), 1)

    assert calls == ["https://api.github.com/repos/owner/repo/pulls/1/reviews"]
    assert result == [{"user": {"login": "someone"}, "state": "APPROVED"}]
