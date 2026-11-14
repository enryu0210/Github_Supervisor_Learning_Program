import re
import sqlite3
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from gitcoach import config
from gitcoach.models import Event

DB_PATH = Path.home() / ".gitcoach" / "events.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
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
    related_event_id TEXT,
    synced INTEGER NOT NULL DEFAULT 0
)
"""


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(_SCHEMA)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(events)")}
    if "synced" not in columns:
        conn.execute("ALTER TABLE events ADD COLUMN synced INTEGER NOT NULL DEFAULT 0")


def make_event(
    *,
    rule_id: str,
    severity: str,
    branch: str,
    action: str,
    command_summary: str,
    pr_number: int | None = None,
    explanation: str | None = None,
    llm_used: bool = False,
    related_event_id: str | None = None,
    repo: str | None = None,
    member: str | None = None,
) -> Event:
    """`repo`·`member`를 지정하면 그 값을 그대로 쓴다(가이드 결과 이벤트가 원래
    `guided` 스냅샷 값을 복사할 때 씀). 지정하지 않으면 현재 context에서 다시
    계산한다 — 가이드 진행 중 브랜치 등이 바뀌어도 결과 이벤트는 원본과 같은
    값을 가리켜야 하므로(`01_cli.md` 6절) 호출부에서 스냅샷 값을 넘겨야 한다."""
    return Event(
        id=str(uuid.uuid4()),
        schema_version=1,
        occurred_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        source="cli",
        repo=repo if repo is not None else _repo(),
        member=member if member is not None else _member(),
        rule_id=rule_id,
        severity=severity,
        action=action,
        command_summary=command_summary,
        branch=branch,
        pr_number=pr_number,
        explanation=explanation,
        llm_used=llm_used,
        related_event_id=related_event_id,
    )


def record(event: Event) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        _ensure_schema(conn)
        conn.execute(
            """
            INSERT INTO events (
                id, schema_version, occurred_at, source, repo, member,
                rule_id, severity, action, command_summary, branch,
                pr_number, explanation, llm_used, related_event_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO NOTHING
            """,
            (
                event.id,
                event.schema_version,
                event.occurred_at,
                event.source,
                event.repo,
                event.member,
                event.rule_id,
                event.severity,
                event.action,
                event.command_summary,
                event.branch,
                event.pr_number,
                event.explanation,
                int(event.llm_used),
                event.related_event_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def update_explanation(event_id: str, explanation: str, llm_used: bool) -> None:
    """가이드 시작 시점에 이미 insert된 guided 이벤트에 설명을 나중에 채운다.
    다중 위반 큐에서 2번째 이후 가이드는 그 가이드가 실제로 시작될 때(이전 가이드가
    끝난 뒤, 보통 다른 프로세스 실행)에만 설명을 알 수 있어 insert 시점엔 비어 있다."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        _ensure_schema(conn)
        conn.execute(
            "UPDATE events SET explanation = ?, llm_used = ? WHERE id = ?",
            (explanation, int(llm_used), event_id),
        )
        conn.commit()
    finally:
        conn.close()


def query(*, today: bool = False) -> list[Event]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    try:
        _ensure_schema(conn)
        sql = "SELECT * FROM events WHERE repo = ?"
        params: list = [_repo()]
        if today:
            sql += " AND substr(occurred_at, 1, 10) = ?"
            params.append(datetime.now().astimezone().date().isoformat())
        sql += " ORDER BY occurred_at"
        cursor = conn.execute(sql, params)
        columns = [c[0] for c in cursor.description]
        rows = cursor.fetchall()
    finally:
        conn.close()
    return [_row_to_event(dict(zip(columns, row))) for row in rows]


def unsynced(limit: int = 100) -> list[Event]:
    """아직 서버로 보내지 않은 이벤트를 전역(레포 무관)으로 조회한다.
    `query()`/`log`와 달리 레포 필터가 없다 — 학생이 여러 팀 레포를 오갈 수 있어
    `sync`는 로컬에 쌓인 모든 레포의 미전송 이벤트를 다 올려야 한다.

    `action="guided"`인데 `explanation`이 아직 안 채워진 이벤트는 큐에서 아직
    시작되지 않은 가이드일 수 있다(#48). 그 guided를 가리키는 결과 이벤트
    (`guide_completed`/`guide_stopped`, `related_event_id`)가 하나도 없으면
    아직 "진행 중"이므로 이번 sync에서는 올리지 않고 보류한다 — 서버 적재가
    `on conflict (id) do nothing`이라 한 번 explanation=NULL로 올라가면 영원히
    고쳐지지 않기 때문(`docs/architecture/data-flow.md` 공통 규칙). PR #43(템플릿
    폴백)으로 가이드가 실제로 시작되면 explanation은 항상 즉시 채워지므로, NULL로
    남는 건 전부 아직 시작 안 한 큐 항목뿐이다(#63 전제)."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        _ensure_schema(conn)
        cursor = conn.execute(
            """
            SELECT * FROM events
            WHERE synced = 0
              AND (
                  action != 'guided'
                  OR explanation IS NOT NULL
                  OR EXISTS (
                      SELECT 1 FROM events AS followup
                      WHERE followup.related_event_id = events.id
                  )
              )
            ORDER BY occurred_at, id
            LIMIT ?
            """,
            (limit,),
        )
        columns = [c[0] for c in cursor.description]
        rows = cursor.fetchall()
    finally:
        conn.close()
    return [_row_to_event(dict(zip(columns, row))) for row in rows]


def mark_synced(ids: list[str]) -> None:
    if not ids:
        return
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        _ensure_schema(conn)
        placeholders = ",".join("?" * len(ids))
        conn.execute(f"UPDATE events SET synced = 1 WHERE id IN ({placeholders})", ids)
        conn.commit()
    finally:
        conn.close()


def mark_rejected(ids: list[str]) -> None:
    """서버가 거절한 이벤트를 synced=2로 영구 제외한다. rejected가 synced=0으로
    남으면 unsynced()가 매번 같은 거절 건부터 돌려줘 그 뒤 정상 이벤트가
    전송되지 못하는 문제(#60 리뷰)를 막기 위함. 재전송은 별도 기능으로 다룬다."""
    if not ids:
        return
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        _ensure_schema(conn)
        placeholders = ",".join("?" * len(ids))
        conn.execute(f"UPDATE events SET synced = 2 WHERE id IN ({placeholders})", ids)
        conn.commit()
    finally:
        conn.close()


def _row_to_event(row: dict) -> Event:
    row.pop("synced", None)  # synced는 로컬 전송 상태일 뿐 스키마 v1 필드가 아님
    row["llm_used"] = bool(row["llm_used"])
    return Event(**row)


def _repo() -> str:
    # fork+PR 워크플로에서 origin은 각자의 fork라 팀 공용 레포 이름이 아니다.
    # upstream(팀 레포)을 우선 쓰고, 없으면(혼자 쓰는 레포 등) origin으로 폴백한다.
    url = _remote_url("upstream") or _remote_url("origin")
    match = re.search(r"[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    return match.group(1).lower() if match else url.lower()


def _remote_url(name: str) -> str:
    result = subprocess.run(
        ["git", "remote", "get-url", name],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def _member() -> str:
    return (config.member() or _member_fallback()).strip().lower()


def _member_fallback() -> str:
    result = subprocess.run(
        ["git", "config", "user.name"],
        capture_output=True,
        text=True,
        check=False,
    )
    name = result.stdout.strip().lower()
    return re.sub(r"[^a-z0-9-]", "", name)
