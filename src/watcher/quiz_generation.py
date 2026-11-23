import json
import logging
import uuid

from gitcoach.explain import ollama
from supabase import Client
from watcher import quiz_templates
from watcher.config import WatcherConfig

logger = logging.getLogger("watcher")

# 한 번 생성해 영구 고정한 값(watcher/events.py의 _NAMESPACE와 같은 역할, 다른
# 값). 바뀌면 같은 근거 이벤트의 퀴즈 id가 전부 달라져서 `on conflict (id) do
# nothing` 멱등성이 깨진다(#116 1번 A안).
_NAMESPACE = uuid.UUID("698962ec-13f3-46ce-87c3-d57b37d4956a")

# 퀴즈 출제 근거로 쓰는 action (#116 2번). rule_id는 제한하지 않는다 — 이 세
# action을 만드는 규칙이 지금은 R01~R06·R08뿐이라 결과는 같지만, 나중에 규칙이
# 늘어도 코드 변경이 필요 없다.
_CANDIDATE_ACTIONS = ["allowed", "guide_stopped", "detected"]

# 매 틱 조회하는 후보 상한. 실제로 퀴즈를 만드는 건수는 이보다 작은
# config.quiz_batch_size로 더 제한한다.
_LOOKBACK = 200

_CHOICE_COUNT = 4

_RULE_TITLES = {
    "R01": "main에 직접 push",
    "R02": "force push",
    "R03": "비밀 정보 커밋",
    "R04": "main에서 직접 커밋",
    "R05": "브랜치명 규칙 위반",
    "R06": "커밋 메시지 규칙 위반",
    "R07": "되돌리기 어려운 명령",
    "R08": "PR 대상 브랜치 오류",
}

_SYSTEM_PROMPT = (
    "너는 Git을 처음 배우는 학생 팀을 위한 퀴즈를 내는 코치다.\n"
    "아래 '사실'만 근거로 4지선다 퀴즈를 만든다. 사실에 없는 내용과 명령어는 "
    "절대 만들지 않는다. JSON 객체 하나만 출력하고 다른 글자는 쓰지 않는다."
)

_NUM_PREDICT = 400


def quiz_id(source_event_id: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, f"quiz\x1f{source_event_id}"))


def _fetch_candidates(client: Client, config: WatcherConfig) -> list[dict]:
    res = (
        client.table("events")
        .select("id, member, rule_id, command_summary, branch, severity")
        .eq("repo", config.repo)
        .in_("action", _CANDIDATE_ACTIONS)
        .order("occurred_at", desc=True)
        .limit(_LOOKBACK)
        .execute()
    )
    return res.data or []


def _existing_quiz_ids(client: Client, ids: list[str]) -> set[str]:
    if not ids:
        return set()
    res = client.table("quizzes").select("id").in_("id", ids).execute()
    return {row["id"] for row in res.data or []}


def _select_unquizzed(client: Client, config: WatcherConfig) -> list[dict]:
    """아직 퀴즈가 없는 근거 이벤트만 고른다(#116 1번 — id가 결정론적이라 중복
    저장은 안 생기지만, 틱마다 같은 이벤트로 Ollama를 또 호출하지 않으려면
    생성 전에 걸러내는 편이 낫다)."""
    candidates = _fetch_candidates(client, config)
    if not candidates:
        return []
    quiz_ids_by_event = {event["id"]: quiz_id(event["id"]) for event in candidates}
    existing = _existing_quiz_ids(client, list(quiz_ids_by_event.values()))
    unquizzed = [
        event for event in candidates if quiz_ids_by_event[event["id"]] not in existing
    ]
    return unquizzed[: config.quiz_batch_size]


def _resolve_member_id(client: Client, github_login: str) -> str | None:
    res = (
        client.table("members")
        .select("id")
        .eq("github_login", github_login)
        .limit(1)
        .execute()
    )
    return res.data[0]["id"] if res.data else None


def _build_messages(event: dict) -> list[dict]:
    rule_id = event["rule_id"]
    facts = {
        "rule": _RULE_TITLES.get(rule_id, rule_id),
        "command_summary": event.get("command_summary"),
        "branch": event.get("branch"),
        "severity": event.get("severity"),
    }
    user = (
        f"규칙: {facts['rule']}\n"
        f"사실: {json.dumps(facts, ensure_ascii=False)}\n"
        "형식: 아래 JSON 스키마로만 답한다.\n"
        '{"question": "...", "choices": ["...", "...", "...", "..."], '
        '"answer_index": 0, "explanation": "..."}\n'
        f"선택지는 정확히 {_CHOICE_COUNT}개, answer_index는 0~{_CHOICE_COUNT - 1} "
        "중 정답 위치, explanation은 한국어 존댓말 한 문장."
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def _extract_json(text: str) -> str:
    """Ollama가 코드 펜스나 앞뒤 설명을 덧붙여도 중괄호 안쪽만 골라낸다."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return text
    return text[start : end + 1]


def _parse_quiz(text: str) -> quiz_templates.QuizTemplate | None:
    try:
        data = json.loads(_extract_json(text))
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None

    question = data.get("question")
    choices = data.get("choices")
    answer_index = data.get("answer_index")
    explanation = data.get("explanation")

    if not isinstance(question, str) or not question.strip():
        return None
    if not isinstance(choices, list) or len(choices) != _CHOICE_COUNT:
        return None
    if not all(isinstance(c, str) and c.strip() for c in choices):
        return None
    if not isinstance(answer_index, int) or isinstance(answer_index, bool):
        return None
    if not 0 <= answer_index < _CHOICE_COUNT:
        return None
    if not isinstance(explanation, str) or not explanation.strip():
        return None

    return question, choices, answer_index, explanation


def _generate_quiz(config: WatcherConfig, event: dict) -> quiz_templates.QuizTemplate:
    messages = _build_messages(event)
    try:
        text = ollama.ask(
            messages,
            url=config.ollama_url,
            model=config.ollama_model,
            num_predict=_NUM_PREDICT,
        )
    except ollama.OllamaError as exc:
        logger.warning(
            "Ollama 호출 실패, 폴백 문항 사용: rule=%s (%s)", event["rule_id"], exc
        )
        return quiz_templates.fallback(event["rule_id"])

    parsed = _parse_quiz(text)
    if parsed is None:
        logger.warning(
            "Ollama 응답이 퀴즈 형식에 안 맞아 폴백 문항 사용: rule=%s",
            event["rule_id"],
        )
        return quiz_templates.fallback(event["rule_id"])
    return parsed


def generate(client: Client, config: WatcherConfig) -> list[dict]:
    """events에서 아직 퀴즈가 없는 근거 이벤트를 골라 Ollama로 4지선다 퀴즈를
    만든다. 배치 상한(config.quiz_batch_size)만큼만 생성해 한 폴링 틱 안에서
    끝낸다(01_cli.md 5-1절 12번)."""
    candidates = _select_unquizzed(client, config)
    rows = []
    for event in candidates:
        member_id = _resolve_member_id(client, event["member"])
        if member_id is None:
            logger.warning(
                "members에 없는 멤버라 퀴즈를 건너뜀: %s (%s)",
                event["member"],
                event["rule_id"],
            )
            continue

        question, choices, answer_index, explanation = _generate_quiz(config, event)
        rows.append(
            {
                "id": quiz_id(event["id"]),
                "member_id": member_id,
                "rule_id": event["rule_id"],
                "source_event_id": event["id"],
                "question": question,
                "choices": choices,
                "answer_index": answer_index,
                "explanation": explanation,
            }
        )
    return rows
