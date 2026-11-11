import sqlite3
import subprocess

from gitcoach import config, events


def _init_repo(remote: str = "https://github.com/team/repo.git") -> None:
    subprocess.run(["git", "init", "-b", "main"], check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], check=True)
    subprocess.run(["git", "config", "user.name", "T User"], check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], check=True)
    subprocess.run(["git", "remote", "add", "origin", remote], check=True)


def _use_tmp_db(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(events, "DB_PATH", tmp_path / "events.db")


def _use_tmp_global_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "GLOBAL_CONFIG_PATH", tmp_path / "config.toml")


def test_make_event_fills_all_fields(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    _use_tmp_global_config(tmp_path, monkeypatch)
    ev = events.make_event(
        rule_id="R01",
        severity="high",
        branch="main",
        action="allowed",
        command_summary="git push origin main",
    )
    assert ev.id
    assert ev.schema_version == 1
    assert ev.occurred_at
    assert ev.source == "cli"
    assert ev.repo == "team/repo"
    assert ev.member == "tuser"
    assert ev.rule_id == "R01"
    assert ev.action == "allowed"
    assert ev.related_event_id is None


def test_record_then_query_roundtrips(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    _use_tmp_db(tmp_path, monkeypatch)
    _use_tmp_global_config(tmp_path, monkeypatch)
    ev = events.make_event(
        rule_id="R01",
        severity="high",
        branch="main",
        action="allowed",
        command_summary="git push origin main",
    )
    events.record(ev)
    rows = events.query()
    assert len(rows) == 1
    assert rows[0].id == ev.id
    assert rows[0].command_summary == "git push origin main"


def test_record_same_id_twice_is_safe(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    _use_tmp_db(tmp_path, monkeypatch)
    _use_tmp_global_config(tmp_path, monkeypatch)
    ev = events.make_event(
        rule_id="R01",
        severity="high",
        branch="main",
        action="allowed",
        command_summary="git push origin main",
    )
    events.record(ev)
    events.record(ev)
    assert len(events.query()) == 1


def test_query_today_filters_other_dates(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    _use_tmp_db(tmp_path, monkeypatch)
    _use_tmp_global_config(tmp_path, monkeypatch)
    ev = events.make_event(
        rule_id="R01",
        severity="high",
        branch="main",
        action="allowed",
        command_summary="git push origin main",
    )
    ev.occurred_at = "2020-01-01T00:00:00+09:00"
    events.record(ev)
    assert events.query(today=True) == []
    assert len(events.query(today=False)) == 1


def test_make_event_uses_config_member_when_set(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    _use_tmp_global_config(tmp_path, monkeypatch)
    (tmp_path / "config.toml").write_text('member = "octocat"')

    ev = events.make_event(
        rule_id="R01",
        severity="high",
        branch="main",
        action="allowed",
        command_summary="git push origin main",
    )
    assert ev.member == "octocat"


def test_query_filters_by_repo(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(remote="https://github.com/team/repo-a.git")
    _use_tmp_db(tmp_path, monkeypatch)
    _use_tmp_global_config(tmp_path, monkeypatch)
    events.record(
        events.make_event(
            rule_id="R01",
            severity="high",
            branch="main",
            action="allowed",
            command_summary="git push origin main",
        )
    )

    other_repo = tmp_path / "other"
    other_repo.mkdir()
    monkeypatch.chdir(other_repo)
    _init_repo(remote="https://github.com/team/repo-b.git")
    assert events.query() == []


def test_unsynced_returns_events_across_repos(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(remote="https://github.com/team/repo-a.git")
    _use_tmp_db(tmp_path, monkeypatch)
    _use_tmp_global_config(tmp_path, monkeypatch)
    ev1 = events.make_event(
        rule_id="R01",
        severity="high",
        branch="main",
        action="allowed",
        command_summary="a",
    )
    events.record(ev1)

    other_repo = tmp_path / "other"
    other_repo.mkdir()
    monkeypatch.chdir(other_repo)
    _init_repo(remote="https://github.com/team/repo-b.git")
    ev2 = events.make_event(
        rule_id="R02",
        severity="high",
        branch="main",
        action="allowed",
        command_summary="b",
    )
    events.record(ev2)

    # unsynced()는 query()와 달리 레포로 거르지 않는다 — 다른 레포 이벤트도 함께 나와야 함
    assert {e.id for e in events.unsynced()} == {ev1.id, ev2.id}


def test_unsynced_respects_limit(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    _use_tmp_db(tmp_path, monkeypatch)
    _use_tmp_global_config(tmp_path, monkeypatch)
    for i in range(3):
        events.record(
            events.make_event(
                rule_id="R01",
                severity="high",
                branch="main",
                action="allowed",
                command_summary=f"cmd{i}",
            )
        )
    assert len(events.unsynced(limit=2)) == 2


def test_mark_synced_excludes_from_unsynced(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    _use_tmp_db(tmp_path, monkeypatch)
    _use_tmp_global_config(tmp_path, monkeypatch)
    ev = events.make_event(
        rule_id="R01",
        severity="high",
        branch="main",
        action="allowed",
        command_summary="x",
    )
    events.record(ev)
    assert len(events.unsynced()) == 1
    events.mark_synced([ev.id])
    assert events.unsynced() == []


def test_mark_synced_does_not_change_query_output(tmp_path, monkeypatch) -> None:
    # synced는 로컬 전송 상태일 뿐 스키마 v1 필드가 아니라 query()/log 출력엔 안 보여야 함
    monkeypatch.chdir(tmp_path)
    _init_repo()
    _use_tmp_db(tmp_path, monkeypatch)
    _use_tmp_global_config(tmp_path, monkeypatch)
    ev = events.make_event(
        rule_id="R01",
        severity="high",
        branch="main",
        action="allowed",
        command_summary="x",
    )
    events.record(ev)
    events.mark_synced([ev.id])
    rows = events.query()
    assert len(rows) == 1
    assert rows[0].id == ev.id


def test_mark_rejected_excludes_from_unsynced(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    _use_tmp_db(tmp_path, monkeypatch)
    _use_tmp_global_config(tmp_path, monkeypatch)
    ev = events.make_event(
        rule_id="R01",
        severity="high",
        branch="main",
        action="allowed",
        command_summary="x",
    )
    events.record(ev)
    assert len(events.unsynced()) == 1
    events.mark_rejected([ev.id])
    # 거절된 이벤트는 재전송 대상이 아니라 synced처럼 unsynced()에서 빠져야 한다
    # (synced=0으로 남으면 매번 배치 앞자리를 차지해 그 뒤 이벤트가 막힌다)
    assert events.unsynced() == []


def test_mark_rejected_does_not_change_query_output(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    _use_tmp_db(tmp_path, monkeypatch)
    _use_tmp_global_config(tmp_path, monkeypatch)
    ev = events.make_event(
        rule_id="R01",
        severity="high",
        branch="main",
        action="allowed",
        command_summary="x",
    )
    events.record(ev)
    events.mark_rejected([ev.id])
    rows = events.query()
    assert len(rows) == 1
    assert rows[0].id == ev.id


def test_member_is_lowercased_even_if_config_has_mixed_case(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    _use_tmp_global_config(tmp_path, monkeypatch)
    (tmp_path / "config.toml").write_text('member = "LeafBell-SII"')

    ev = events.make_event(
        rule_id="R01",
        severity="high",
        branch="main",
        action="allowed",
        command_summary="x",
    )
    assert ev.member == "leafbell-sii"


def test_repo_prefers_upstream_remote_over_origin(tmp_path, monkeypatch) -> None:
    # fork+PR 워크플로에서 origin은 각자의 fork라, 팀 공용 레포 이름은
    # upstream에서 읽어야 한다(아니면 매 팀원의 이벤트에 fork 이름이 찍힌다)
    monkeypatch.chdir(tmp_path)
    _init_repo(remote="https://github.com/my-fork/repo.git")
    subprocess.run(
        ["git", "remote", "add", "upstream", "https://github.com/team/repo.git"],
        check=True,
    )
    _use_tmp_global_config(tmp_path, monkeypatch)

    ev = events.make_event(
        rule_id="R01",
        severity="high",
        branch="main",
        action="allowed",
        command_summary="x",
    )
    assert ev.repo == "team/repo"


def test_repo_falls_back_to_origin_without_upstream(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(remote="https://github.com/team/repo.git")
    _use_tmp_global_config(tmp_path, monkeypatch)

    ev = events.make_event(
        rule_id="R01",
        severity="high",
        branch="main",
        action="allowed",
        command_summary="x",
    )
    assert ev.repo == "team/repo"


def test_migration_adds_synced_column_to_pre_existing_db(tmp_path, monkeypatch) -> None:
    # cli-sync 이전 버전으로 만들어진(synced 컬럼 없는) DB를 열어도 깨지지 않아야 한다
    monkeypatch.chdir(tmp_path)
    _init_repo()
    db_path = tmp_path / "events.db"
    monkeypatch.setattr(events, "DB_PATH", db_path)
    _use_tmp_global_config(tmp_path, monkeypatch)

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE events (
            id TEXT PRIMARY KEY,
            schema_version INTEGER NOT NULL,
            occurred_at TEXT NOT NULL,
            source TEXT NOT NULL,
            repo TEXT NOT NULL,
            member TEXT NOT NULL,
            rule_id TEXT NOT NULL,
            severity TEXT NOT NULL,
            action TEXT NOT NULL,
            command_summary TEXT NOT NULL,
            branch TEXT NOT NULL,
            pr_number INTEGER,
            explanation TEXT,
            llm_used INTEGER NOT NULL,
            related_event_id TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO events VALUES "
        "('old-id', 1, '2020-01-01T00:00:00+09:00', 'cli', 'team/repo', "
        "'octocat', 'R01', 'high', 'allowed', 'git push', 'main', "
        "NULL, NULL, 0, NULL)"
    )
    conn.commit()
    conn.close()

    pending = events.unsynced()
    assert len(pending) == 1
    assert pending[0].id == "old-id"
