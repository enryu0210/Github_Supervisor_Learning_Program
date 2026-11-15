import json

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


def test_write_event_creates_file_with_matching_content(tmp_path) -> None:
    event = _make()
    output_dir = tmp_path / "events"
    path = events.write_event(event, output_dir)

    assert path == output_dir / f"{event.id}.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["id"] == event.id
    assert saved["rule_id"] == "R05"
    assert saved["explanation"] == "브랜치명 규칙 위반"


def test_write_event_overwrites_same_file_for_same_event(tmp_path) -> None:
    output_dir = tmp_path / "events"
    first = _make(explanation="첫 감지")
    second = _make(explanation="재감지")

    events.write_event(first, output_dir)
    path = events.write_event(second, output_dir)

    assert len(list(output_dir.iterdir())) == 1
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["explanation"] == "재감지"
