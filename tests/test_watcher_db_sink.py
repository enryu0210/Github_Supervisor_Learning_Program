import logging
from pathlib import Path

import pytest
from postgrest.exceptions import APIError

from gitcoach.models import Event
from watcher import db_sink
from watcher.config import WatcherConfig, WatcherConfigError


class _FakeResult:
    def __init__(self, data) -> None:
        self.data = data


class _FakeTable:
    def __init__(self, client: "_FakeClient", name: str) -> None:
        self._client = client
        self._name = name
        self._op = None
        self._filters: dict = {}
        self._rows = None
        self._on_conflict = None

    def select(self, *_columns) -> "_FakeTable":
        self._op = "select"
        return self

    def eq(self, column: str, value) -> "_FakeTable":
        self._filters[column] = value
        return self

    def limit(self, _n: int) -> "_FakeTable":
        return self

    def upsert(self, rows, *, on_conflict=None, ignore_duplicates=None) -> "_FakeTable":
        self._op = "upsert"
        self._rows = rows
        self._on_conflict = on_conflict
        self._ignore_duplicates = ignore_duplicates
        return self

    def execute(self) -> _FakeResult:
        self._client.calls.append(
            {
                "table": self._name,
                "op": self._op,
                "filters": dict(self._filters),
                "rows": self._rows,
                "on_conflict": self._on_conflict,
                "ignore_duplicates": getattr(self, "_ignore_duplicates", None),
            }
        )
        response = self._client.responses[self._name].pop(0)
        if isinstance(response, Exception):
            raise response
        return _FakeResult(response)


