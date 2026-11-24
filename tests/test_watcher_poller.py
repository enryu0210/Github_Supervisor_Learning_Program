import json
import logging
from pathlib import Path

from postgrest.exceptions import APIError

from gitcoach.models import Event
from watcher import db_sink, poller
from watcher.config import WatcherConfig
from watcher.github_client import GitHubClientError

_REPO_ID = "11111111-1111-1111-1111-111111111111"


def _config(
    poll_interval_seconds: int = 7,
    review_concentration_path: Path | None = None,
) -> WatcherConfig:
    return WatcherConfig(
        token="secret-token",
        repo="owner/repo",
        poll_interval_seconds=poll_interval_seconds,
        review_concentration_path=review_concentration_path
        or Path("./review_concentration.json"),
        supabase_url="https://example.supabase.co",
        supabase_service_key="service-key",
    )


def _event(rule_id: str = "R01") -> Event:
    return Event(
        id=f"11111111-1111-1111-1111-{rule_id.lower():0>12}",
        schema_version=1,
        occurred_at="2026-11-16T00:00:00+09:00",
        source="github",
        repo="owner/repo",
        member="hoil-lim",
        rule_id=rule_id,
        severity="high",
        action="detected",
        command_summary=None,
        branch="main",
        explanation="테스트용 감지 이벤트",
    )


def _stub_all(monkeypatch) -> None:
    monkeypatch.setattr(
        poller.github_client, "get_repo", lambda cfg: {"default_branch": "main"}
    )
    monkeypatch.setattr(poller.push_detection, "run", lambda cfg: [])
    monkeypatch.setattr(poller.branch_naming, "run", lambda cfg: [])
    monkeypatch.setattr(poller.pr_base_detection, "run", lambda cfg: [])
    monkeypatch.setattr(poller.commit_message, "run", lambda cfg: [])
    monkeypatch.setattr(poller.db_sink, "upload_events", lambda client, events: None)
    monkeypatch.setattr(poller.quiz_generation, "generate", lambda client, cfg: [])
    monkeypatch.setattr(poller.db_sink, "upload_quizzes", lambda client, rows: None)
    monkeypatch.setattr(poller.review_concentration, "run", lambda cfg: [])
    monkeypatch.setattr(poller.stale_prs, "run", lambda cfg: [])
    monkeypatch.setattr(poller.db_sink, "upload_prs", lambda client, repo_id, prs: {})
    monkeypatch.setattr(poller.pr_reviews, "run", lambda cfg: [])
    monkeypatch.setattr(
        poller.db_sink,
        "upload_pr_reviews",
        lambda client, repo_id, pr_ids, records: None,
    )


def test_poll_once_logs_default_branch(monkeypatch, caplog) -> None:
    _stub_all(monkeypatch)
    with caplog.at_level(logging.INFO, logger="watcher"):
        poller.poll_once(_config(), client=object(), repo_id=_REPO_ID)
    assert "owner/repo" in caplog.text
    assert "main" in caplog.text


def test_poll_once_uploads_detected_events(monkeypatch, caplog) -> None:
    _stub_all(monkeypatch)
    monkeypatch.setattr(poller.push_detection, "run", lambda cfg: [_event("R01")])
    uploaded = []
    monkeypatch.setattr(
        poller.db_sink, "upload_events", lambda client, events: uploaded.extend(events)
    )

    with caplog.at_level(logging.INFO, logger="watcher"):
        poller.poll_once(_config(), client=object(), repo_id=_REPO_ID)

    assert [e.rule_id for e in uploaded] == ["R01"]
    assert "1건" in caplog.text


def test_poll_once_skips_events_upload_when_no_violations(monkeypatch) -> None:
    _stub_all(monkeypatch)
    calls = []
    monkeypatch.setattr(
        poller.db_sink, "upload_events", lambda client, events: calls.append(events)
    )

    poller.poll_once(_config(), client=object(), repo_id=_REPO_ID)

    assert calls == []


