import io

from rich.console import Console

from gitcoach import ui
from gitcoach.models import Choice, Violation


def _violation(rule_id="R01", severity="high", allow_run=True) -> Violation:
    return Violation(
        rule_id=rule_id,
        title="t",
        severity=severity,
        facts={},
        guide_id="g1",
        allow_run=allow_run,
        warning="경고문",
        consequence="결과문",
    )


def _capture(monkeypatch) -> io.StringIO:
    buf = io.StringIO()
    monkeypatch.setattr(ui, "console", Console(file=buf, width=100))
    return buf


def test_prompt_choice_single_violation_shows_both_options(monkeypatch) -> None:
    buf = _capture(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda prompt="": "2")
    assert ui.prompt_choice([_violation()]) is Choice.GUIDE
    out = buf.getvalue()
    assert "[1]" in out and "[2]" in out


def test_prompt_choice_default_enter_is_guide(monkeypatch) -> None:
    _capture(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    assert ui.prompt_choice([_violation()]) is Choice.GUIDE


def test_prompt_choice_run_selected(monkeypatch) -> None:
    _capture(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda prompt="": "1")
    assert ui.prompt_choice([_violation()]) is Choice.RUN


def test_prompt_choice_multiple_violations_shows_count_header(monkeypatch) -> None:
    buf = _capture(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda prompt="": "2")
    ui.prompt_choice([_violation("R01", "high"), _violation("R02", "medium")])
    assert "위반 2개" in buf.getvalue()


def test_prompt_choice_blocked_hides_run_option(monkeypatch) -> None:
    buf = _capture(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda prompt="": "q")
    assert ui.prompt_choice([_violation(allow_run=False)]) is Choice.CANCEL
    assert "[1]" not in buf.getvalue()


def test_print_cancelled(monkeypatch) -> None:
    buf = _capture(monkeypatch)
    ui.print_cancelled()
    assert "취소" in buf.getvalue()
