from gitcoach.models import Command, Context
from gitcoach.rules.r06_commit_message import check_commit_message


def _ctx() -> Context:
    return Context(
        current_branch="feature/cli-x",
        push_branch="feature/cli-x",
        staged_files=[],
        protected_branches=["main"],
        interactive=True,
    )


def test_badly_formatted_message_is_violation() -> None:
    cmd = Command(
        subcommand="commit", flags=["-m"], positionals=[], message="fix login"
    )
    v = check_commit_message(cmd, _ctx())
    assert v is not None
    assert v.rule_id == "R06"
    assert v.severity == "low"
    assert v.allow_run is True
    assert v.facts == {"message": "fix login"}


def test_well_formatted_message_is_not_violation() -> None:
    cmd = Command(
        subcommand="commit", flags=["-m"], positionals=[], message="feat(cli): x"
    )
    assert check_commit_message(cmd, _ctx()) is None


def test_commit_without_message_flag_is_not_violation() -> None:
    cmd = Command(subcommand="commit", flags=[], positionals=[], message=None)
    assert check_commit_message(cmd, _ctx()) is None


def test_non_commit_command_is_not_violation() -> None:
    cmd = Command(subcommand="push", flags=[], positionals=["origin"])
    assert check_commit_message(cmd, _ctx()) is None


def test_commit_dash_am_with_bad_message_is_violation() -> None:
    cmd = Command(subcommand="commit", flags=["-a"], positionals=[], message="fix")
    v = check_commit_message(cmd, _ctx())
    assert v is not None
    assert v.rule_id == "R06"