def test_poll_once_aggregates_events_from_all_detectors(monkeypatch) -> None:
    _stub_all(monkeypatch)
    monkeypatch.setattr(poller.push_detection, "run", lambda cfg: [_event("R01")])
    monkeypatch.setattr(poller.branch_naming, "run", lambda cfg: [_event("R05")])
    monkeypatch.setattr(poller.pr_base_detection, "run", lambda cfg: [_event("R08")])
    monkeypatch.setattr(poller.commit_message, "run", lambda cfg: [_event("R06")])
    uploaded = []
    monkeypatch.setattr(
        poller.db_sink, "upload_events", lambda client, events: uploaded.extend(events)
    )

    poller.poll_once(_config(), client=object(), repo_id=_REPO_ID)

    assert {e.rule_id for e in uploaded} == {"R01", "R05", "R08", "R06"}


def test_poll_once_continues_when_events_upload_fails(monkeypatch, caplog) -> None:
    _stub_all(monkeypatch)
    monkeypatch.setattr(poller.push_detection, "run", lambda cfg: [_event("R01")])

    def raise_db_error(client, events):
        raise db_sink.DbSinkError("boom")

    monkeypatch.setattr(poller.db_sink, "upload_events", raise_db_error)
    prs_calls = []
    monkeypatch.setattr(
        poller.db_sink,
        "upload_prs",
        lambda client, repo_id, prs: prs_calls.append(prs) or {},
    )

    with caplog.at_level(logging.WARNING, logger="watcher"):
        poller.poll_once(_config(), client=object(), repo_id=_REPO_ID)

    assert "boom" in caplog.text
    assert prs_calls == [[]]


def test_poll_once_uploads_generated_quizzes(monkeypatch, caplog) -> None:
    _stub_all(monkeypatch)
    quiz_row = {"id": "quiz-uuid", "rule_id": "R01"}
    monkeypatch.setattr(
        poller.quiz_generation, "generate", lambda client, cfg: [quiz_row]
    )
    uploaded = []
    monkeypatch.setattr(
        poller.db_sink, "upload_quizzes", lambda client, rows: uploaded.extend(rows)
    )

    with caplog.at_level(logging.INFO, logger="watcher"):
        poller.poll_once(_config(), client=object(), repo_id=_REPO_ID)

    assert uploaded == [quiz_row]
    assert "1건" in caplog.text


def test_poll_once_skips_quiz_upload_when_no_quizzes_generated(monkeypatch) -> None:
    _stub_all(monkeypatch)
    calls = []
    monkeypatch.setattr(
        poller.db_sink, "upload_quizzes", lambda client, rows: calls.append(rows)
    )

    poller.poll_once(_config(), client=object(), repo_id=_REPO_ID)

    assert calls == []


def test_poll_once_continues_when_quiz_upload_fails(monkeypatch, caplog) -> None:
    _stub_all(monkeypatch)
    monkeypatch.setattr(
        poller.quiz_generation, "generate", lambda client, cfg: [{"id": "quiz-uuid"}]
    )

    def raise_db_error(client, rows):
        raise db_sink.DbSinkError("quiz boom")

    monkeypatch.setattr(poller.db_sink, "upload_quizzes", raise_db_error)

    with caplog.at_level(logging.WARNING, logger="watcher"):
        poller.poll_once(_config(), client=object(), repo_id=_REPO_ID)

    assert "quiz boom" in caplog.text


