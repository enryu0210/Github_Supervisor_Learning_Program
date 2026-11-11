import subprocess

from gitcoach import context
from gitcoach.models import Command


def _init_repo(tmp_path) -> None:
    subprocess.run(["git", "init", "-b", "main"], check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], check=True)
    subprocess.run(["git", "config", "user.name", "t"], check=True)


def test_collect_current_branch(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    (tmp_path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "f.txt"], check=True)
    subprocess.run(["git", "commit", "-m", "init"], check=True)

    ctx = context.collect(Command(subcommand="push", flags=[], positionals=[]))
    assert ctx.current_branch == "main"
    assert ctx.protected_branches == ["main"]


def test_collect_push_branch_from_refspec(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], check=True)

    cmd = Command(
        subcommand="push",
        flags=[],
        positionals=["origin", "develop"],
        remote="origin",
        refspec="develop",
    )
    ctx = context.collect(cmd)
    assert ctx.push_branch == "develop"


def test_collect_push_branch_defaults_to_current(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], check=True)

    ctx = context.collect(Command(subcommand="push", flags=[], positionals=[]))
    assert ctx.push_branch == "main"


def test_collect_staged_files(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    (tmp_path / "secret.env").write_text("KEY=1")
    subprocess.run(["git", "add", "secret.env"], check=True)

    ctx = context.collect(Command(subcommand="commit", flags=[], positionals=[]))
    assert ctx.staged_files == ["secret.env"]


def test_collect_interactive(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], check=True)

    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    ctx = context.collect(Command(subcommand="status", flags=[], positionals=[]))
    assert ctx.interactive is False


def test_collect_repo_root(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], check=True)

    ctx = context.collect(Command(subcommand="status", flags=[], positionals=[]))
    assert ctx.repo_root is not None
    assert (ctx.repo_root / ".git").exists()


def test_collect_protected_branches_from_gitcoach_toml(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    (tmp_path / ".gitcoach.toml").write_text('protected = ["main", "develop"]')
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], check=True)

    ctx = context.collect(Command(subcommand="status", flags=[], positionals=[]))
    assert ctx.protected_branches == ["main", "develop"]
