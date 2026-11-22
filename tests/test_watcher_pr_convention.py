import io

from watcher import pr_convention

_OK_TITLE = "ci(infra): 워크플로 6개로 정리"


def test_check_pr_passes_valid_feature_pr() -> None:
    problems = pr_convention.check_pr(
        "feature/infra-ci-workflows",
        "develop",
        _OK_TITLE,
        ["ci(infra): ci-test 추가", "docs(docs): 표 갱신"],
    )
    assert problems == []


def test_check_pr_reports_each_rule() -> None:
    problems = pr_convention.check_pr(
        "my-branch", "main", "작업함", ["feat(cli): 정상", "WIP"]
    )
    assert [p[:3] for p in problems] == ["R05", "R08", "R06", "R06"]
    assert "`WIP`" in problems[-1]


def test_check_pr_skips_commit_check_for_release() -> None:
    # release PR은 규칙 이전 커밋(init_commit 등)을 담고 있어도 실패하면 안 된다
    problems = pr_convention.check_pr(
        "release/v0.1", "main", "chore(infra): v0.1 릴리스", ["init_commit"]
    )
    assert problems == []


def test_escape_blocks_newline_injection() -> None:
    assert pr_convention._escape("a\n::warning::b%") == "a%0A::warning::b%25"


def test_main_exit_codes(monkeypatch, capsys) -> None:
    monkeypatch.setenv("HEAD_REF", "feature/infra-ci-workflows")
    monkeypatch.setenv("BASE_REF", "develop")
    monkeypatch.setenv("PR_TITLE", _OK_TITLE)
    monkeypatch.setattr("sys.stdin", io.StringIO("ci(infra): a\n\n"))
    assert pr_convention.main() == 0

    monkeypatch.setenv("PR_TITLE", "bad")
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert pr_convention.main() == 1
    assert "::error::R06" in capsys.readouterr().out

    monkeypatch.delenv("BASE_REF")
    assert pr_convention.main() == 2
