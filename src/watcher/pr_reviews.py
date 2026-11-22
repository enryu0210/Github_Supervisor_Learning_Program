import json
from pathlib import Path

from watcher import github_client
from watcher.config import WatcherConfig

_PENDING_STATE = "PENDING"


def _is_submitted(review: dict) -> bool:
    """제출 전(PENDING) 리뷰는 수집하지 않는다(review_concentration과 동일 기준,
    D4/#44 — submitted_at이 비어 있어 not null 요건과도 맞물림)."""
    return review.get("state") != _PENDING_STATE


def to_pr_review_record(repo: str, pr_number: int, review: dict) -> dict:
    """GitHub 리뷰 응답을 `pr_reviews` 테이블 스키마(D4/#44, 샘플:
    samples/watcher/pr_reviews_sample.json)로 변환한다. `body`는 필드 자체를
    넣지 않는다(#44 필드 목록에서 제외)."""
    return {
        "review_id": review["id"],
        "repo": repo.lower(),
        "pr_number": pr_number,
        "reviewer": review["user"]["login"].lower(),
        "status": review["state"],
        "submitted_at": review["submitted_at"],
        "commit_sha": review["commit_id"],
        "html_url": review["html_url"],
    }


def run(config: WatcherConfig) -> list[dict]:
    records: list[dict] = []
    for pr in github_client.list_all_pulls(config):
        for review in github_client.list_pull_reviews(config, pr["number"]):
            if _is_submitted(review):
                records.append(to_pr_review_record(config.repo, pr["number"], review))
    return records


def write_snapshot(records: list[dict], path: Path) -> Path:
    """`review_id` 기준 upsert 대상이라 `stale_prs`/`review_concentration`과
    같은 방식 — 매 폴링마다 전체를 덮어쓴다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
