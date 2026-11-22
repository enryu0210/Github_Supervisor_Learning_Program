import json
from pathlib import Path

from watcher import review_concentration
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


def _review(login: str = "leafbell-sii", state: str = "APPROVED") -> dict:
    return {"user": {"login": login}, "state": state}


def test_submitted_reviews_drops_pending() -> None:
    reviews = [_review(state="APPROVED"), _review(state="PENDING")]

    result = review_concentration._submitted_reviews(reviews)

    assert [r["state"] for r in result] == ["APPROVED"]


def test_count_by_reviewer_lowercases_login_and_counts() -> None:
    reviews = [
        _review(login="Leafbell-Sii"),
        _review(login="leafbell-sii"),
        _review(login="enryu0210"),
    ]

    counts = review_concentration.count_by_reviewer(reviews)

    assert counts == {"leafbell-sii": 2, "enryu0210": 1}


def test_to_summary_computes_share_sorted_by_reviewer() -> None:
    summary = review_concentration.to_summary({"leafbell-sii": 3, "enryu0210": 1})

    assert summary == [
        {"reviewer": "enryu0210", "review_count": 1, "share": 0.25},
        {"reviewer": "leafbell-sii", "review_count": 3, "share": 0.75},
    ]


def test_to_summary_returns_empty_list_for_no_reviews() -> None:
    assert review_concentration.to_summary({}) == []


def test_run_aggregates_reviews_across_pulls(monkeypatch) -> None:
    monkeypatch.setattr(
        review_concentration.github_client,
        "list_all_pulls",
        lambda cfg: [{"number": 1}, {"number": 2}],
    )

    def fake_list_pull_reviews(cfg, number):
        return {
            1: [
                _review(login="enryu0210"),
                _review(login="enryu0210", state="PENDING"),
            ],
            2: [_review(login="leafbell-sii")],
        }[number]

    monkeypatch.setattr(
        review_concentration.github_client, "list_pull_reviews", fake_list_pull_reviews
    )

    summary = review_concentration.run(_config())

    assert summary == [
        {"reviewer": "enryu0210", "review_count": 1, "share": 0.5},
        {"reviewer": "leafbell-sii", "review_count": 1, "share": 0.5},
    ]


def test_run_returns_empty_for_no_pulls(monkeypatch) -> None:
    monkeypatch.setattr(
        review_concentration.github_client, "list_all_pulls", lambda cfg: []
    )

    assert review_concentration.run(_config()) == []


def test_write_snapshot_creates_parent_dir_and_writes_array(tmp_path) -> None:
    path = tmp_path / "nested" / "review_concentration.json"
    records = [{"reviewer": "enryu0210", "review_count": 1, "share": 1.0}]

    result = review_concentration.write_snapshot(records, path)

    assert result == path
    assert json.loads(path.read_text(encoding="utf-8")) == records


def test_write_snapshot_overwrites_existing_file(tmp_path) -> None:
    path = tmp_path / "review_concentration.json"
    path.write_text(json.dumps([{"reviewer": "old"}]), encoding="utf-8")

    review_concentration.write_snapshot([], path)

    assert json.loads(path.read_text(encoding="utf-8")) == []
