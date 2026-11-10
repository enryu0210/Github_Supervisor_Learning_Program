import subprocess

from gitcoach import events, guide
from gitcoach.guide import matcher, state
from gitcoach.guide.scenarios import SCENARIOS
from gitcoach.models import Command, Context, GuideAction, Violation


def _use_tmp_db(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(events, "DB_PATH", tmp_path / "events.db")


def _init_repo() -> None:
    subprocess.run(["git", "init", "-b", "main"], check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], check=True)
    subprocess.run(["git", "config", "user.name", "t"], check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], check=True)


def _ctx(branch: str = "main") -> Context:
    return Context(
        current_branch=branch,
        push_branch=branch,
        staged_files=[],
        protected_branches=["main"],
        interactive=True,
    )


def _violation(
    rule_id: str = "R01",
    guide_id: str = "r01_protected_push",
    facts: dict | None = None,
) -> Violation:
    return Violation(
        rule_id=rule_id,
        title="t",
        severity="high",
        facts=facts or {},
        guide_id=guide_id,
        allow_run=True,
        warning="w",
        consequence="c",
    )


def test_is_check_command() -> None:
    assert matcher.is_check_command(
        Command(subcommand="status", flags=[], positionals=[])
    )
    assert not matcher.is_check_command(
        Command(subcommand="push", flags=[], positionals=[])
    )


def test_all_scenarios_have_well_formed_steps() -> None:
    for scenario in SCENARIOS.values():
        assert scenario.steps
        for step in scenario.steps:
            assert step.instruction
            assert step.hint
            assert step.answer


def test_r01_has_exactly_one_non_git_step() -> None:
    scenario = SCENARIOS["r01_protected_push"]
    non_git_steps = [s for s in scenario.steps if s.expect is None]
    assert len(non_git_steps) == 1


def test_state_load_returns_none_when_no_file(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    assert state.load() is None


def test_start_persists_and_state_load_roundtrips(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    guide.start([_violation()], _ctx())
    loaded = state.load()
    assert loaded.queue[0].rule_id == "R01"
    assert loaded.step_index == 0


def test_state_clear_removes_file(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    guide.start([_violation()], _ctx())
    state.clear()
    assert state.load() is None


def test_on_command_none_when_no_guide_active(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    outcome = guide.on_command(["status"])
    assert outcome.action is GuideAction.NONE


def test_on_command_outside_git_repo_does_not_crash(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    outcome = guide.on_command(["clone", "x"])
    assert outcome.action is GuideAction.NONE


def test_on_command_check_command_reminds(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    guide.start([_violation()], _ctx())
    outcome = guide.on_command(["status"])
    assert outcome.action is GuideAction.EXEC_AND_REMIND


def test_on_command_matching_step_advances(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    guide.start([_violation()], _ctx())
    outcome = guide.on_command(["switch", "-c", "feature/cli-login-fix"])
    assert outcome.action is GuideAction.EXEC_AND_ADVANCE
    assert state.load().step_index == 1


def test_on_command_non_matching_falls_through_without_changing_state(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    guide.start([_violation()], _ctx())
    outcome = guide.on_command(["commit", "-m", "x"])
    assert outcome.action is GuideAction.FALLTHROUGH
    assert state.load().step_index == 0


def test_hint_first_call_shows_hint_then_answer(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    guide.start([_violation()], _ctx())
    assert "힌트" in guide.hint()
    assert "정답" in guide.hint()


def test_done_advances_git_outside_step_and_completes_single_guide(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    _use_tmp_db(tmp_path, monkeypatch)
    guide.start([_violation()], _ctx())

    outcome1 = guide.on_command(["switch", "-c", "feature/cli-login-fix"])
    assert outcome1.action is GuideAction.EXEC_AND_ADVANCE
    subprocess.run(["git", "switch", "-c", "feature/cli-login-fix"], check=True)

    outcome2 = guide.on_command(["push", "-u", "origin", "feature/cli-login-fix"])
    assert outcome2.action is GuideAction.EXEC_AND_ADVANCE
    assert state.load().step_index == 2

    guide.done()
    assert state.load() is None


def test_done_records_guide_completed_pointing_at_original_guided_event(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    _use_tmp_db(tmp_path, monkeypatch)
    ev = events.make_event(
        rule_id="R01",
        severity="high",
        branch="main",
        action="guided",
        command_summary="git push origin main",
    )
    events.record(ev)
    guide.start([_violation()], _ctx(), [ev], "git push origin main")

    guide.on_command(["switch", "-c", "feature/cli-login-fix"])
    subprocess.run(["git", "switch", "-c", "feature/cli-login-fix"], check=True)
    guide.on_command(["push", "-u", "origin", "feature/cli-login-fix"])
    guide.done()

    rows = [e for e in events.query() if e.action == "guide_completed"]
    assert len(rows) == 1
    assert rows[0].related_event_id == ev.id
    assert rows[0].command_summary == "git push origin main"


def test_multi_violation_queue_moves_to_next_guide_on_completion(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    _use_tmp_db(tmp_path, monkeypatch)
    guide.start(
        [_violation(), _violation(rule_id="R02", guide_id="r02_force_push")], _ctx()
    )

    guide.on_command(["switch", "-c", "feature/cli-login-fix"])
    subprocess.run(["git", "switch", "-c", "feature/cli-login-fix"], check=True)
    guide.on_command(["push", "-u", "origin", "feature/cli-login-fix"])
    guide.done()

    loaded = state.load()
    assert loaded.queue[0].rule_id == "R02"
    assert loaded.step_index == 0


def test_skip_moves_to_next_guide_in_queue(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    _use_tmp_db(tmp_path, monkeypatch)
    guide.start(
        [_violation(), _violation(rule_id="R02", guide_id="r02_force_push")], _ctx()
    )
    guide.skip()
    assert state.load().queue[0].rule_id == "R02"
    assert events.query() == []


def test_skip_records_guide_stopped_pointing_at_original_guided_event(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    _use_tmp_db(tmp_path, monkeypatch)
    ev = events.make_event(
        rule_id="R01",
        severity="high",
        branch="main",
        action="guided",
        command_summary="git push origin main",
    )
    events.record(ev)
    guide.start([_violation()], _ctx(), [ev], "git push origin main")

    guide.skip()

    rows = [e for e in events.query() if e.action == "guide_stopped"]
    assert len(rows) == 1
    assert rows[0].related_event_id == ev.id
    assert rows[0].command_summary == "git push origin main"


def test_skip_last_guide_clears_state(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    _use_tmp_db(tmp_path, monkeypatch)
    guide.start([_violation()], _ctx())
    guide.skip()
    assert state.load() is None


def test_stop_clears_entire_queue(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    _use_tmp_db(tmp_path, monkeypatch)
    guide.start(
        [_violation(), _violation(rule_id="R02", guide_id="r02_force_push")], _ctx()
    )
    guide.stop()
    assert state.load() is None


def test_r03_step1_requires_the_flagged_file(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _init_repo()
    guide.start(
        [
            _violation(
                rule_id="R03",
                guide_id="r03_secret_commit",
                facts={"files": [".env"]},
            )
        ],
        _ctx(),
    )
    wrong_file = guide.on_command(["restore", "--staged", "other.txt"])
    assert wrong_file.action is GuideAction.FALLTHROUGH

    right_file = guide.on_command(["restore", "--staged", ".env"])
    assert right_file.action is GuideAction.EXEC_AND_ADVANCE
