from gitcoach.models import Command, Context
from gitcoach.rules.r02_force_push import check_force_push


def _ctx() -> Context:
    return Context(
        current_branch="feature/cli-x",
        push_branch="feature/cli-x",
        staged_files=[],
        protected_branches=["main"],
        interactive=True,
    )


def test_dash_f_is_high_severity_violation() -> None:
    cmd = Command(
        subcommand="push",
        flags=["-f"],
        positionals=["origin", "feature/cli-x"],
        remote="origin",
    )
    v = check_force_push(cmd, _ctx())
    assert v is not None
    assert v.rule_id == "R02"
    assert v.severity == "high"
    assert v.allow_run is True


def test_dash_dash_force_is_high_severity_violation() -> None:
    cmd = Command(
        subcommand="push",
        flags=["--force"],
        positionals=["origin", "feature/cli-x"],
        remote="origin",
    )
    v = check_force_push(cmd, _ctx())
    assert v is not None
    assert v.severity == "high"


def test_plus_refspec_is_high_severity_violation() -> None:
    cmd = Command(
        subcommand="push",
        flags=[],
        positionals=["origin", "+feature/cli-x"],
        remote="origin",
        refspec="+feature/cli-x",
    )
    v = check_force_push(cmd, _ctx())
    assert v is not None
    assert v.severity == "high"


def test_force_with_lease_only_is_medium_severity() -> None:
    cmd = Command(
        subcommand="push",
        flags=["--force-with-lease"],
        positionals=["origin", "feature/cli-x"],
        remote="origin",
    )
    v = check_force_push(cmd, _ctx())
    assert v is not None
    assert v.severity == "medium"


def test_plain_push_is_not_violation() -> None:
    cmd = Command(
        subcommand="push",
        flags=[],
        positionals=["origin", "feature/cli-x"],
        remote="origin",
    )
    assert check_force_push(cmd, _ctx()) is None


def test_non_push_command_is_not_violation() -> None:
    cmd = Command(subcommand="commit", flags=["-m"], positionals=[], message="feat: x")
    assert check_force_push(cmd, _ctx()) is None
