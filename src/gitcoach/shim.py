import subprocess
import sys

from gitcoach import context, parser, rules, ui
from gitcoach.models import Choice


def is_interactive() -> bool:
    return sys.stdin.isatty()


def run(argv: list[str]) -> int:
    if not is_interactive():
        return _exec_git(argv)

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
    return 1  # TODO(cli-guide-engine): 가이드 시작


def _exec_git(argv: list[str]) -> int:
    return subprocess.run(["git", *argv], check=False).returncode
