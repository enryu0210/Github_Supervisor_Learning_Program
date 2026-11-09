from gitcoach.models import Command, Context
from gitcoach.rules.r03_secret_commit import check_secret_commit


def _ctx(staged_files: list[str]) -> Context:
    return Context(
        current_branch="feature/web-login",
        push_branch="feature/web-login",
        staged_files=staged_files,
        protected_branches=["main"],
        interactive=True,
    )


def test_staged_dotenv_is_violation() -> None:
    cmd = Command(
        subcommand="commit",
        flags=["-m"],
        positionals=[],
        message="feat(web): local config",
    )
    v = check_secret_commit(cmd, _ctx([".env"]))
    assert v is not None
    assert v.rule_id == "R03"
    assert v.allow_run is False
    assert v.facts == {"files": [".env"]}


def test_staged_dotenv_variant_is_violation() -> None:
    cmd = Command(subcommand="add", flags=[], positionals=[".env.local"])
    v = check_secret_commit(cmd, _ctx([".env.local"]))
    assert v is not None


def test_staged_dotenv_example_is_not_violation() -> None:
    cmd = Command(subcommand="add", flags=[], positionals=[".env.example"])
    assert check_secret_commit(cmd, _ctx([".env.example"])) is None


def test_staged_private_key_is_violation() -> None:
    cmd = Command(
        subcommand="commit", flags=["-m"], positionals=[], message="chore: deploy key"
    )
    v = check_secret_commit(cmd, _ctx(["deploy/id_rsa"]))
    assert v is not None
    assert v.facts == {"files": ["deploy/id_rsa"]}


def test_staged_pem_file_is_violation() -> None:
    cmd = Command(
        subcommand="push",
        flags=[],
        positionals=["origin", "feature/web-login"],
        remote="origin",
    )
    v = check_secret_commit(cmd, _ctx(["certs/server.pem"]))
    assert v is not None


def test_no_staged_secret_is_not_violation() -> None:
    cmd = Command(
        subcommand="commit",
        flags=["-m"],
        positionals=[],
        message="feat(web): login form",
    )
    assert check_secret_commit(cmd, _ctx(["src/login.py"])) is None


def test_non_checked_subcommand_is_not_violation() -> None:
    cmd = Command(subcommand="status", flags=[], positionals=[])
    assert check_secret_commit(cmd, _ctx([".env"])) is None
