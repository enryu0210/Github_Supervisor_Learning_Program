from gitcoach.models import Command, Context, Violation

_WARNING = "main 브랜치에 직접 push하려고 해요."
_CONSEQUENCE = "리뷰·CI 없이 main에 들어가 배포까지 이어질 수 있어요."


def check_protected_push(cmd: Command, ctx: Context) -> Violation | None:
    if cmd.subcommand != "push":
        return None
    if ctx.push_branch not in ctx.protected_branches:
        return None

    return Violation(
        rule_id="R01",
        title="보호된 브랜치(main) 직접 push",
        severity="high",
        facts={"push_branch": ctx.push_branch, "remote": cmd.remote},
        guide_id="r01_protected_push",
        allow_run=True,
        warning=_WARNING,
        consequence=_CONSEQUENCE,
    )
