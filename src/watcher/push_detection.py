import logging

from gitcoach.models import Event
from watcher import events, github_client
from watcher.config import WatcherConfig
from watcher.github_client import GitHubClientError

logger = logging.getLogger("watcher")

# watcher는 레포 워킹트리에 접근하지 않아 `.gitcoach.toml`을 읽을 수 없다.
# CLI가 `cli-config` 전에 쓰던 하드코딩과 같은 성격(01_cli.md 3-8, context.py 주석).
_PROTECTED_BRANCHES = ["main"]
_ZERO_SHA = "0" * 40


def _branch_name(ref: str) -> str:
    return ref.removeprefix("refs/heads/")


def _is_pr_merge(config: WatcherConfig, sha: str, branch: str) -> bool:
    """이 커밋이 `branch`를 base로 하는 머지된 PR의 일부인지 확인한다.

    release→main처럼 PR 병합으로 들어온 커밋도 PushEvent를 발생시키므로,
    이 확인이 없으면 정상적인 릴리스 병합마다 R01 거짓 양성이 쌓인다.
    조회 실패는 fail-open(위반 아님으로 취급, 다음 폴링에서 다시 본다) —
    거짓 양성보다 "이번 틱엔 놓치고 다음 틱에 다시 본다"가 낫다고 판단했다.
    """
    try:
        pulls = github_client.list_pulls_for_commit(config, sha)
    except GitHubClientError as exc:
        logger.warning("PR 연결 확인 실패, 이번 틱은 건너뜀: %s", exc)
        return True
    return any(
        pr.get("base", {}).get("ref") == branch and pr.get("merged_at") for pr in pulls
    )


def _is_force_push(config: WatcherConfig, before: str, head: str) -> bool:
    """`before...head` 비교 결과로 히스토리 재작성(force push) 여부를 판정한다.

    Events API의 PushEvent에는 webhook payload의 `forced` 필드가 없어
    compare API의 status로 파생 판정한다. "diverged"면 히스토리가 재작성된
    경우(force push), "ahead"면 정상 push다. 조회 실패는 fail-open.
    """
    try:
        result = github_client.compare_commits(config, before, head)
    except GitHubClientError as exc:
        logger.warning("force push 확인 실패, 이번 틱은 건너뜀: %s", exc)
        return False
    return result.get("status") == "diverged"


def check_push_event(config: WatcherConfig, raw_event: dict) -> list[Event]:
    if raw_event.get("type") != "PushEvent":
        return []

    payload = raw_event["payload"]
    branch = _branch_name(payload["ref"])
    before = payload["before"]
    head = payload["head"]
    member = raw_event["actor"]["login"]

    violations: list[Event] = []

    if branch in _PROTECTED_BRANCHES and not _is_pr_merge(config, head, branch):
        violations.append(
            events.make_detected_event(
                rule_id="R01",
                severity="high",
                repo=config.repo,
                member=member,
                branch=branch,
                entity=head,
                explanation=(
                    f"GitHub Events API 조회 결과 {branch} 브랜치에 직접 push 발견"
                    "(연결된 병합 PR 없음)"
                ),
            )
        )

    if before != _ZERO_SHA and before != head and _is_force_push(config, before, head):
        violations.append(
            events.make_detected_event(
                rule_id="R02",
                severity="high",
                repo=config.repo,
                member=member,
                branch=branch,
                entity=f"{branch}:{head}",
                explanation=(
                    "GitHub compare API 결과 히스토리가 재작성된 force push 발견"
                    "(status=diverged)"
                ),
            )
        )

    return violations


def run(config: WatcherConfig) -> list[Event]:
    raw_events = github_client.list_events(config)
    violations: list[Event] = []
    for raw_event in raw_events:
        violations.extend(check_push_event(config, raw_event))
    return violations
