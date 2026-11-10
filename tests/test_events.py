import subprocess

from gitcoach import events


def _init_repo(remote: str = "https://github.com/team/repo.git") -> None:
    subprocess.run(["git", "init", "-b", "main"], check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], check=True)
    subprocess.run(["git", "config", "user.name", "T User"], check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], check=True)
    subprocess.run(["git", "remote", "add", "origin", remote], check=True)


def _use_tmp_db(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(events, "DB_PATH", tmp_path / "events.db")


def test_make_event_fills_all_fields(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
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


def test_query_filters_by_repo(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(remote="https://github.com/team/repo-a.git")
    _use_tmp_db(tmp_path, monkeypatch)
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
