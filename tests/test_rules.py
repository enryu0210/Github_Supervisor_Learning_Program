from gitcoach import rules
from gitcoach.models import Command, Context, Violation


def _ctx() -> Context:
    return Context(
        current_branch="main",
        push_branch="main",
        staged_files=[],
        protected_branches=["main"],
        interactive=True,
    )


def test_evaluate_empty_when_no_rules_match(monkeypatch) -> None:
    monkeypatch.setattr(rules, "_RULES", [])
    cmd = Command(subcommand="push", flags=[], positionals=[])
    assert rules.evaluate(cmd, _ctx()) == []


def test_evaluate_sorts_by_severity(monkeypatch) -> None:
    low = Violation(
        rule_id="RX",
        title="t",
        severity="low",
        facts={},
        guide_id="gx",
        allow_run=True,
        warning="w",
        consequence="c",
    )
    high = Violation(
        rule_id="RY",
        title="t",
        severity="high",
        facts={},
        guide_id="gy",
        allow_run=True,
        warning="w",
        consequence="c",
    )
    monkeypatch.setattr(rules, "_RULES", [lambda cmd, ctx: low, lambda cmd, ctx: high])

    result = rules.evaluate(
        Command(subcommand="push", flags=[], positionals=[]), _ctx()
    )
    assert [v.rule_id for v in result] == ["RY", "RX"]
