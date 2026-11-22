from gitcoach.models import Event
from watcher import events, github_client
from watcher.config import WatcherConfig

# release/vX.Y만 main을 base로 하는 게 정상 흐름이다(CLAUDE.md 브랜치 정책).
# 그 외 모든 브랜치(feature·fix·docs 등)는 develop을 base로 해야 하므로,
# 접두사를 화이트리스트로 나열하는 대신 "release가 아니면 develop이어야 한다"로 일반화한다.
_REQUIRED_BASE = "develop"


def check_pr_base(repo: str, pr: dict) -> Event | None:
    head_ref = pr["head"]["ref"]
    base_ref = pr["base"]["ref"]

    if head_ref.startswith("release/") or base_ref == _REQUIRED_BASE:
        return None

    number = pr["number"]
    return events.make_detected_event(
        rule_id="R08",
        severity="low",
        repo=repo,
        member=pr["user"]["login"],
        branch=head_ref,
        entity=f"pr:{number}",
        explanation=(
            f"GitHub PR #{number} 확인 결과 head={head_ref}가 base={base_ref}로 "
            f"열려 있음({_REQUIRED_BASE}이어야 함)"
        ),
        pr_number=number,
        occurred_at=pr["created_at"],
    )


def run(config: WatcherConfig) -> list[Event]:
    violations: list[Event] = []
    for pr in github_client.list_open_pulls(config):
        event = check_pr_base(config.repo, pr)
        if event is not None:
            violations.append(event)
    return violations
