"""PR 규칙 검사 — CI `pr-convention` 워크플로가 실행한다.

CLI(R05 브랜치 이름·R06 커밋 메시지)와 watcher(R08 PR base)의 판정 함수를 그대로
불러 쓴다. 로컬 경고, watcher 감지, CI 판정이 늘 같은 기준을 갖게 하려는 것이다
(규칙을 여기서 다시 쓰면 한쪽만 고쳐지는 순간 기준이 갈라진다).

이벤트는 적재하지 않는다(같은 위반은 watcher가 `detected`로 남김, data-flow.md).

사용법(워크플로):
    git log --no-merges --format=%s BASE..HEAD | python -m watcher.pr_convention
    환경변수 HEAD_REF, BASE_REF, PR_TITLE 필요
"""

import os
import sys

from gitcoach.commit_format import is_valid_commit_message
from gitcoach.rules.r05_branch_naming import is_valid_branch_name
from watcher.pr_base_detection import is_valid_pr_base

_COMMIT_FORMAT = "`type(scope): 설명` (예: `feat(cli): R01 감지 추가`)"


def check_pr(
    head_ref: str, base_ref: str, title: str, commit_subjects: list[str]
) -> list[str]:
    """규칙에 어긋난 항목을 사람이 읽을 문장으로 돌려준다. 빈 목록이면 통과."""
    problems: list[str] = []

    if not is_valid_branch_name(head_ref):
        problems.append(
            f"R05 브랜치 이름 `{head_ref}`이(가) 규칙에 맞지 않아요. "
            "`feature/<영역>-<설명>`, `fix/<영역>-<설명>`, `docs/<설명>`, "
            "`release/vX.Y` 중 하나로 바꿔 주세요."
        )
    if not is_valid_pr_base(head_ref, base_ref):
        problems.append(
            f"R08 PR이 `{base_ref}`로 열려 있어요. "
            "`release/*`가 아니면 base는 `develop`이어야 해요."
        )
    if not is_valid_commit_message(title):
        problems.append(
            f"R06 PR 제목 `{title}`이(가) {_COMMIT_FORMAT} 형식이 아니에요."
        )

    # release PR은 develop 전체 이력을 담는다. 규칙이 생기기 전 커밋(init_commit 등)이
    # 섞여 있어 항상 실패하므로, 커밋은 feature/fix PR 단계에서 이미 검사한 것으로 본다.
    if not head_ref.startswith("release/"):
        for subject in commit_subjects:
            if not is_valid_commit_message(subject):
                problems.append(
                    f"R06 커밋 메시지 `{subject}`이(가) {_COMMIT_FORMAT} 형식이 아니에요."
                )
    return problems


def _escape(text: str) -> str:
    """GitHub Actions 명령(`::error::`) 값에 쓰는 문자를 이스케이프한다.
    브랜치 이름·PR 제목은 PR 작성자가 정하는 값이라 그대로 출력하면 줄바꿈 등으로
    로그 명령을 흉내 낼 수 있다."""
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def main() -> int:
    try:
        head_ref = os.environ["HEAD_REF"]
        base_ref = os.environ["BASE_REF"]
        title = os.environ["PR_TITLE"]
    except KeyError as exc:
        print(f"::error::환경변수 {exc.args[0]}이(가) 없어요 (워크플로 설정 확인)")
        return 2

    subjects = [line for line in sys.stdin.read().splitlines() if line.strip()]
    problems = check_pr(head_ref, base_ref, title, subjects)

    for problem in problems:
        print(f"::error::{_escape(problem)}")
    if problems:
        print(
            f"PR 규칙 위반 {len(problems)}건. 고치는 방법: docs/guide/01_cli.md 규칙 표"
        )
        return 1
    print(f"PR 규칙 통과: 브랜치·base·제목, 커밋 {len(subjects)}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
