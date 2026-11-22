from watcher import github_client
from watcher.config import WatcherConfig

_PENDING_STATE = "PENDING"


def _is_valid_review(review: dict) -> bool:
    """제출 전(PENDING) 리뷰는 수집하지 않는다(review_concentration과 동일 기준,
    D4/#44 — submitted_at이 비어 있어 not null 요건과도 맞물림). 삭제된 계정
    (`user`가 null)이나 사라진 커밋(`commit_id`가 null)의 리뷰는 DB not null
    제약에 걸리므로 함께 거른다(watcher-load.md 5절)."""
    return (
        review.get("state") != _PENDING_STATE
        and review.get("user") is not None
        and review.get("commit_id") is not None
    )


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
            if _is_valid_review(review):
                records.append(to_pr_review_record(config.repo, pr["number"], review))
    return records
