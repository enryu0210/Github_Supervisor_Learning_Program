import itertools
import logging
import time
from collections.abc import Callable

from supabase import Client
from watcher import (
    branch_naming,
    commit_message,
    db_sink,
    github_client,
    pr_base_detection,
    pr_reviews,
    push_detection,
    quiz_generation,
    review_concentration,
    stale_prs,
)
from watcher.config import WatcherConfig
from watcher.github_client import GitHubClientError

logger = logging.getLogger("watcher")


def poll_once(config: WatcherConfig, client: Client, repo_id: str) -> None:
    """한 번의 폴링 tick. 토큰·레포 설정이 실제로 GitHub API와 통하는지 확인하는
    스모크 호출 후, push 감지(R01·R02)·브랜치명 감지(R05)·PR base 감지(R08)·
    커밋 메시지 감지(R06)를 돌려 위반이 있으면 한 배치로 `events`에 적재하고,
    `prs`(방치 PR 판정용)·`pr_reviews`(review 단위, D4/#44 확정 필드)를 DB에
    upsert한다. 리뷰 쏠림 통계(멤버별 리뷰 수·비중, 판정 기준값은 D2 미정이라
    숫자만)는 DB 테이블이 없어 그대로 JSON 스냅샷으로 남긴다. `events`의 아직
    퀴즈가 없는 근거 이벤트는 Ollama로 퀴즈화해 `quizzes`에 넣는다(5-1절 12번,
    #116) — prs 업로드 실패로 일찍 return해도 건너뛰지 않도록 그 앞에 둔다."""
    repo = github_client.get_repo(config)
    logger.info(
        "poll ok: %s (default_branch=%s)", config.repo, repo.get("default_branch")
    )

    violations = [
        *push_detection.run(config),
        *branch_naming.run(config),
        *pr_base_detection.run(config),
        *commit_message.run(config),
    ]
    if violations:
        try:
            db_sink.upload_events(client, violations)
        except db_sink.DbSinkError as exc:
            logger.warning("events 업로드 실패: %s", exc)
        else:
            logger.info("%d건의 detected 이벤트 업로드", len(violations))

    quiz_rows = quiz_generation.generate(client, config)
    if quiz_rows:
        try:
            db_sink.upload_quizzes(client, quiz_rows)
        except db_sink.DbSinkError as exc:
            logger.warning("quizzes 업로드 실패: %s", exc)
        else:
            logger.info("%d건의 퀴즈 생성", len(quiz_rows))

    reviews = review_concentration.run(config)
    path = review_concentration.write_snapshot(
        reviews, config.review_concentration_path
    )
    logger.info("review concentration snapshot: %d명 -> %s", len(reviews), path)

    prs = stale_prs.run(config)
    try:
        pr_ids = db_sink.upload_prs(client, repo_id, prs)
    except db_sink.DbSinkError as exc:
        logger.warning("prs 업로드 실패, 이번 주기는 pr_reviews를 건너뜀: %s", exc)
        return
    logger.info("%d건의 PR 업로드", len(prs))

    pr_review_records = pr_reviews.run(config)
    try:
        db_sink.upload_pr_reviews(client, repo_id, pr_ids, pr_review_records)
    except db_sink.DbSinkError as exc:
        logger.warning("pr_reviews 업로드 실패: %s", exc)
    else:
        logger.info("%d건의 pr_reviews 업로드", len(pr_review_records))


def run_forever(
    config: WatcherConfig,
    *,
    sleep: Callable[[float], None] = time.sleep,
    max_iterations: int | None = None,
    client: Client | None = None,
) -> None:
    """무한 폴링 루프. `repo_id`는 시작할 때 한 번만 찾는다 — 없으면 매 주기
    조용히 실패하지 않도록 여기서 멈춘다(watcher-load.md 2절). 한 번의 tick이
    실패해도(네트워크·DB 오류 등) 로그만 남기고 다음 주기에 계속 돈다 — 장기
    실행 서비스라 한 번의 오류로 전체가 죽으면 안 된다."""
    client = client or db_sink.create_client_from_config(config)
    repo_id = db_sink.resolve_repo_id(client, config.repo)

    logger.info(
        "watcher 시작: repo=%s, interval=%ds", config.repo, config.poll_interval_seconds
    )
    iterations = itertools.count() if max_iterations is None else range(max_iterations)
    for _ in iterations:
        try:
            poll_once(config, client, repo_id)
        except GitHubClientError as exc:
            logger.warning("poll failed: %s", exc)
        except Exception:
            logger.exception("poll failed with an unexpected error")
        sleep(config.poll_interval_seconds)
