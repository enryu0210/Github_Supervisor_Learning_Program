from gitcoach.commit_format import is_valid_commit_message
from gitcoach.models import Event
from watcher import events, github_client
from watcher.config import WatcherConfig

_UNKNOWN_MEMBER = "unknown"


def check_commit(repo: str, pr: dict, commit: dict) -> Event | None:
    # 제목줄만 검사한다. R06 정규식은 한 줄 형식만 통과시키는데, 이 팀은
    # 제목줄 뒤에 본문을 붙이는 커밋을 실제로 쓰고 있어서(#101 확인) 전체
    # 메시지를 검사하면 제목줄이 규칙에 맞는 커밋까지 위반으로 잘못 걸린다.
    subject = commit["commit"]["message"].splitlines()[0]
    if is_valid_commit_message(subject):
        return None

    author = commit.get("author") or {}
    member = author.get("login") or _UNKNOWN_MEMBER
    number = pr["number"]

    return events.make_detected_event(
        rule_id="R06",
        severity="low",
        repo=repo,
        member=member,
        branch=pr["head"]["ref"],
        entity=commit["sha"],
        explanation=f"GitHub PR #{number}의 커밋 목록 조회 결과 커밋 메시지 규칙 위반 발견",
        pr_number=number,
    )


def run(config: WatcherConfig) -> list[Event]:
    violations: list[Event] = []
    for pr in github_client.list_open_pulls(config):
        for commit in github_client.list_pull_commits(config, pr["number"]):
            event = check_commit(config.repo, pr, commit)
            if event is not None:
                violations.append(event)
    return violations
