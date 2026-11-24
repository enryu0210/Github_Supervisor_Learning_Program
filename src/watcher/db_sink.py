import logging
import re
from dataclasses import asdict

from postgrest.exceptions import APIError

from gitcoach.models import Event
from supabase import Client, create_client
from watcher.config import WatcherConfig, WatcherConfigError

logger = logging.getLogger("watcher")

# events.member DB 제약(watcher-load.md 3절)과 동일. github-actions[bot] 같은 봇
# 계정은 `[`·`]` 때문에 거절되므로 배치에 넣기 전에 걸러낸다.
_MEMBER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class DbSinkError(Exception):
    pass


def create_client_from_config(config: WatcherConfig) -> Client:
    return create_client(config.supabase_url, config.supabase_service_key)


def resolve_repo_id(client: Client, repo_full_name: str) -> str:
    """시작할 때 한 번만 호출한다. 없으면 매 폴링마다 조용히 실패하지 않도록
    여기서 멈춘다(watcher-load.md 2절). `repos.full_name`은 소문자로 저장되어
    있어(repos 체크 제약과 동일 규칙) 여기서도 소문자로 맞춰 조회한다."""
    repo_full_name = repo_full_name.lower()
    try:
        res = (
            client.table("repos")
            .select("id")
            .eq("full_name", repo_full_name)
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise WatcherConfigError(f"repos 조회에 실패했어요: {exc}") from exc
    if not res.data:
        raise WatcherConfigError(
            f"repos에 {repo_full_name}가 없어요. DB 담당에게 seed 등록을 요청하세요."
        )
    return res.data[0]["id"]


def upload_events(client: Client, events: list[Event]) -> None:
    rows = []
    for event in events:
        if not _MEMBER_PATTERN.match(event.member):
            logger.warning(
                "member가 DB 제약에 맞지 않아 건너뜀: %s (%s)",
                event.member,
                event.rule_id,
            )
            continue
        rows.append(asdict(event))
    if not rows:
        return
    try:
        client.table("events").upsert(
            rows, on_conflict="id", ignore_duplicates=True
        ).execute()
    except APIError as exc:
        raise DbSinkError(f"events 업로드에 실패했어요: {exc}") from exc


def upload_prs(client: Client, repo_id: str, prs: list[dict]) -> dict[int, str]:
    """`(repo_id, number)` 기준 upsert. 반환값은 pr_reviews 적재에 쓴다."""
    if not prs:
        return {}
    rows = [
        {**{k: v for k, v in pr.items() if k != "repo"}, "repo_id": repo_id}
        for pr in prs
    ]
    try:
        res = client.table("prs").upsert(rows, on_conflict="repo_id,number").execute()
    except APIError as exc:
        raise DbSinkError(f"prs 업로드에 실패했어요: {exc}") from exc
    return {row["number"]: row["id"] for row in res.data}


def upload_pr_reviews(
    client: Client, repo_id: str, pr_ids: dict[int, str], records: list[dict]
) -> None:
    """`prs` 적재 뒤에 호출한다. 이번 배치에서 적재하지 않은 PR의 리뷰는
    `(repo_id, number)`로 `prs.id`를 조회해 채운다(watcher-load.md 5절)."""
    if not records:
        return
    rows = []
    for record in records:
        pr_number = record["pr_number"]
        pr_id = pr_ids.get(pr_number) or _lookup_pr_id(client, repo_id, pr_number)
        if pr_id is None:
            logger.warning("pr_id를 찾을 수 없어 리뷰를 건너뜀: PR #%d", pr_number)
            continue
        rows.append(
            {
                "review_id": record["review_id"],
                "pr_id": pr_id,
                "reviewer": record["reviewer"],
                "status": record["status"],
                "submitted_at": record["submitted_at"],
                "commit_sha": record["commit_sha"],
                "html_url": record["html_url"],
            }
        )
    if not rows:
        return
    try:
        client.table("pr_reviews").upsert(rows, on_conflict="review_id").execute()
    except APIError as exc:
        raise DbSinkError(f"pr_reviews 업로드에 실패했어요: {exc}") from exc


def upload_quizzes(client: Client, rows: list[dict]) -> None:
    """`id`가 결정론적(uuid5)이라 `on conflict (id) do nothing`으로 넣는다
    (watcher-load.md 6절, #116 1번)."""
    if not rows:
        return
    try:
        client.table("quizzes").upsert(
            rows, on_conflict="id", ignore_duplicates=True
        ).execute()
    except APIError as exc:
        raise DbSinkError(f"quizzes 업로드에 실패했어요: {exc}") from exc


def _lookup_pr_id(client: Client, repo_id: str, number: int) -> str | None:
    try:
        res = (
            client.table("prs")
            .select("id")
            .eq("repo_id", repo_id)
            .eq("number", number)
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise DbSinkError(f"pr_id 조회에 실패했어요: {exc}") from exc
    return res.data[0]["id"] if res.data else None
