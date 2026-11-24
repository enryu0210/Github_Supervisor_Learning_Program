import json
import logging
from pathlib import Path

from gitcoach.explain.ollama import OllamaError
from watcher import quiz_generation, quiz_templates
from watcher.config import WatcherConfig


class _FakeResult:
    def __init__(self, data) -> None:
        self.data = data


class _FakeTable:
    def __init__(self, client: "_FakeClient", name: str) -> None:
        self._client = client
        self._name = name
        self._filters: dict = {}
        self._in_filters: dict = {}
        self._order = None
        self._limit = None

    def select(self, *_columns) -> "_FakeTable":
        return self

    def eq(self, column: str, value) -> "_FakeTable":
        self._filters[column] = value
        return self

    def in_(self, column: str, values) -> "_FakeTable":
        self._in_filters[column] = list(values)
        return self

    def order(self, column: str, desc: bool = False) -> "_FakeTable":
        self._order = (column, desc)
        return self

    def limit(self, n: int) -> "_FakeTable":
        self._limit = n
        return self

    def execute(self) -> _FakeResult:
        self._client.calls.append(
            {
                "table": self._name,
                "filters": dict(self._filters),
                "in_filters": dict(self._in_filters),
                "order": self._order,
                "limit": self._limit,
            }
        )
        response = self._client.responses[self._name].pop(0)
        if isinstance(response, Exception):
            raise response
        return _FakeResult(response)


