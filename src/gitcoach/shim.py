import subprocess
import sys

from gitcoach import context, guide, parser, rules, ui
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
    if choice is Choice.RUN:
        return _exec_git(argv)  # TODO(cli-event-log): allowed 기록
    if choice is Choice.CANCEL:
        return 1  # TODO(cli-event-log): blocked 기록

    ui.print_cancelled()
    guide_state = guide.start(violations, ctx)
    ui.print_guide_message(guide.start_message(guide_state, " ".join(["git", *argv])))
    return 1  # TODO(cli-event-log): 위반마다 guided 기록


def _exec_git(argv: list[str]) -> int:
    return subprocess.run(["git", *argv], check=False).returncode
