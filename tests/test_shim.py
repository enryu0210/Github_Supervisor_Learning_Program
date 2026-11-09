import subprocess

from gitcoach import shim


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
