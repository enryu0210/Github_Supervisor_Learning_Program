from gitcoach.models import Command, Context
from gitcoach.rules.r04_direct_commit import check_direct_commit


def _ctx(branch: str, protected: list[str] | None = None) -> Context:
    return Context(
        current_branch=branch,
        push_branch=branch,
        staged_files=[],
        protected_branches=protected if protected is not None else ["main"],
        interactive=True,
    )


def test_commit_on_main_is_violation() -> None:
    cmd = Command(
        subcommand="commit", flags=["-m"], positionals=[], message="feat(cli): x"
    )
    v = check_direct_commit(cmd, _ctx("main"))
    assert v is not None
    assert v.rule_id == "R04"
    assert v.severity == "medium"
    assert v.allow_run is True
    assert v.facts == {"branch": "main"}


def test_commit_on_feature_branch_is_not_violation() -> None:
    cmd = Command(
        subcommand="commit", flags=["-m"], positionals=[], message="feat(cli): x"
    )
    assert check_direct_commit(cmd, _ctx("feature/cli-x")) is None


def test_commit_on_develop_is_not_violation() -> None:
    cmd = Command(
        subcommand="commit", flags=["-m"], positionals=[], message="feat(cli): x"
    )
    assert check_direct_commit(cmd, _ctx("develop")) is None


def test_non_commit_command_is_not_violation() -> None:
    cmd = Command(subcommand="push", flags=[], positionals=["origin", "main"])
    assert check_direct_commit(cmd, _ctx("main")) is None