def test_poll_once_continues_when_quiz_generation_raises_api_error(
    monkeypatch, caplog
) -> None:
    """퀴즈 생성 중 Supabase APIError가 나도 그 틱의 나머지 단계(리뷰 쏠림·
    prs·pr_reviews)는 계속 돌아야 한다(#133 리뷰 2번)."""
    _stub_all(monkeypatch)

    def raise_api_error(client, cfg):
        raise APIError({"message": "quiz query boom"})

    monkeypatch.setattr(poller.quiz_generation, "generate", raise_api_error)
    prs_calls = []
    monkeypatch.setattr(
        poller.db_sink,
        "upload_prs",
        lambda client, repo_id, prs: prs_calls.append(prs) or {},
    )

    with caplog.at_level(logging.WARNING, logger="watcher"):
        poller.poll_once(_config(), client=object(), repo_id=_REPO_ID)

    assert "quiz query boom" in caplog.text
    assert prs_calls == [[]]


def test_poll_once_generates_quizzes_even_when_prs_upload_fails(monkeypatch) -> None:
    _stub_all(monkeypatch)
    monkeypatch.setattr(
        poller.db_sink,
        "upload_prs",
        lambda client, repo_id, prs: (_ for _ in ()).throw(db_sink.DbSinkError("x")),
    )
    quiz_calls = []
    monkeypatch.setattr(
        poller.quiz_generation,
        "generate",
        lambda client, cfg: quiz_calls.append(cfg) or [],
    )

    poller.poll_once(_config(), client=object(), repo_id=_REPO_ID)

    assert len(quiz_calls) == 1


def test_poll_once_uploads_prs_with_repo_id(monkeypatch) -> None:
    _stub_all(monkeypatch)
    pr_record = {"number": 1, "state": "open"}
    monkeypatch.setattr(poller.stale_prs, "run", lambda cfg: [pr_record])
    calls = []
    monkeypatch.setattr(
        poller.db_sink,
        "upload_prs",
        lambda client, repo_id, prs: calls.append((repo_id, prs)) or {},
    )

    poller.poll_once(_config(), client=object(), repo_id=_REPO_ID)

    assert calls == [(_REPO_ID, [pr_record])]


def test_poll_once_skips_pr_reviews_when_prs_upload_fails(monkeypatch, caplog) -> None:
    _stub_all(monkeypatch)

    def raise_db_error(client, repo_id, prs):
        raise db_sink.DbSinkError("prs boom")

    monkeypatch.setattr(poller.db_sink, "upload_prs", raise_db_error)
    pr_reviews_run_called = []
    monkeypatch.setattr(
        poller.pr_reviews, "run", lambda cfg: pr_reviews_run_called.append(cfg) or []
    )

    with caplog.at_level(logging.WARNING, logger="watcher"):
        poller.poll_once(_config(), client=object(), repo_id=_REPO_ID)

    assert "prs boom" in caplog.text
    assert pr_reviews_run_called == []


def test_poll_once_uploads_pr_reviews_with_resolved_pr_ids(monkeypatch) -> None:
    _stub_all(monkeypatch)
    monkeypatch.setattr(
        poller.db_sink, "upload_prs", lambda client, repo_id, prs: {1: "pr-uuid"}
    )
    review_record = {"review_id": 1, "pr_number": 1}
    monkeypatch.setattr(poller.pr_reviews, "run", lambda cfg: [review_record])
    calls = []
    monkeypatch.setattr(
        poller.db_sink,
        "upload_pr_reviews",
        lambda client, repo_id, pr_ids, records: calls.append(
            (repo_id, pr_ids, records)
        ),
    )

    poller.poll_once(_config(), client=object(), repo_id=_REPO_ID)

    assert calls == [(_REPO_ID, {1: "pr-uuid"}, [review_record])]


def test_poll_once_writes_review_concentration_snapshot(
    monkeypatch, caplog, tmp_path
) -> None:
    _stub_all(monkeypatch)
    summary = [{"reviewer": "hoil-lim", "review_count": 3, "share": 1.0}]
    monkeypatch.setattr(poller.review_concentration, "run", lambda cfg: summary)

    review_path = tmp_path / "review_concentration.json"
    with caplog.at_level(logging.INFO, logger="watcher"):
        poller.poll_once(
            _config(review_concentration_path=review_path),
            client=object(),
            repo_id=_REPO_ID,
        )

    assert json.loads(review_path.read_text(encoding="utf-8")) == summary
    assert "1명" in caplog.text


