from watcher import events


def _make(**overrides):
    kwargs = {
        "rule_id": "R05",
        "severity": "low",
        "repo": "owner/repo",
        "member": "hoil-lim",
        "branch": "Feature_Login",
        "entity": "Feature_Login",
        "explanation": "브랜치명 규칙 위반",
    }
    kwargs.update(overrides)
    return events.make_detected_event(**kwargs)


def test_make_detected_event_id_is_deterministic() -> None:
    first = _make()
    second = _make()
    assert first.id == second.id


def test_make_detected_event_id_changes_with_entity() -> None:
    first = _make(entity="Feature_Login")
    second = _make(entity="Feature_Signup")
    assert first.id != second.id


def test_make_detected_event_id_changes_with_rule_id() -> None:
    first = _make(rule_id="R05")
    second = _make(rule_id="R06")
    assert first.id != second.id


def test_make_detected_event_id_changes_with_repo() -> None:
    first = _make(repo="owner/repo")
    second = _make(repo="owner/other-repo")
    assert first.id != second.id


def test_make_detected_event_normalizes_repo_and_member() -> None:
    event = _make(repo="Owner/Repo", member="Hoil-Lim")
    assert event.repo == "owner/repo"
    assert event.member == "hoil-lim"


def test_make_detected_event_fixed_fields() -> None:
    event = _make()
    assert event.schema_version == 1
    assert event.source == "github"
    assert event.action == "detected"
    assert event.command_summary is None
    assert event.llm_used is False
    assert event.related_event_id is None


def test_make_detected_event_uses_provided_occurred_at() -> None:
    event = _make(occurred_at="2026-11-01T09:00:00+09:00")
    assert event.occurred_at == "2026-11-01T09:00:00+09:00"


def test_make_detected_event_defaults_occurred_at_to_now() -> None:
    event = _make()
    assert event.occurred_at is not None
    # 감지 시각 기본값이 살아있는지만 확인 — 정확한 현재 시각 비교는 불안정하다.
    assert "T" in event.occurred_at
