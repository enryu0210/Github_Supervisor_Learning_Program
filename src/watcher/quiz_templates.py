"""Ollama 실패·응답 형식 오류 시 쓰는 고정 폴백 문항(explain/templates.py의 폴백
패턴과 동일). 선택지는 항상 4개다."""

QuizTemplate = tuple[
    str, list[str], int, str
]  # question, choices, answer_index, explanation

_FALLBACKS: dict[str, QuizTemplate] = {
    "R01": (
        "main 브랜치에 직접 push하면 생길 수 있는 일은?",
        [
            "리뷰·CI 없이 배포까지 이어질 수 있다",
            "push가 자동으로 PR로 바뀐다",
            "로컬 커밋이 사라진다",
            "아무 일도 없다",
        ],
        0,
        "main은 팀이 공유하는 배포 브랜치라 리뷰·CI를 거쳐 PR로 들어가야 해요.",
    ),
    "R02": (
        "팀원이 이미 push한 브랜치에 force push를 하면?",
        [
            "아무 일도 없다",
            "팀원의 커밋이 원격에서 사라질 수 있다",
            "내 로컬 커밋이 삭제된다",
            "PR이 자동 병합된다",
        ],
        1,
        "force push는 원격 기록을 내 기록으로 덮어써요.",
    ),
    "R03": (
        ".env를 실수로 staged 했을 때 올바른 명령은?",
        [
            "git restore --staged .env",
            "git commit --amend",
            "git push --force",
            "git add .",
        ],
        0,
        "staged에서 빼고 .gitignore에 등록해요.",
    ),
    "R04": (
        "main에서 커밋해 버렸을 때 먼저 할 일은?",
        [
            "feature 브랜치를 만들어 커밋을 옮긴다",
            "바로 push한다",
            "레포를 지우고 다시 clone한다",
            "git clean -fd로 지운다",
        ],
        0,
        "feature 브랜치로 커밋을 옮긴 뒤 main을 원격 상태로 되돌려요.",
    ),
    "R05": (
        "팀 규칙에 맞는 브랜치 이름은?",
        ["Feature/Login", "feature/web-login", "fix_bug", "test#1"],
        1,
        "feature|fix/<영역>-<설명> 형식이고, 대문자·#은 쓰지 않아요.",
    ),
    "R06": (
        "팀 규칙에 맞는 커밋 메시지는?",
        ["수정", "fix", "feat(web): 개요 KPI 카드 추가", "asdf"],
        2,
        "type(scope): 설명 형식이에요.",
    ),
    "R08": (
        "feature 브랜치의 PR은 어디를 base로 열어야 할까?",
        ["main", "develop", "release", "아무 브랜치나"],
        1,
        "feature → develop으로 PR을 올려야 리뷰·통합 과정을 거쳐요.",
    ),
}

_DEFAULT: QuizTemplate = (
    "이 상황에서 올바른 다음 행동은?",
    [
        "규칙에 맞게 다시 시도한다",
        "그대로 둔다",
        "레포를 지운다",
        "되돌릴 수 없는 명령을 쓴다",
    ],
    0,
    "규칙 도감에서 해당 규칙을 다시 확인해 보세요.",
)


def fallback(rule_id: str) -> QuizTemplate:
    return _FALLBACKS.get(rule_id, _DEFAULT)