class _FakeClient:
    def __init__(self, responses: dict[str, list]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    def table(self, name: str) -> _FakeTable:
        return _FakeTable(self, name)


def _config(quiz_batch_size: int = 10) -> WatcherConfig:
    return WatcherConfig(
        token="secret-token",
        repo="owner/repo",
        poll_interval_seconds=300,
        review_concentration_path=Path("./review_concentration.json"),
        supabase_url="https://example.supabase.co",
        supabase_service_key="service-key",
        ollama_url="http://localhost:11434",
        ollama_model="gemma4:e2b",
        quiz_batch_size=quiz_batch_size,
    )


def _event(
    *,
    event_id: str = "event-1",
    rule_id: str = "R01",
    member: str = "hoil-lim",
    command_summary: str | None = "git push origin main",
    branch: str = "main",
    severity: str = "high",
) -> dict:
    return {
        "id": event_id,
        "member": member,
        "rule_id": rule_id,
        "command_summary": command_summary,
        "branch": branch,
        "severity": severity,
    }


_VALID_QUIZ_JSON = json.dumps(
    {
        "question": "main에 직접 push하면?",
        "choices": ["A", "B", "C", "D"],
        "answer_index": 1,
        "explanation": "설명입니다.",
    },
    ensure_ascii=False,
)


# ---------------------------------------------------------------- quiz_id


def test_quiz_id_is_deterministic_for_same_event() -> None:
    assert quiz_generation.quiz_id("event-1") == quiz_generation.quiz_id("event-1")


def test_quiz_id_differs_for_different_events() -> None:
    assert quiz_generation.quiz_id("event-1") != quiz_generation.quiz_id("event-2")


# ---------------------------------------------------------------- _select_unquizzed


def test_select_unquizzed_filters_out_events_with_existing_quiz() -> None:
    event_a = _event(event_id="event-1")
    event_b = _event(event_id="event-2")
    existing_id = quiz_generation.quiz_id("event-1")
    client = _FakeClient(
        {"events": [[event_a, event_b]], "quizzes": [[{"id": existing_id}]]}
    )

    result = quiz_generation._select_unquizzed(client, _config())

    assert [e["id"] for e in result] == ["event-2"]


def test_select_unquizzed_skips_quiz_lookup_when_no_candidates() -> None:
    client = _FakeClient({"events": [[]]})

    result = quiz_generation._select_unquizzed(client, _config())

    assert result == []
    assert all(call["table"] != "quizzes" for call in client.calls)


def test_select_unquizzed_respects_batch_size() -> None:
    events = [_event(event_id="event-1"), _event(event_id="event-2")]
    client = _FakeClient({"events": [events], "quizzes": [[]]})

    result = quiz_generation._select_unquizzed(client, _config(quiz_batch_size=1))

    assert [e["id"] for e in result] == ["event-1"]


def test_fetch_candidates_filters_by_repo_and_action() -> None:
    client = _FakeClient({"events": [[]]})

    quiz_generation._fetch_candidates(client, _config())

    call = client.calls[0]
    assert call["filters"] == {"repo": "owner/repo"}
    assert call["in_filters"] == {"action": ["allowed", "guide_stopped", "detected"]}


# ---------------------------------------------------------------- _parse_quiz


def test_parse_quiz_accepts_valid_json() -> None:
    parsed = quiz_generation._parse_quiz(_VALID_QUIZ_JSON)
    assert parsed == ("main에 직접 push하면?", ["A", "B", "C", "D"], 1, "설명입니다.")


def test_parse_quiz_extracts_json_from_code_fence() -> None:
    fenced = f"```json\n{_VALID_QUIZ_JSON}\n```"
    assert quiz_generation._parse_quiz(fenced) is not None


def test_parse_quiz_rejects_non_json() -> None:
    assert quiz_generation._parse_quiz("이건 json이 아니에요") is None


def test_parse_quiz_rejects_wrong_choice_count() -> None:
    data = json.dumps(
        {
            "question": "q",
            "choices": ["A", "B", "C"],
            "answer_index": 0,
            "explanation": "e",
        }
    )
    assert quiz_generation._parse_quiz(data) is None


def test_parse_quiz_rejects_out_of_range_answer_index() -> None:
    data = json.dumps(
        {
            "question": "q",
            "choices": ["A", "B", "C", "D"],
            "answer_index": 4,
            "explanation": "e",
        }
    )
    assert quiz_generation._parse_quiz(data) is None


def test_parse_quiz_rejects_boolean_answer_index() -> None:
    data = json.dumps(
        {
            "question": "q",
            "choices": ["A", "B", "C", "D"],
            "answer_index": True,
            "explanation": "e",
        }
    )
    assert quiz_generation._parse_quiz(data) is None


def test_parse_quiz_rejects_empty_explanation() -> None:
    data = json.dumps(
        {
            "question": "q",
            "choices": ["A", "B", "C", "D"],
            "answer_index": 0,
            "explanation": "",
        }
    )
    assert quiz_generation._parse_quiz(data) is None


# ---------------------------------------------------------------- generate


def test_generate_builds_row_from_ollama_response(monkeypatch) -> None:
    client = _FakeClient(
        {
            "events": [[_event()]],
            "quizzes": [[]],
            "members": [[{"id": "member-uuid"}]],
        }
    )
    ask_calls = []
    monkeypatch.setattr(
        quiz_generation.ollama,
        "ask",
        lambda messages, **kw: ask_calls.append(kw) or _VALID_QUIZ_JSON,
    )

    rows = quiz_generation.generate(client, _config())

    assert rows == [
        {
            "id": quiz_generation.quiz_id("event-1"),
            "member_id": "member-uuid",
            "rule_id": "R01",
            "source_event_id": "event-1",
            "question": "main에 직접 push하면?",
            "choices": ["A", "B", "C", "D"],
            "answer_index": 1,
            "explanation": "설명입니다.",
        }
    ]
    assert ask_calls == [
        {
            "url": "http://localhost:11434",
            "model": "gemma4:e2b",
            "num_predict": 400,
            "timeout": 30.0,
        }
    ]


def test_generate_skips_event_when_member_not_registered(caplog) -> None:
    client = _FakeClient(
        {"events": [[_event(member="unknown-user")]], "quizzes": [[]], "members": [[]]}
    )

    with caplog.at_level(logging.WARNING, logger="watcher"):
        rows = quiz_generation.generate(client, _config())

    assert rows == []
    assert "unknown-user" in caplog.text


def test_generate_skips_event_on_ollama_error(caplog, monkeypatch) -> None:
    """호출 자체가 실패하면 폴백으로 영구 고정하지 않고 다음 주기에 다시
    시도하도록 이번 틱엔 행을 만들지 않는다(#133 리뷰 1번)."""
    client = _FakeClient(
        {
            "events": [[_event(rule_id="R02")]],
            "quizzes": [[]],
            "members": [[{"id": "member-uuid"}]],
        }
    )
    monkeypatch.setattr(
        quiz_generation.ollama,
        "ask",
        lambda messages, **kw: (_ for _ in ()).throw(OllamaError("boom")),
    )

    with caplog.at_level(logging.WARNING, logger="watcher"):
        rows = quiz_generation.generate(client, _config())

    assert rows == []
    assert "재시도" in caplog.text


def test_generate_falls_back_on_malformed_ollama_response(monkeypatch) -> None:
    client = _FakeClient(
        {
            "events": [[_event(rule_id="R05")]],
            "quizzes": [[]],
            "members": [[{"id": "member-uuid"}]],
        }
    )
    monkeypatch.setattr(quiz_generation.ollama, "ask", lambda messages, **kw: "garbage")

    rows = quiz_generation.generate(client, _config())

    question, _choices, _answer_index, _explanation = quiz_templates.fallback("R05")
    assert rows[0]["question"] == question


def test_generate_returns_empty_list_when_no_candidates() -> None:
    client = _FakeClient({"events": [[]]})

    rows = quiz_generation.generate(client, _config())

    assert rows == []
