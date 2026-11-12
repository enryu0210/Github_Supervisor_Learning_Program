import sqlite3
import subprocess

import httpx
import pytest

from gitcoach import config, events, sync


def _synced_flag(event_id: str) -> int:
    conn = sqlite3.connect(events.DB_PATH)
    try:
        return conn.execute(
            "SELECT synced FROM events WHERE id = ?", (event_id,)
        ).fetchone()[0]
    finally:
        conn.close()


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


def test_push_events_excludes_rejected_from_future_unsynced(
    tmp_path, monkeypatch
) -> None:
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
    # 거절된 이벤트를 synced=0으로 남기면 다음 sync에서 계속 같은 배치 앞자리를
    # 차지해 그 뒤 정상 이벤트가 전송되지 못한다 — 영구 제외해야 한다.
    assert events.unsynced() == []


def test_push_events_old_rejected_does_not_block_newer_events(
    tmp_path, monkeypatch
) -> None:
    # 리뷰에서 재현된 시나리오: 거절 100건(오래됨) 뒤에 쌓인 정상 건이
    # 영원히 전송되지 않던 문제
    _setup(tmp_path, monkeypatch)
    rejected_ids = set(_record_events(sync.BATCH_SIZE, prefix="bad"))
    good_ids = _record_events(5, prefix="good")

    def fake_post(url, *, json, headers, timeout):
        results = [
            {"id": e["id"], "status": "rejected", "reason": "형식 오류"}
            if e["id"] in rejected_ids
            else {"id": e["id"], "status": "inserted"}
            for e in json["events"]
        ]
        return _FakeResponse({"results": results})

    monkeypatch.setattr(httpx, "post", fake_post)
    result = sync.push_events()
    assert result.inserted == 5
    assert {i for i, _ in result.rejected} == rejected_ids
    assert good_ids  # sanity: 정상 건이 실제로 기록됐는지 확인
    assert events.unsynced() == []
    # 다시 실행해도 이미 영구 제외된 거절 건이 재집계되지 않는다
    result2 = sync.push_events()
    assert result2.rejected == []
    assert result2.inserted == 0


def test_push_events_does_not_recount_same_rejected_id_across_batches(
    tmp_path, monkeypatch
) -> None:
    # 거절 1건 + 정상 다건을 여러 배치로 처리할 때, 같은 거절 id가 배치마다
    # 다시 조회되어 result.rejected에 중복으로 쌓이면 안 된다
    _setup(tmp_path, monkeypatch)
    bad_id = _record_events(1, prefix="bad")[0]
    _record_events(sync.BATCH_SIZE + 5, prefix="good")

    def fake_post(url, *, json, headers, timeout):
        results = [
            {"id": e["id"], "status": "rejected", "reason": "형식 오류"}
            if e["id"] == bad_id
            else {"id": e["id"], "status": "inserted"}
            for e in json["events"]
        ]
        return _FakeResponse({"results": results})

    monkeypatch.setattr(httpx, "post", fake_post)
    result = sync.push_events()
    assert result.rejected == [(bad_id, "형식 오류")]
    assert result.inserted == sync.BATCH_SIZE + 5


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


def test_push_events_raises_sync_error_on_malformed_response(
    tmp_path, monkeypatch
) -> None:
    _setup(tmp_path, monkeypatch)
    _record_events(1)

    def fake_post(url, *, json, headers, timeout):
        # "status" 필드가 없는 등 가정과 다른 응답 — KeyError가 traceback으로
        # 새지 않고 SyncError로 바뀌어야 한다
        return _FakeResponse({"results": [{"id": "x"}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(sync.SyncError):
        sync.push_events()


def test_push_events_does_not_upload_pending_guided_event(
    tmp_path, monkeypatch
) -> None:
    # 큐에서 아직 시작 안 한 guided(explanation=None, 결과 이벤트 없음)는
    # 서버 적재가 on conflict do nothing이라 올리면 영원히 고쳐지지 않는다(#48)
    _setup(tmp_path, monkeypatch)
    pending = events.make_event(
        rule_id="R01",
        severity="high",
        branch="main",
        action="guided",
        command_summary="x",
    )
    events.record(pending)
    calls = []

    def fake_post(url, *, json, headers, timeout):
        calls.append(json)
        raise AssertionError("보류 대상만 있을 때는 sync가 요청을 보내면 안 된다")

    monkeypatch.setattr(httpx, "post", fake_post)
    result = sync.push_events()
    assert calls == []
    assert result.inserted == 0
    assert result.duplicate == 0
    assert _synced_flag(pending.id) == 0


def test_push_events_uploads_guided_event_once_explanation_backfilled(
    tmp_path, monkeypatch
) -> None:
    _setup(tmp_path, monkeypatch)
    ev = events.make_event(
        rule_id="R01",
        severity="high",
        branch="main",
        action="guided",
        command_summary="x",
    )
    events.record(ev)
    events.update_explanation(ev.id, "설명", False)

    def fake_post(url, *, json, headers, timeout):
        return _FakeResponse({"results": [{"id": ev.id, "status": "inserted"}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    result = sync.push_events()
    assert result.inserted == 1
    assert events.unsynced() == []


def test_push_events_uploads_guided_event_once_terminal_event_recorded(
    tmp_path, monkeypatch
) -> None:
    _setup(tmp_path, monkeypatch)
    ev = events.make_event(
        rule_id="R01",
        severity="high",
        branch="main",
        action="guided",
        command_summary="x",
    )
    events.record(ev)
    followup = events.make_event(
        rule_id="R01",
        severity="high",
        branch="main",
        action="guide_stopped",
        command_summary="x",
        related_event_id=ev.id,
    )
    events.record(followup)

    def fake_post(url, *, json, headers, timeout):
        sent_ids = {e["id"] for e in json["events"]}
        assert sent_ids == {ev.id, followup.id}
        return _FakeResponse(
            {
                "results": [
                    {"id": ev.id, "status": "inserted"},
                    {"id": followup.id, "status": "inserted"},
                ]
            }
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    result = sync.push_events()
    assert result.inserted == 2
    assert events.unsynced() == []


def test_push_events_batch_includes_eligible_events_even_with_pending_one_present(
    tmp_path, monkeypatch
) -> None:
    _setup(tmp_path, monkeypatch)
    pending = events.make_event(
        rule_id="R01",
        severity="high",
        branch="main",
        action="guided",
        command_summary="x",
    )
    events.record(pending)
    good_ids = _record_events(3, prefix="good")

    def fake_post(url, *, json, headers, timeout):
        ids_in_batch = [e["id"] for e in json["events"]]
        assert pending.id not in ids_in_batch
        return _FakeResponse(
            {"results": [{"id": i, "status": "inserted"} for i in ids_in_batch]}
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    result = sync.push_events()
    assert result.inserted == len(good_ids)
    assert _synced_flag(pending.id) == 0


class _FakeResponse:
    def __init__(self, body: dict, status_code: int = 200) -> None:
        self._body = body
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=None, response=self)

    def json(self) -> dict:
        return self._body
