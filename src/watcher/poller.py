import itertools
import logging
import time
from collections.abc import Callable

from watcher import events, github_client, push_detection
from watcher.config import WatcherConfig
from watcher.github_client import GitHubClientError

logger = logging.getLogger("watcher")


def poll_once(config: WatcherConfig) -> None:
    """한 번의 폴링 tick. 토큰·레포 설정이 실제로 GitHub API와 통하는지 확인하는
    스모크 호출 후, push 감지(R01·R02)를 돌려 위반이 있으면 이벤트로 저장한다."""
    repo = github_client.get_repo(config)
    logger.info(
        "poll ok: %s (default_branch=%s)", config.repo, repo.get("default_branch")
    )

    for event in push_detection.run(config):
        path = events.write_event(event, config.events_dir)
        logger.info("detected %s on %s -> %s", event.rule_id, event.branch, path)


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
