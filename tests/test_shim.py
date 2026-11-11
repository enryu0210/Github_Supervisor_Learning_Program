import subprocess

from gitcoach import events, explain, rules, shim, ui
from gitcoach.models import Choice, Explanation, Violation


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


def _violation(rule_id="R01", allow_run=True) -> Violation:
    return Violation(
        rule_id=rule_id,
        title="t",
        severity="high",
        facts={},
        guide_id="r01_protected_push",
        allow_run=allow_run,
        warning="w",
        consequence="c",
    )


def _use_tmp_db(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(events, "DB_PATH", tmp_path / "events.db")


def test_run_interactive_no_violations_execs_git(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(rules, "evaluate", lambda cmd, ctx: [])
    assert shim.run(["status"]) == 0


def test_run_interactive_run_choice_execs_git(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    _use_tmp_db(tmp_path, monkeypatch)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(rules, "evaluate", lambda cmd, ctx: [_violation()])
    monkeypatch.setattr(ui, "prompt_choice", lambda violations: Choice.RUN)
    assert shim.run(["status"]) == 0
    rows = events.query()
    assert len(rows) == 1
    assert rows[0].action == "allowed"
    assert rows[0].rule_id == "R01"


def test_run_interactive_cancel_choice_blocks(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    _use_tmp_db(tmp_path, monkeypatch)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(
        rules,
        "evaluate",
        lambda cmd, ctx: [_violation(), _violation(rule_id="R03", allow_run=False)],
    )
    monkeypatch.setattr(ui, "prompt_choice", lambda violations: Choice.CANCEL)
    assert shim.run(["status"]) == 1
    rows = events.query()
    assert len(rows) == 1
    assert rows[0].action == "blocked"
    assert rows[0].rule_id == "R03"


def test_run_disabled_rule_skips_prompt_and_execs_git(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    (tmp_path / ".gitcoach.toml").write_text('disabled_rules = ["R05"]')
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(rules, "evaluate", lambda cmd, ctx: [_violation(rule_id="R05")])

    def fail_if_called(violations):
        raise AssertionError("꺼진 규칙은 선택지를 띄우면 안 돼요")

    monkeypatch.setattr(ui, "prompt_choice", fail_if_called)
    assert shim.run(["status"]) == 0


def test_run_disabled_rule_does_not_affect_other_rules(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    _use_tmp_db(tmp_path, monkeypatch)
    (tmp_path / ".gitcoach.toml").write_text('disabled_rules = ["R05"]')
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(
        rules,
        "evaluate",
        lambda cmd, ctx: [_violation(rule_id="R05"), _violation(rule_id="R01")],
    )
    monkeypatch.setattr(ui, "prompt_choice", lambda violations: Choice.RUN)
    assert shim.run(["status"]) == 0
    rows = events.query()
    assert [r.rule_id for r in rows] == ["R01"]


def test_run_masks_credentials_in_recorded_command_summary(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    _use_tmp_db(tmp_path, monkeypatch)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(rules, "evaluate", lambda cmd, ctx: [_violation()])
    monkeypatch.setattr(ui, "prompt_choice", lambda violations: Choice.RUN)
    monkeypatch.setattr(shim, "_exec_git", lambda argv: 0)
    shim.run(["push", "https://user:ghp_secrettoken@github.com/x", "main"])
    rows = events.query()
    assert len(rows) == 1
    assert "ghp_secrettoken" not in rows[0].command_summary
    assert "user" not in rows[0].command_summary


def test_run_interactive_guide_choice_cancels_and_prints(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    _use_tmp_db(tmp_path, monkeypatch)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(rules, "evaluate", lambda cmd, ctx: [_violation()])
    monkeypatch.setattr(ui, "prompt_choice", lambda violations: Choice.GUIDE)
    monkeypatch.setattr(
        explain, "explain", lambda rule_id, title, facts: Explanation("설명", False)
    )
    printed = []
    monkeypatch.setattr(ui, "print_cancelled", lambda: printed.append(True))
    assert shim.run(["status"]) == 1
    assert printed == [True]
    rows = events.query()
    assert len(rows) == 1
    assert rows[0].action == "guided"
    assert rows[0].explanation == "설명"
