import subprocess

import httpx
import pytest

from gitcoach import config, events, sync


def _init_repo(remote: str = "https://github.com/team/repo.git") -> None:
    subprocess.run(["git", "init", "-b", "main"], check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], check=True)
    subprocess.run(["git", "config", "user.name", "T User"], check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], check=True)
    subprocess.run(["git", "remote", "add", "origin", remote], check=True)


def _setup(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    monkeypatch.setattr(events, "DB_PATH", tmp_path / "events.db")
    monkeypatch.setattr(config, "GLOBAL_CONFIG_PATH", tmp_path / "config.toml")
    monkeypatch.setenv(sync.SYNC_URL_ENV, "https://edge.example/ingest-events")
    monkeypatch.setenv(sync.SYNC_TOKEN_ENV, "team-token")


def _record_events(n: int, prefix: str = "cmd") -> list[str]:
    ids = []
    for i in range(n):
        ev = events.make_event(
            rule_id="R01",
            severity="high",
            branch="main",
            action="allowed",
            command_summary=f"{prefix}{i}",
        )
        events.record(ev)
        ids.append(ev.id)
    return ids


def test_push_events_raises_without_env_vars(tmp_path, monkeypatch) -> None:
    _setup(tmp_path, monkeypatch)
    monkeypatch.delenv(sync.SYNC_URL_ENV, raising=False)
    with pytest.raises(sync.SyncError):
        sync.push_events()


def test_push_events_raises_without_token(tmp_path, monkeypatch) -> None:
    _setup(tmp_path, monkeypatch)
    monkeypatch.delenv(sync.SYNC_TOKEN_ENV, raising=False)
    with pytest.raises(sync.SyncError):
        sync.push_events()


def test_push_events_sends_auth_header_and_url(tmp_path, monkeypatch) -> None:
    _setup(tmp_path, monkeypatch)
    ids = _record_events(1)
    calls = []

    def fake_post(url, *, json, headers, timeout):
        calls.append((url, headers))
        return _FakeResponse({"results": [{"id": ids[0], "status": "inserted"}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    sync.push_events()
    assert calls == [
        ("https://edge.example/ingest-events", {"Authorization": "Bearer team-token"})
    ]


def test_push_events_request_body_contains_event_fields(tmp_path, monkeypatch) -> None:
    _setup(tmp_path, monkeypatch)
    ids = _record_events(1)
    bodies = []

    def fake_post(url, *, json, headers, timeout):
        bodies.append(json)
        return _FakeResponse({"results": [{"id": ids[0], "status": "inserted"}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    sync.push_events()
    assert len(bodies) == 1
    sent = bodies[0]["events"][0]
    assert sent["id"] == ids[0]
    assert sent["command_summary"] == "cmd0"
    assert sent["rule_id"] == "R01"


def test_push_events_marks_inserted_and_duplicate_as_synced(
    tmp_path, monkeypatch
) -> None:
    _setup(tmp_path, monkeypatch)
    ids = _record_events(2)

    def fake_post(url, *, json, headers, timeout):
        return _FakeResponse(
            {
                "results": [
                    {"id": ids[0], "status": "inserted"},
                    {"id": ids[1], "status": "duplicate"},
                ]
            }
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    result = sync.push_events()
    assert result.inserted == 1
    assert result.duplicate == 1
    assert result.rejected == []
    assert events.unsynced() == []


def test_push_events_keeps_rejected_as_unsynced(tmp_path, monkeypatch) -> None:
    _setup(tmp_path, monkeypatch)
    ids = _record_events(1)

    def fake_post(url, *, json, headers, timeout):
        return _FakeResponse(
            {"results": [{"id": ids[0], "status": "rejected", "reason": "형식 오류"}]}
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    result = sync.push_events()
    assert result.inserted == 0
    assert result.rejected == [(ids[0], "형식 오류")]
    # 거절된 이벤트는 synced 처리되지 않아 다음 sync에서 다시 시도된다
    assert len(events.unsynced()) == 1


def test_push_events_stops_when_batch_makes_no_progress(tmp_path, monkeypatch) -> None:
    # 전부 rejected라 synced 처리된 게 없으면 같은 배치를 무한 재요청하지 않고 멈춘다
    _setup(tmp_path, monkeypatch)
    _record_events(1)
    call_count = 0

    def fake_post(url, *, json, headers, timeout):
        nonlocal call_count
        call_count += 1
        ids_in_batch = [e["id"] for e in json["events"]]
        return _FakeResponse(
            {
                "results": [
                    {"id": i, "status": "rejected", "reason": "x"} for i in ids_in_batch
                ]
            }
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    sync.push_events()
    assert call_count == 1


def test_push_events_processes_multiple_batches(tmp_path, monkeypatch) -> None:
    _setup(tmp_path, monkeypatch)
    _record_events(sync.BATCH_SIZE + 5)
    call_count = 0

    def fake_post(url, *, json, headers, timeout):
        nonlocal call_count
        call_count += 1
        ids_in_batch = [e["id"] for e in json["events"]]
        return _FakeResponse(
            {"results": [{"id": i, "status": "inserted"} for i in ids_in_batch]}
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    result = sync.push_events()
    assert call_count == 2
    assert result.inserted == sync.BATCH_SIZE + 5
    assert events.unsynced() == []


def test_push_events_raises_on_http_error(tmp_path, monkeypatch) -> None:
    _setup(tmp_path, monkeypatch)
    _record_events(1)

    def fake_post(url, *, json, headers, timeout):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(sync.SyncError):
        sync.push_events()


class _FakeResponse:
    def __init__(self, body: dict, status_code: int = 200) -> None:
        self._body = body
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=None, response=self)

    def json(self) -> dict:
        return self._body
