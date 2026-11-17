import logging

from gitcoach.models import Event
from gitcoach.rules.r05_branch_naming import is_valid_branch_name, suggest_name
from watcher import events, github_client
from watcher.config import WatcherConfig
from watcher.github_client import GitHubClientError

logger = logging.getLogger("watcher")

# main/develop은 브랜치 보호 정책상 특례 브랜치명이라 R05 정규식(feature|fix/<영역>-<설명>,
# docs/<설명>, release/vX.Y)에 안 맞아도 위반이 아니다(CLAUDE.md 브랜치 정책).
# push_detection.py의 _PROTECTED_BRANCHES와 같은 성격의 하드코딩 — watcher는 워킹트리가
# 없어 .gitcoach.toml을 읽을 수 없다.
_EXEMPT_BRANCHES = {"main", "develop"}

_UNKNOWN_MEMBER = "unknown"


def _attribute_member(config: WatcherConfig, sha: str) -> str:
    """브랜치 head 커밋의 GitHub 계정을 member로 쓴다. 브랜치 목록 API엔 작성자
    정보가 없어 위반인 브랜치에만(전체 브랜치 수가 아니라 위반 건수만큼) 커밋을
    한 번 더 조회한다. 조회 실패·연결된 계정 없음은 "unknown"으로 채우되, 위반
    자체는 그대로 기록한다 — push_detection의 fail-open(위반을 숨김)과 반대
    방향이다. 여기선 "위반 여부"는 is_valid_branch_name으로 이미 확정됐고
    "누구인지"만 불확실하므로, 귀책자를 못 찾았다고 이미 확실한 위반을 지우면
    더 나쁘다.
    """
    try:
        commit = github_client.get_commit(config, sha)
    except GitHubClientError as exc:
        logger.warning("브랜치 커밋 작성자 조회 실패, member=unknown으로 기록: %s", exc)
        return _UNKNOWN_MEMBER
    author = commit.get("author") or {}
    return author.get("login") or _UNKNOWN_MEMBER


def check_branch(config: WatcherConfig, branch: dict) -> Event | None:
    name = branch.get("name", "")
    if not name or name in _EXEMPT_BRANCHES or is_valid_branch_name(name):
        return None

    sha = branch.get("commit", {}).get("sha", "")
    member = _attribute_member(config, sha) if sha else _UNKNOWN_MEMBER
    suggestion = suggest_name(name)

    return events.make_detected_event(
        rule_id="R05",
        severity="low",
        repo=config.repo,
        member=member,
        branch=name,
        entity=name,
        explanation=(
            f"GitHub 브랜치 목록 조회 결과 '{name}' 브랜치명이 규칙에 안 맞음"
            f"(제안: {suggestion})"
        ),
    )


def run(config: WatcherConfig) -> list[Event]:
    violations: list[Event] = []
    for branch in github_client.list_branches(config):
        event = check_branch(config, branch)
        if event is not None:
            violations.append(event)
    return violations
