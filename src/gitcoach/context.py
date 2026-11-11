import subprocess
import sys

from gitcoach import config
from gitcoach.models import Command, Context


def collect(cmd: Command) -> Context:
    current_branch = _current_branch()
    repo_root = config.find_repo_root()
    return Context(
        current_branch=current_branch,
        push_branch=cmd.refspec or current_branch,
        staged_files=_staged_files(),
        protected_branches=config.protected_branches(repo_root),
        interactive=sys.stdin.isatty(),
        repo_root=repo_root,
    )


def _current_branch() -> str:
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def _staged_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=False,
    )
    return [line for line in result.stdout.splitlines() if line]
