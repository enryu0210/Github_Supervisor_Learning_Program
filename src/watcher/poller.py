import itertools
import logging
import time
from collections.abc import Callable

from watcher import (
    branch_naming,
    commit_message,
    events,
    github_client,
    pr_base_detection,
    push_detection,
    review_concentration,
    stale_prs,
)
from watcher.config import WatcherConfig
from watcher.github_client import GitHubClientError

logger = logging.getLogger("watcher")


def poll_once(config: WatcherConfig) -> None:
    """한 번의 폴링 tick. 토큰·레포 설정이 실제로 GitHub API와 통하는지 확인하는
    스모크 호출 후, push 감지(R01·R02)·브랜치명 감지(R05)·PR base 감지(R08)·
    커밋 메시지 감지(R06)를 돌려 위반이 있으면 이벤트로 저장하고,
    PR 스냅샷(`prs.last_activity_at`, 방치 PR 판정용)과 리뷰 쏠림 통계
    (멤버별 리뷰 수·비중, 판정 기준값은 D2 미정이라 숫자만)를 매번 덮어쓴다."""
    repo = github_client.get_repo(config)
    logger.info(
        "poll ok: %s (default_branch=%s)", config.repo, repo.get("default_branch")
    )

    for event in push_detection.run(config):
        path = events.write_event(event, config.events_dir)
        logger.info("detected %s on %s -> %s", event.rule_id, event.branch, path)

    for event in branch_naming.run(config):
        path = events.write_event(event, config.events_dir)
        logger.info("detected %s on %s -> %s", event.rule_id, event.branch, path)

    for event in pr_base_detection.run(config):
        path = events.write_event(event, config.events_dir)
        logger.info("detected %s on %s -> %s", event.rule_id, event.branch, path)

    for event in commit_message.run(config):
        path = events.write_event(event, config.events_dir)
        logger.info("detected %s on %s -> %s", event.rule_id, event.branch, path)

    prs = stale_prs.run(config)
    path = stale_prs.write_snapshot(prs, config.prs_path)
    logger.info("prs snapshot: %d건 -> %s", len(prs), path)

    reviews = review_concentration.run(config)
    path = review_concentration.write_snapshot(
        reviews, config.review_concentration_path
    )
    logger.info("review concentration snapshot: %d명 -> %s", len(reviews), path)


def run_forever(
    config: WatcherConfig,
    *,
    sleep: Callable[[float], None] = time.sleep,
    max_iterations: int | None = None,
) -> None:
    """무한 폴링 루프. 한 번의 tick이 실패해도(네트워크 오류 등) 로그만 남기고
    다음 주기에 계속 돈다 — 장기 실행 서비스라 한 번의 오류로 전체가 죽으면 안 된다."""
    logger.info(
        "watcher 시작: repo=%s, interval=%ds", config.repo, config.poll_interval_seconds
    )
    iterations = itertools.count() if max_iterations is None else range(max_iterations)
    for _ in iterations:
        try:
            poll_once(config)
        except GitHubClientError as exc:
            logger.warning("poll failed: %s", exc)
        except Exception:
            logger.exception("poll failed with an unexpected error")
        sleep(config.poll_interval_seconds)
