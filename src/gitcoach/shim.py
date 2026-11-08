import subprocess
import sys


def is_interactive() -> bool:
    return sys.stdin.isatty()


def run(argv: list[str]) -> int:
    if not is_interactive():
        return _exec_git(argv)
    # TODO(cli-git-parser 이후): parse → context → rules → choice
    return _exec_git(argv)


def _exec_git(argv: list[str]) -> int:
    return subprocess.run(["git", *argv], check=False).returncode
