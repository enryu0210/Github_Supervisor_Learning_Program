from pathlib import Path

from watcher import stale_prs
from watcher.config import WatcherConfig


def _config() -> WatcherConfig:
    return WatcherConfig(
        token="secret-token",
        repo="owner/repo",
        poll_interval_seconds=300,
        review_concentration_path=Path("./review_concentration.json"),
        supabase_url="https://example.supabase.co",
        supabase_service_key="service-key",
    )


def _pr(
    *,
    number: int = 1,
    title: str = "feat(cli): 예시 PR",
    author: str = "Hoil-Lim",
    state: str = "open",
    created_at: str = "2026-11-10T09:12:00Z",
    updated_at: str = "2026-11-10T09:12:00Z",
    merged_at: str | None = None,
    reviewers: list[str] | None = None,
) -> dict:
    pr = {
        "number": number,
        "title": title,
        "user": {"login": author},
        "state": state,
        "created_at": created_at,
        "updated_at": updated_at,
        "merged_at": merged_at,
    }
    if reviewers is not None:
        pr["requested_reviewers"] = [{"login": login} for login in reviewers]
    return pr


def test_to_pr_record_maps_open_pr_fields() -> None:
    record = stale_prs.to_pr_record(
        "Owner/Repo",
        _pr(reviewers=["Leafbell-Sii"], updated_at="2026-11-10T11:00:00Z"),
    )

    assert record == {
        "repo": "owner/repo",
        "number": 1,
        "title": "feat(cli): 예시 PR",
        "author": "hoil-lim",
        "state": "open",
        "opened_at": "2026-11-10T09:12:00Z",
        "merged_at": None,
        "reviewers": ["leafbell-sii"],
        "last_activity_at": "2026-11-10T11:00:00Z",
    }


def test_to_pr_record_keeps_merged_at_for_merged_pr() -> None:
    record = stale_prs.to_pr_record(
        "owner/repo",
        _pr(state="closed", merged_at="2026-11-07T10:30:00Z", reviewers=[]),
    )

    assert record["state"] == "closed"
    assert record["merged_at"] == "2026-11-07T10:30:00Z"


def test_to_pr_record_null_merged_at_for_closed_without_merge() -> None:
    record = stale_prs.to_pr_record("owner/repo", _pr(state="closed", reviewers=[]))

    assert record["state"] == "closed"
    assert record["merged_at"] is None


def test_to_pr_record_defaults_reviewers_to_empty_list_when_missing() -> None:
    record = stale_prs.to_pr_record("owner/repo", _pr())

    assert record["reviewers"] == []


def test_to_pr_record_uses_last_updated_at_as_last_activity() -> None:
    record = stale_prs.to_pr_record(
        "owner/repo",
        _pr(created_at="2026-11-07T16:40:00Z", updated_at="2026-11-07T17:00:00Z"),
    )

    assert record["opened_at"] == "2026-11-07T16:40:00Z"
    assert record["last_activity_at"] == "2026-11-07T17:00:00Z"


def test_run_maps_every_pull(monkeypatch) -> None:
    monkeypatch.setattr(
        stale_prs.github_client,
        "list_all_pulls",
        lambda cfg: [_pr(number=1), _pr(number=2, state="closed")],
    )

    records = stale_prs.run(_config())

    assert [r["number"] for r in records] == [1, 2]
    assert records[1]["state"] == "closed"


def test_run_returns_empty_for_no_pulls(monkeypatch) -> None:
    monkeypatch.setattr(stale_prs.github_client, "list_all_pulls", lambda cfg: [])

    assert stale_prs.run(_config()) == []
