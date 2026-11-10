import subprocess
import sys

from gitcoach import context, events, guide, parser, rules, ui
from gitcoach.models import Choice, GuideAction


def is_interactive() -> bool:
    return sys.stdin.isatty()


def run(argv: list[str]) -> int:
    if not is_interactive():
        return _exec_git(argv)

    outcome = guide.on_command(argv)
    if outcome.action in (GuideAction.EXEC_AND_ADVANCE, GuideAction.EXEC_AND_REMIND):
        code = _exec_git(argv)
        if outcome.message:
            ui.print_guide_message(outcome.message)
        return code
    if outcome.action is GuideAction.FALLTHROUGH and outcome.message:
        ui.print_guide_message(outcome.message)

    cmd = parser.parse(argv)
    ctx = context.collect(cmd)
    violations = rules.evaluate(cmd, ctx)
    if not violations:
        return _exec_git(argv)

    choice = ui.prompt_choice(violations)
    command_summary = " ".join(["git", *argv])

    if choice is Choice.RUN:
        for v in violations:
            events.record(
                events.make_event(
                    rule_id=v.rule_id,
                    severity=v.severity,
                    branch=ctx.current_branch,
                    action="allowed",
                    command_summary=command_summary,
                )
            )
        return _exec_git(argv)

    if choice is Choice.CANCEL:
        blocked_v = next(v for v in violations if not v.allow_run)
        events.record(
            events.make_event(
                rule_id=blocked_v.rule_id,
                severity=blocked_v.severity,
                branch=ctx.current_branch,
                action="blocked",
                command_summary=command_summary,
            )
        )
        return 1

    ui.print_cancelled()
    guide_events = []
    for v in violations:
        ev = events.make_event(
            rule_id=v.rule_id,
            severity=v.severity,
            branch=ctx.current_branch,
            action="guided",
            command_summary=command_summary,
        )
        events.record(ev)
        guide_events.append(ev)
    guide_state = guide.start(violations, ctx, guide_events, command_summary)
    ui.print_guide_message(guide.start_message(guide_state, command_summary))
    return 1


def _exec_git(argv: list[str]) -> int:
    return subprocess.run(["git", *argv], check=False).returncode
