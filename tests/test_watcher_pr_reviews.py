import json
from pathlib import Path

from watcher import pr_reviews
from watcher.config import WatcherConfig


def _config() -> WatcherConfig:
    return WatcherConfig(
        token="secret-token",
        repo="owner/repo",
        poll_interval_seconds=300,
        events_dir=Path("./events"),
        prs_path=Path("./prs.json"),
        review_concentration_path=Path("./review_concentration.json"),
        pr_reviews_path=Path("./pr_reviews.json"),
    )


def _review(
    *,
    review_id: int = 5001,
    login: str = "Leafbell-Sii",
    state: str = "APPROVED",
    submitted_at: str = "2026-11-10T11:00:00Z",
    commit_id: str = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345670",
    html_url: str = "https://github.com/owner/repo/pull/1#pullrequestreview-5001",
) -> dict:
    return {
        "id": review_id,
        "user": {"login": login},
        "state": state,
        "submitted_at": submitted_at,
        "commit_id": commit_id,
        "html_url": html_url,
        "body": "본문은 저장 대상이 아님",
    }


def test_to_pr_review_record_maps_fields_and_drops_body() -> None:
    record = pr_reviews.to_pr_review_record(
        "Owner/Repo", 101, _review(login="Leafbell-Sii")
    )

    assert record == {
        "review_id": 5001,
        "repo": "owner/repo",
        "pr_number": 101,
        "reviewer": "leafbell-sii",
        "status": "APPROVED",
        "submitted_at": "2026-11-10T11:00:00Z",
        "commit_sha": "a1b2c3d4e5f60718293a4b5c6d7e8f9012345670",
        "html_url": "https://github.com/owner/repo/pull/1#pullrequestreview-5001",
    }
    assert "body" not in record


def test_is_submitted_drops_pending() -> None:
    assert pr_reviews._is_submitted(_review(state="APPROVED")) is True
    assert pr_reviews._is_submitted(_review(state="PENDING")) is False


def test_run_aggregates_and_filters_pending_across_pulls(monkeypatch) -> None:
    monkeypatch.setattr(
        pr_reviews.github_client,
        "list_all_pulls",
        lambda cfg: [{"number": 1}, {"number": 2}],
    )

    def fake_list_pull_reviews(cfg, number):
        return {
            1: [
                _review(review_id=1, login="enryu0210"),
                _review(review_id=2, login="enryu0210", state="PENDING"),
            ],
            2: [_review(review_id=3, login="leafbell-sii")],
        }[number]

    monkeypatch.setattr(
        pr_reviews.github_client, "list_pull_reviews", fake_list_pull_reviews
    )

    records = pr_reviews.run(_config())

    assert [r["review_id"] for r in records] == [1, 3]
    assert [r["pr_number"] for r in records] == [1, 2]


def test_run_returns_empty_for_no_pulls(monkeypatch) -> None:
    monkeypatch.setattr(pr_reviews.github_client, "list_all_pulls", lambda cfg: [])

    assert pr_reviews.run(_config()) == []


def test_write_snapshot_creates_parent_dir_and_writes_array(tmp_path) -> None:
    path = tmp_path / "nested" / "pr_reviews.json"
    records = [pr_reviews.to_pr_review_record("owner/repo", 1, _review())]

    result = pr_reviews.write_snapshot(records, path)

    assert result == path
    assert json.loads(path.read_text(encoding="utf-8")) == records


def test_write_snapshot_overwrites_existing_file(tmp_path) -> None:
    path = tmp_path / "pr_reviews.json"
    path.write_text(json.dumps([{"review_id": 999}]), encoding="utf-8")

    pr_reviews.write_snapshot([], path)

    assert json.loads(path.read_text(encoding="utf-8")) == []
