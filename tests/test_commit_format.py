import pytest

from gitcoach.commit_format import is_valid_commit_message

_VALID = [
    "feat(cli): add R04 rule",
    "fix(watcher): handle timeout",
    "docs(docs): update guide",
    "test(web): cover dashboard",
    "chore(db): bump schema",
    "ci(infra): add workflow",
    "refactor(cli): simplify matcher",
]

_INVALID = [
    "fix login",
    "feat(login): add R04 rule",
    "feat(cli):add R04 rule",
    "feat(cli) add R04 rule",
    "feat(cli): ",
    "wip(cli): quick save",
]


@pytest.mark.parametrize("message", _VALID)
def test_valid_messages(message: str) -> None:
    assert is_valid_commit_message(message) is True


@pytest.mark.parametrize("message", _INVALID)
def test_invalid_messages(message: str) -> None:
    assert is_valid_commit_message(message) is False
