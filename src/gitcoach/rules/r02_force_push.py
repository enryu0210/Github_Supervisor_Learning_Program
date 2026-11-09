from gitcoach.models import Command, Context, Violation

_WARNING = "원격 기록을 덮어쓰는 force push를 하려고 해요."
_CONSEQUENCE = "다른 사람이 올린 커밋이 사라질 수 있어요."


def _has_lease(flags: list[str]) -> bool:
    return any(
        f == "--force-with-lease" or f.startswith("--force-with-lease=") for f in flags
    )


def check_force_push(cmd: Command, ctx: Context) -> Violation | None:
    if cmd.subcommand != "push":
        return None

    has_force = "-f" in cmd.flags or "--force" in cmd.flags
    has_plus_ref = bool(cmd.refspec) and cmd.refspec.startswith("+")
    has_lease = _has_lease(cmd.flags)

    if not (has_force or has_plus_ref or has_lease):
        return None

    severity = "high" if (has_force or has_plus_ref) else "medium"

    return Violation(
        rule_id="R02",
        title="force push",
        severity=severity,
        facts={"push_branch": ctx.push_branch, "remote": cmd.remote},
        guide_id="r02_force_push",
        allow_run=True,
        warning=_WARNING,
        consequence=_CONSEQUENCE,
    )
