import json
from pathlib import Path

from watcher import github_client
from watcher.config import WatcherConfig


def to_pr_record(repo: str, pr: dict) -> dict:
    """GitHub PR 응답을 `prs` 테이블 스키마(샘플: samples/watcher/prs_sample.json)로 변환한다.
    방치 여부(3일 기준, D3)는 DB 뷰 `v_stale_prs`가 `last_activity_at`으로 판정하므로
    여기서는 계산하지 않는다(D2 미정 — rule_id·`detected` 이벤트화도 하지 않음)."""
    reviewers = [r["login"].lower() for r in pr.get("requested_reviewers", [])]
    return {
        "repo": repo.lower(),
        "number": pr["number"],
        "title": pr["title"],
        "author": pr["user"]["login"].lower(),
        "state": pr["state"],
        "opened_at": pr["created_at"],
        "merged_at": pr.get("merged_at"),
        "reviewers": reviewers,
        "last_activity_at": pr["updated_at"],
    }


def run(config: WatcherConfig) -> list[dict]:
    return [
        to_pr_record(config.repo, pr) for pr in github_client.list_all_pulls(config)
    ]


def write_snapshot(records: list[dict], path: Path) -> Path:
    """`events.write_event`와 달리 건마다 파일을 쌓지 않는다. `prs`는
    (repo, number) 기준 upsert 대상이라 매 폴링마다 전체 배열을 한 파일에 덮어써
    DB 적재(10번 PR)가 그대로 batch upsert하면 되게 한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
