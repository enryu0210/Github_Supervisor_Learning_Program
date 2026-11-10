from gitcoach.models import Command, Context, Violation

_WARNING = "main 브랜치에서 직접 커밋하려고 해요."
_CONSEQUENCE = "로컬이라 당장 피해는 없지만, 다음 push에서 R01에 걸리고 원격과 어긋나 동기화가 꼬일 수 있어요."


def check_direct_commit(cmd: Command, ctx: Context) -> Violation | None:
    if cmd.subcommand != "commit":
        return None
    if ctx.current_branch not in ctx.protected_branches:
        return None

    return Violation(
        rule_id="R04",
        title="보호된 브랜치(main) 직접 커밋",
        severity="medium",
        facts={"branch": ctx.current_branch},
        guide_id="r04_direct_commit",
        allow_run=True,
        warning=_WARNING,
        consequence=_CONSEQUENCE,
    )
