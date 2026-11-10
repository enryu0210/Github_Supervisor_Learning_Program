import re
import sqlite3
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

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
    explanation TEXT NOT NULL,
    llm_used INTEGER NOT NULL,
    related_event_id TEXT
)
"""


def make_event(
    *,
    rule_id: str,
    severity: str,
    branch: str,
    action: str,
    command_summary: str,
    pr_number: int | None = None,
    explanation: str = "",
    llm_used: bool = False,
    related_event_id: str | None = None,
) -> Event:
    return Event(
        id=str(uuid.uuid4()),
        schema_version=1,
        occurred_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        source="cli",
        repo=_repo(),
        member=_member(),
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
        conn.execute(_SCHEMA)
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


def query(*, today: bool = False) -> list[Event]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(_SCHEMA)
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


def _row_to_event(row: dict) -> Event:
    row["llm_used"] = bool(row["llm_used"])
    return Event(**row)


def _repo() -> str:
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=False,
    )
    url = result.stdout.strip()
    match = re.search(r"[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    return match.group(1).lower() if match else url.lower()


def _member() -> str:
    result = subprocess.run(
        ["git", "config", "user.name"],
        capture_output=True,
        text=True,
        check=False,
    )
    name = result.stdout.strip().lower()
    return re.sub(r"[^a-z0-9]", "", name)  # TODO(cli-config): github_login으로 교체
