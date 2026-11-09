from rich.console import Console

from gitcoach.models import Choice, Violation

console = Console(stderr=True)


def prompt_choice(violations: list[Violation]) -> Choice:
    blocked = any(not v.allow_run for v in violations)
    _print_violations(violations, blocked)
    return _read_choice(blocked)


def print_cancelled() -> None:
    console.print("원래 명령을 취소했어요.")


def _print_violations(violations: list[Violation], blocked: bool) -> None:
    if len(violations) == 1:
        v = violations[0]
        console.print(f"⚠  [{v.rule_id}] {v.warning}")
        console.print(f"   그냥 실행하면: {v.consequence}")
    else:
        console.print(f"⚠  위반 {len(violations)}개 (심각한 순서)")
        for i, v in enumerate(violations, 1):
            console.print(f"   {i}. [{v.rule_id}] {v.warning}")
            console.print(f"      그냥 실행하면: {v.consequence}")

    if not blocked:
        console.print("   [1] 그냥 실행할래요")
    console.print("   [2] 어떻게 해야 하나요?   (기본값)")
    if blocked:
        console.print("   [q] 취소")


def _read_choice(blocked: bool) -> Choice:
    while True:
        raw = input("> ").strip().lower()
        if raw in ("", "2"):
            return Choice.GUIDE
        if raw == "1" and not blocked:
            return Choice.RUN
        if raw == "q" and blocked:
            return Choice.CANCEL
