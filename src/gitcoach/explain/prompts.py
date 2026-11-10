import json

_SYSTEM = (
    "너는 Git을 처음 배우는 학생 팀을 돕는 코치다.\n"
    "아래 '사실'만 근거로 설명한다. 사실에 없는 내용과 명령어는 절대 만들지 않는다."
)


def build_messages(title: str, facts: dict) -> list[dict]:
    user = (
        f"규칙: {title}\n"
        f"사실: {json.dumps(facts, ensure_ascii=False)}\n"
        "형식: 한국어 3문장, 존댓말. (1) 왜 문제인지 (2) 그대로 하면 생기는 일\n"
        "(3) 아래 가이드를 따라 해 보자고만 말한다."
    )
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": user},
    ]
