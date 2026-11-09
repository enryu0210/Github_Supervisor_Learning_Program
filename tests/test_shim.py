import subprocess

from gitcoach import rules, shim, ui
from gitcoach.models import Choice, Violation


def test_is_interactive_true(monkeypatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    assert shim.is_interactive() is True


def test_is_interactive_false(monkeypatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert shim.is_interactive() is False


def test_run_calls_real_git(monkeypatch) -> None:
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    code = shim.run(["status"])
    assert code == 0
    assert calls == [["git", "status"]]


def test_run_propagates_exit_code(monkeypatch) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 1),
    )
    assert shim.run(["push"]) == 1


def test_run_same_behavior_when_not_interactive(monkeypatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert shim.run(["log"]) == 0
    assert calls == [["git", "log"]]


def test_run_integration_tmp_repo(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], check=True)
    assert shim.run(["status"]) == 0


def _init_repo() -> None:
    subprocess.run(["git", "init", "-b", "main"], check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], check=True)
    subprocess.run(["git", "config", "user.name", "t"], check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], check=True)


def _violation(allow_run=True) -> Violation:
    return Violation(
        rule_id="R01",
        title="t",
        severity="high",
        facts={},
        guide_id="g1",
        allow_run=allow_run,
        warning="w",
        consequence="c",
    )


def test_run_interactive_no_violations_execs_git(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(rules, "evaluate", lambda cmd, ctx: [])
    assert shim.run(["status"]) == 0


def test_run_interactive_run_choice_execs_git(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(rules, "evaluate", lambda cmd, ctx: [_violation()])
    monkeypatch.setattr(ui, "prompt_choice", lambda violations: Choice.RUN)
    assert shim.run(["status"]) == 0


def test_run_interactive_cancel_choice_blocks(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(rules, "evaluate", lambda cmd, ctx: [_violation(allow_run=False)])
    monkeypatch.setattr(ui, "prompt_choice", lambda violations: Choice.CANCEL)
    assert shim.run(["status"]) == 1


def test_run_interactive_guide_choice_cancels_and_prints(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(rules, "evaluate", lambda cmd, ctx: [_violation()])
    monkeypatch.setattr(ui, "prompt_choice", lambda violations: Choice.GUIDE)
    printed = []
    monkeypatch.setattr(ui, "print_cancelled", lambda: printed.append(True))
    assert shim.run(["status"]) == 1
    assert printed == [True]
