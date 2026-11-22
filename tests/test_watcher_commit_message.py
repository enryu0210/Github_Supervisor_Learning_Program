from pathlib import Path

from watcher import commit_message
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


def _pr(*, number: int = 1, head: str = "feature/cli-x") -> dict:
    return {"number": number, "head": {"ref": head}}


def _commit(
    *,
    sha: str = "a" * 40,
    message: str,
    author: str | None = "hoil-lim",
    parents: list[dict] | None = None,
    committer_date: str = "2026-11-16T03:00:00Z",
) -> dict:
    return {
        "sha": sha,
        "commit": {
            "message": message,
            "committer": {"date": committer_date},
        },
        "author": {"login": author} if author is not None else None,
        "parents": parents if parents is not None else [{"sha": "p" * 40}],
    }


def test_check_commit_flags_invalid_message() -> None:
    event = commit_message.check_commit(
        "owner/repo",
        _pr(number=42, head="feature/db-schema-update"),
        _commit(message="fix login"),
    )

    assert event is not None
    assert event.rule_id == "R06"
    assert event.severity == "low"
    assert event.branch == "feature/db-schema-update"
    assert event.pr_number == 42
    assert event.member == "hoil-lim"
    assert "42" in event.explanation
    assert event.occurred_at == "2026-11-16T03:00:00Z"


def test_check_commit_uses_sha_as_entity_via_idempotent_id() -> None:
    sha = "b" * 40
    event = commit_message.check_commit(
        "owner/repo", _pr(number=1), _commit(sha=sha, message="fix login")
    )
    other = commit_message.check_commit(
        "owner/repo", _pr(number=1), _commit(sha=sha, message="fix login")
    )

    assert event is not None
    assert event.id == other.id


def test_check_commit_skips_valid_message() -> None:
    event = commit_message.check_commit(
        "owner/repo", _pr(), _commit(message="feat(cli): add x")
    )

    assert event is None


def test_check_commit_skips_valid_subject_with_body() -> None:
    # 실제 PR #101 커밋과 같은 형태: 제목줄은 규칙에 맞고 뒤에 본문이 붙는다.
    # 본문까지 통째로 검사하면 정상 커밋이 위반으로 잘못 걸린다.
    message = (
        "feat(watcher): PR base(R08) 감지\n\n"
        "열린 PR 목록을 조회해 head가 release/*가 아닌데 base가 develop이 아니면\n"
        "R08 detected 이벤트로 남긴다.\n\n"
        "Refs #100"
    )
    event = commit_message.check_commit("owner/repo", _pr(), _commit(message=message))

    assert event is None


def test_check_commit_flags_invalid_subject_even_with_valid_looking_body() -> None:
    message = "fix login\n\nfeat(cli): this line is in the body, not the subject"
    event = commit_message.check_commit("owner/repo", _pr(), _commit(message=message))

    assert event is not None


def test_check_commit_skips_merge_commit_with_multiple_parents() -> None:
    event = commit_message.check_commit(
        "owner/repo",
        _pr(),
        _commit(
            message="Merge branch 'develop' into feature/x",
            parents=[{"sha": "p" * 40}, {"sha": "q" * 40}],
        ),
    )

    assert event is None


def test_check_commit_flags_empty_message_without_crashing() -> None:
    event = commit_message.check_commit("owner/repo", _pr(), _commit(message=""))

    assert event is not None


def test_check_commit_member_fallback_when_author_is_null() -> None:
    event = commit_message.check_commit(
        "owner/repo", _pr(), _commit(message="fix login", author=None)
    )

    assert event is not None
    assert event.member == "unknown"


def test_check_commit_member_fallback_when_author_missing() -> None:
    pr = _pr()
    commit = {
        "sha": "c" * 40,
        "commit": {
            "message": "fix login",
            "committer": {"date": "2026-11-16T03:00:00Z"},
        },
    }

    event = commit_message.check_commit("owner/repo", pr, commit)

    assert event is not None
    assert event.member == "unknown"


def test_run_aggregates_only_violations_across_prs(monkeypatch) -> None:
    monkeypatch.setattr(
        commit_message.github_client,
        "list_open_pulls",
        lambda cfg: [
            _pr(number=1, head="feature/cli-x"),
            _pr(number=2, head="fix/cli-y"),
        ],
    )

    def fake_list_pull_commits(cfg, number):
        if number == 1:
            return [
                _commit(sha="a" * 40, message="feat(cli): ok"),
                _commit(sha="b" * 40, message="bad message"),
            ]
        return [_commit(sha="c" * 40, message="also bad")]

    monkeypatch.setattr(
        commit_message.github_client, "list_pull_commits", fake_list_pull_commits
    )

    violations = commit_message.run(_config())

    assert len(violations) == 2
    assert {v.pr_number for v in violations} == {1, 2}


def test_run_returns_empty_for_no_open_pulls(monkeypatch) -> None:
    monkeypatch.setattr(commit_message.github_client, "list_open_pulls", lambda cfg: [])

    assert commit_message.run(_config()) == []