def test_run_forever_resolves_client_and_repo_id_once_when_not_provided(
    monkeypatch,
) -> None:
    sentinel_client = object()
    resolve_calls = []
    create_calls = []
    monkeypatch.setattr(
        poller.db_sink,
        "create_client_from_config",
        lambda cfg: create_calls.append(cfg) or sentinel_client,
    )
    monkeypatch.setattr(
        poller.db_sink,
        "resolve_repo_id",
        lambda client, repo: resolve_calls.append((client, repo)) or _REPO_ID,
    )
    poll_calls = []
    monkeypatch.setattr(
        poller,
        "poll_once",
        lambda cfg, client, repo_id: poll_calls.append((client, repo_id)),
    )

    poller.run_forever(_config(), sleep=lambda s: None, max_iterations=3)

    assert create_calls == [_config()]
    assert resolve_calls == [(sentinel_client, "owner/repo")]
    assert poll_calls == [(sentinel_client, _REPO_ID)] * 3


def test_run_forever_uses_provided_client_without_creating_one(monkeypatch) -> None:
    provided_client = object()
    create_calls = []
    monkeypatch.setattr(
        poller.db_sink,
        "create_client_from_config",
        lambda cfg: create_calls.append(cfg) or object(),
    )
    monkeypatch.setattr(
        poller.db_sink, "resolve_repo_id", lambda client, repo: _REPO_ID
    )
    monkeypatch.setattr(poller, "poll_once", lambda cfg, client, repo_id: None)

    poller.run_forever(
        _config(), sleep=lambda s: None, max_iterations=1, client=provided_client
    )

    assert create_calls == []


def test_run_forever_sleeps_between_ticks(monkeypatch) -> None:
    monkeypatch.setattr(
        poller.db_sink, "create_client_from_config", lambda cfg: object()
    )
    monkeypatch.setattr(
        poller.db_sink, "resolve_repo_id", lambda client, repo: _REPO_ID
    )
    monkeypatch.setattr(poller, "poll_once", lambda cfg, client, repo_id: None)
    sleeps = []
    poller.run_forever(
        _config(poll_interval_seconds=42), sleep=sleeps.append, max_iterations=3
    )
    assert sleeps == [42, 42, 42]


def test_run_forever_continues_after_poll_failure(monkeypatch, caplog) -> None:
    monkeypatch.setattr(
        poller.db_sink, "create_client_from_config", lambda cfg: object()
    )
    monkeypatch.setattr(
        poller.db_sink, "resolve_repo_id", lambda client, repo: _REPO_ID
    )
    calls = []

    def fake_poll_once(cfg, client, repo_id):
        calls.append(cfg)
        raise GitHubClientError("boom")

    monkeypatch.setattr(poller, "poll_once", fake_poll_once)
    with caplog.at_level(logging.WARNING, logger="watcher"):
        poller.run_forever(_config(), sleep=lambda s: None, max_iterations=2)

    assert len(calls) == 2
    assert "boom" in caplog.text


def test_run_forever_continues_after_unexpected_error(monkeypatch, caplog) -> None:
    monkeypatch.setattr(
        poller.db_sink, "create_client_from_config", lambda cfg: object()
    )
    monkeypatch.setattr(
        poller.db_sink, "resolve_repo_id", lambda client, repo: _REPO_ID
    )
    calls = []

    def fake_poll_once(cfg, client, repo_id):
        calls.append(cfg)
        raise ValueError("unexpected")

    monkeypatch.setattr(poller, "poll_once", fake_poll_once)
    with caplog.at_level(logging.ERROR, logger="watcher"):
        poller.run_forever(_config(), sleep=lambda s: None, max_iterations=2)

    assert len(calls) == 2
    assert "unexpected" in caplog.text
