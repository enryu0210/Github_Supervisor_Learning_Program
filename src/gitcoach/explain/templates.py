_FALLBACKS = {
    "R01": (
        "main은 팀 전체가 공유하는 배포 브랜치예요. "
        "지금처럼 직접 push하면 리뷰·CI 없이 바로 반영되어 문제가 생겼을 때 되돌리기 번거로워요. "
        "아래 가이드를 따라 feature 브랜치로 옮겨 봐요."
    ),
    "R02": (
        "force push는 원격에 이미 올라간 커밋 기록을 덮어써요. "
        "다른 사람이 받아간 기록과 어긋나 그 사람의 작업이 사라진 것처럼 보일 수 있어요. "
        "아래 가이드를 따라 안전하게 맞춰 봐요."
    ),
    "R03": (
        "{files}에는 비밀 정보가 들어 있을 수 있어요. "
        "한 번 커밋되면 기록에 영구히 남아 지우기 어려워요. "
        "아래 가이드를 따라 스테이징에서 빼고 .gitignore에 등록해 봐요."
    ),
}

_DEFAULT = "아래 가이드를 따라 올바른 방법으로 진행해 봐요."


def fallback(rule_id: str, facts: dict) -> str:
    template = _FALLBACKS.get(rule_id, _DEFAULT)
    if rule_id == "R03":
        files = facts.get("files") or ["해당 파일"]
        return template.format(files=", ".join(files))
    return template
