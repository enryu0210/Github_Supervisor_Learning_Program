from gitcoach.models import Command, Context
from gitcoach.rules.r01_protected_push import check_protected_push


def _ctx(push_branch: str, protected: list[str] | None = None) -> Context:
    return Context(
        current_branch=push_branch,
        push_branch=push_branch,
        staged_files=[],
        protected_branches=protected if protected is not None else ["main"],
        interactive=True,
    )


def test_push_to_main_is_violation() -> None:
    cmd = Command(
        subcommand="push",
        flags=[],
        positionals=["origin", "main"],
        remote="origin",
        refspec="main",
    )
    v = check_protected_push(cmd, _ctx("main"))
    assert v is not None
    assert v.rule_id == "R01"
    assert v.severity == "high"
    assert v.allow_run is True
    assert v.facts == {"push_branch": "main", "remote": "origin"}


def test_push_to_develop_is_not_violation() -> None:
    cmd = Command(
        subcommand="push",
        flags=[],
        positionals=["origin", "develop"],
        remote="origin",
        refspec="develop",
    )
    assert check_protected_push(cmd, _ctx("develop")) is None


def test_push_to_feature_branch_is_not_violation() -> None:
    cmd = Command(
        subcommand="push",
        flags=[],
        positionals=["origin", "feature/cli-x"],
        remote="origin",
        refspec="feature/cli-x",
    )
    assert check_protected_push(cmd, _ctx("feature/cli-x")) is None


def test_non_push_command_is_not_violation() -> None:
    cmd = Command(subcommand="commit", flags=["-m"], positionals=[], message="feat: x")
    assert check_protected_push(cmd, _ctx("main")) is None
