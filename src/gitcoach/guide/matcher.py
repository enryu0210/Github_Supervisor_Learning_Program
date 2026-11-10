from gitcoach.models import Command, Context, GuideStep, ViolationSnapshot

_CHECK_SUBCOMMANDS = {"status", "log", "diff", "branch"}


def is_check_command(cmd: Command) -> bool:
    return cmd.subcommand in _CHECK_SUBCOMMANDS


def step_matches(
    step: GuideStep, cmd: Command, ctx: Context, snap: ViolationSnapshot
) -> bool:
    if step.expect is None:
        return False
    return step.expect(cmd, ctx, snap)
