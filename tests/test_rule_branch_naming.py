import pytest

from gitcoach.models import Command, Context
from gitcoach.rules.r05_branch_naming import (
    check_branch_naming,
    is_valid_branch_name,
    suggest_name,
)


def _ctx() -> Context:
    return Context(
        current_branch="main",
        push_branch="main",
        staged_files=[],
        protected_branches=["main"],
        interactive=True,
    )


_VALID_NAMES = [
    "feature/cli-login-fix",
    "fix/db-null-check",
    "docs/update-readme",
    "release/v0.1",
]

_INVALID_NAMES = [
    "MyBranch",
    "feature/MyBranch",
    "feature/cli_login",
    "hotfix/urgent",
    "docs/update_readme",
    "release/experimental",
]


@pytest.mark.parametrize("name", _VALID_NAMES)
def test_valid_names_pass(name: str) -> None:
    assert is_valid_branch_name(name) is True


@pytest.mark.parametrize("name", _INVALID_NAMES)
def test_invalid_names_fail(name: str) -> None:
    assert is_valid_branch_name(name) is False


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("MyBranch", "feature/cli-mybranch"),
        ("hotfix/urgent", "feature/cli-urgent"),
        ("feature/db-add_user", "feature/db-add-user"),
        ("###", "feature/cli-change"),
        ("docs/update_readme", "docs/update-readme"),
        ("release/experimental", "release/v0.1"),
        ("release/v2.5", "release/v2.5"),
    ],
)
def test_suggest_name(name: str, expected: str) -> None:
    assert suggest_name(name) == expected


def test_checkout_dash_b_with_invalid_name_is_violation() -> None:
    cmd = Command(subcommand="checkout", flags=["-b"], positionals=["MyBranch"])
    v = check_branch_naming(cmd, _ctx())
    assert v is not None
    assert v.rule_id == "R05"
    assert v.severity == "low"
    assert v.facts == {"branch_name": "MyBranch", "suggestion": "feature/cli-mybranch"}
    assert "feature/cli-mybranch" in v.warning


def test_switch_dash_c_with_valid_name_is_not_violation() -> None:
    cmd = Command(subcommand="switch", flags=["-c"], positionals=["feature/cli-x"])
    assert check_branch_naming(cmd, _ctx()) is None


def test_checkout_without_create_flag_is_not_violation() -> None:
    cmd = Command(subcommand="checkout", flags=[], positionals=["MyBranch"])
    assert check_branch_naming(cmd, _ctx()) is None


def test_branch_delete_flag_is_not_violation() -> None:
    cmd = Command(subcommand="branch", flags=["-d"], positionals=["MyBranch"])
    assert check_branch_naming(cmd, _ctx()) is None


def test_branch_list_with_no_positionals_is_not_violation() -> None:
    cmd = Command(subcommand="branch", flags=[], positionals=[])
    assert check_branch_naming(cmd, _ctx()) is None


def test_branch_create_with_invalid_name_is_violation() -> None:
    cmd = Command(subcommand="branch", flags=[], positionals=["MyBranch"])
    v = check_branch_naming(cmd, _ctx())
    assert v is not None
    assert v.rule_id == "R05"


def test_checkout_dash_b_with_start_point_checks_new_name_only() -> None:
    cmd = Command(
        subcommand="checkout",
        flags=["-b"],
        positionals=["feature/cli-x", "origin/develop"],
    )
    assert check_branch_naming(cmd, _ctx()) is None
