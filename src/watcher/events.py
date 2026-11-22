import json
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from gitcoach.models import Event

# 한 번 생성해 영구 고정한 값. 바뀌면 같은 사건의 id가 전부 달라져서
# DB의 `on conflict (id) do nothing` 멱등성이 깨진다(01_cli.md 6장).
_NAMESPACE = uuid.UUID("e90de9d9-e31a-4b41-881e-33a570e1d7f0")


def make_detected_event(
    *,
    rule_id: str,
    severity: str,
    repo: str,
    member: str,
    branch: str,
    entity: str,
    explanation: str,
    pr_number: int | None = None,
    occurred_at: str | None = None,
) -> Event:
    repo = repo.lower()
    member = member.lower()
    event_id = uuid.uuid5(_NAMESPACE, f"{rule_id}\x1f{repo}\x1f{entity}")
    return Event(
        id=str(event_id),
        schema_version=1,
        # events는 DB에 do-nothing upsert되므로 occurred_at은 최초 적재 값이 영구
        # 고정된다. 실제 사건 시각을 아는 호출자(push_detection 등)는 occurred_at을
        # 넘기고, 모르는 경우(R05)만 감지 시각으로 대신한다(watcher-load.md 3절).
        occurred_at=occurred_at
        or datetime.now().astimezone().isoformat(timespec="seconds"),
        source="github",
        repo=repo,
        member=member,
        rule_id=rule_id,
        severity=severity,
        action="detected",
        command_summary=None,
        branch=branch,
        pr_number=pr_number,
        explanation=explanation,
        llm_used=False,
        related_event_id=None,
    )


def write_event(event: Event, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{event.id}.json"
    path.write_text(
        json.dumps(asdict(event), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path