class _FakeClient:
    def __init__(self, responses: dict[str, list]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    def table(self, name: str) -> _FakeTable:
        return _FakeTable(self, name)


def _config() -> WatcherConfig:
    return WatcherConfig(
        token="secret-token",
        repo="owner/repo",
        poll_interval_seconds=300,
        review_concentration_path=Path("./review_concentration.json"),
        supabase_url="https://example.supabase.co",
        supabase_service_key="service-key",
    )


def _event(*, member: str = "hoil-lim", rule_id: str = "R01") -> Event:
    return Event(
        id=f"11111111-1111-1111-1111-{rule_id.lower():0>12}",
        schema_version=1,
        occurred_at="2026-11-16T00:00:00+09:00",
        source="github",
        repo="owner/repo",
        member=member,
        rule_id=rule_id,
        severity="high",
        action="detected",
        command_summary=None,
        branch="main",
        explanation="테스트용 감지 이벤트",
    )


def test_create_client_from_config_passes_url_and_service_key(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        db_sink, "create_client", lambda url, key: calls.append((url, key)) or "client"
    )

    result = db_sink.create_client_from_config(_config())

    assert calls == [("https://example.supabase.co", "service-key")]
    assert result == "client"


def test_resolve_repo_id_returns_id_when_found() -> None:
    client = _FakeClient({"repos": [[{"id": "repo-uuid"}]]})

    repo_id = db_sink.resolve_repo_id(client, "owner/repo")

    assert repo_id == "repo-uuid"
    assert client.calls[0]["filters"] == {"full_name": "owner/repo"}


def test_resolve_repo_id_lowercases_repo_full_name_before_query() -> None:
    client = _FakeClient({"repos": [[{"id": "repo-uuid"}]]})

    repo_id = db_sink.resolve_repo_id(
        client, "Enryu0210/Github_Supervisor_Learning_Program"
    )

    assert repo_id == "repo-uuid"
    assert client.calls[0]["filters"] == {
        "full_name": "enryu0210/github_supervisor_learning_program"
    }


def test_resolve_repo_id_raises_when_repo_not_seeded() -> None:
    client = _FakeClient({"repos": [[]]})

    with pytest.raises(WatcherConfigError):
        db_sink.resolve_repo_id(client, "owner/repo")


def test_resolve_repo_id_raises_watcher_config_error_on_api_error() -> None:
    client = _FakeClient({"repos": [APIError({"message": "boom"})]})

    with pytest.raises(WatcherConfigError):
        db_sink.resolve_repo_id(client, "owner/repo")


def test_upload_events_upserts_rows_with_do_nothing_semantics() -> None:
    client = _FakeClient({"events": [None]})
    events = [_event(rule_id="R01"), _event(rule_id="R05")]

    db_sink.upload_events(client, events)

    call = client.calls[0]
    assert call["table"] == "events"
    assert call["op"] == "upsert"
    assert call["on_conflict"] == "id"
    assert call["ignore_duplicates"] is True
    assert [row["rule_id"] for row in call["rows"]] == ["R01", "R05"]


def test_upload_events_drops_bot_accounts(caplog) -> None:
    client = _FakeClient({"events": [None]})
    events = [_event(member="github-actions[bot]"), _event(member="hoil-lim")]

    with caplog.at_level(logging.WARNING, logger="watcher"):
        db_sink.upload_events(client, events)

    call = client.calls[0]
    assert [row["member"] for row in call["rows"]] == ["hoil-lim"]
    assert "github-actions[bot]" in caplog.text


def test_upload_events_skips_upload_when_all_events_are_bots() -> None:
    client = _FakeClient({"events": []})

    db_sink.upload_events(client, [_event(member="github-actions[bot]")])

    assert client.calls == []


def test_upload_events_raises_db_sink_error_on_api_error() -> None:
    client = _FakeClient({"events": [APIError({"message": "boom"})]})

    with pytest.raises(db_sink.DbSinkError):
        db_sink.upload_events(client, [_event()])


def test_upload_prs_returns_empty_map_without_calling_client() -> None:
    client = _FakeClient({})

    result = db_sink.upload_prs(client, "repo-uuid", [])

    assert result == {}
    assert client.calls == []


def test_upload_prs_replaces_repo_with_repo_id_and_returns_number_to_id_map() -> None:
    client = _FakeClient({"prs": [[{"number": 1, "id": "pr-uuid"}]]})
    pr_record = {
        "repo": "owner/repo",
        "number": 1,
        "title": "feat: x",
        "author": "hoil-lim",
        "state": "open",
        "opened_at": "2026-11-10T09:12:00Z",
        "merged_at": None,
        "reviewers": [],
        "last_activity_at": "2026-11-10T09:12:00Z",
    }

    result = db_sink.upload_prs(client, "repo-uuid", [pr_record])

    call = client.calls[0]
    assert call["on_conflict"] == "repo_id,number"
    assert call["rows"][0]["repo_id"] == "repo-uuid"
    assert "repo" not in call["rows"][0]
    assert result == {1: "pr-uuid"}


def test_upload_prs_raises_db_sink_error_on_api_error() -> None:
    client = _FakeClient({"prs": [APIError({"message": "boom"})]})

    with pytest.raises(db_sink.DbSinkError):
        db_sink.upload_prs(client, "repo-uuid", [{"repo": "owner/repo", "number": 1}])


def _review_record(*, review_id: int = 1, pr_number: int = 1) -> dict:
    return {
        "review_id": review_id,
        "repo": "owner/repo",
        "pr_number": pr_number,
        "reviewer": "hoil-lim",
        "status": "APPROVED",
        "submitted_at": "2026-11-16T00:00:00Z",
        "commit_sha": "a" * 40,
        "html_url": "https://github.com/owner/repo/pull/1#pullrequestreview-1",
    }


def test_upload_pr_reviews_skips_upload_when_no_records() -> None:
    client = _FakeClient({})

    db_sink.upload_pr_reviews(client, "repo-uuid", {}, [])

    assert client.calls == []


def test_upload_pr_reviews_resolves_pr_id_from_map() -> None:
    client = _FakeClient({"pr_reviews": [None]})

    db_sink.upload_pr_reviews(client, "repo-uuid", {1: "pr-uuid"}, [_review_record()])

    call = client.calls[0]
    assert call["table"] == "pr_reviews"
    assert call["on_conflict"] == "review_id"
    assert call["rows"] == [
        {
            "review_id": 1,
            "pr_id": "pr-uuid",
            "reviewer": "hoil-lim",
            "status": "APPROVED",
            "submitted_at": "2026-11-16T00:00:00Z",
            "commit_sha": "a" * 40,
            "html_url": "https://github.com/owner/repo/pull/1#pullrequestreview-1",
        }
    ]


def test_upload_pr_reviews_falls_back_to_lookup_when_pr_id_missing_from_map() -> None:
    client = _FakeClient({"prs": [[{"id": "pr-uuid"}]], "pr_reviews": [None]})

    db_sink.upload_pr_reviews(client, "repo-uuid", {}, [_review_record(pr_number=7)])

    lookup_call, upsert_call = client.calls
    assert lookup_call["table"] == "prs"
    assert lookup_call["filters"] == {"repo_id": "repo-uuid", "number": 7}
    assert upsert_call["rows"][0]["pr_id"] == "pr-uuid"


def test_upload_pr_reviews_skips_review_when_pr_id_cannot_be_resolved(caplog) -> None:
    client = _FakeClient({"prs": [[]]})

    with caplog.at_level(logging.WARNING, logger="watcher"):
        db_sink.upload_pr_reviews(
            client, "repo-uuid", {}, [_review_record(pr_number=9)]
        )

    assert len(client.calls) == 1
    assert "9" in caplog.text


def test_upload_pr_reviews_raises_db_sink_error_on_upsert_api_error() -> None:
    client = _FakeClient({"pr_reviews": [APIError({"message": "boom"})]})

    with pytest.raises(db_sink.DbSinkError):
        db_sink.upload_pr_reviews(
            client, "repo-uuid", {1: "pr-uuid"}, [_review_record()]
        )


def test_upload_pr_reviews_raises_db_sink_error_on_lookup_api_error() -> None:
    client = _FakeClient({"prs": [APIError({"message": "boom"})]})

    with pytest.raises(db_sink.DbSinkError):
        db_sink.upload_pr_reviews(
            client, "repo-uuid", {}, [_review_record(pr_number=9)]
        )
