from collections.abc import Callable

from gitcoach.models import Command, Context, Violation
from gitcoach.rules.r01_protected_push import check_protected_push
from gitcoach.rules.r02_force_push import check_force_push
from gitcoach.rules.r03_secret_commit import check_secret_commit
from gitcoach.rules.r04_direct_commit import check_direct_commit

_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

_RULES: list[Callable[[Command, Context], Violation | None]] = [
    check_protected_push,
    check_force_push,
    check_secret_commit,
    check_direct_commit,
]


def evaluate(cmd: Command, ctx: Context) -> list[Violation]:
    violations = [v for check in _RULES if (v := check(cmd, ctx)) is not None]
    return sorted(violations, key=lambda v: _SEVERITY_ORDER[v.severity])
