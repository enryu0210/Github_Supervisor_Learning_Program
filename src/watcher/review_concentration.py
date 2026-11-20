import json
from pathlib import Path

from watcher import github_client
from watcher.config import WatcherConfig

_PENDING_STATE = "PENDING"


def _submitted_reviews(reviews: list[dict]) -> list[dict]:
    """제출 전(PENDING) 리뷰는 집계에서 뺀다(samples/watcher/README.md #44 합의와 동일 기준)."""
    return [r for r in reviews if r.get("state") != _PENDING_STATE]


def count_by_reviewer(reviews: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for review in reviews:
        reviewer = review["user"]["login"].lower()
        counts[reviewer] = counts.get(reviewer, 0) + 1
    return counts


def to_summary(counts: dict[str, int]) -> list[dict]:
    """멤버별 리뷰 수·비중만 낸다. '기준 초과' 판정은 기준값이 아직 팀 결정 전이라
    하지 않는다(01_cli.md 5장 — stale_prs가 '방치 여부'를 DB 뷰에 맡기는 것과 동일한 방식)."""
    total = sum(counts.values())
    return [
        {
            "reviewer": reviewer,
            "review_count": count,
            "share": round(count / total, 4) if total else 0.0,
        }
        for reviewer, count in sorted(counts.items())
    ]


def run(config: WatcherConfig) -> list[dict]:
    reviews: list[dict] = []
    for pr in github_client.list_all_pulls(config):
        reviews.extend(
            _submitted_reviews(github_client.list_pull_reviews(config, pr["number"]))
        )
    return to_summary(count_by_reviewer(reviews))


def write_snapshot(records: list[dict], path: Path) -> Path:
    """prs 스냅샷(stale_prs.write_snapshot)과 같은 방식 — 매 폴링마다 전체를 덮어쓴다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
