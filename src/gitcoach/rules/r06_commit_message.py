from gitcoach.commit_format import is_valid_commit_message
from gitcoach.models import Command, Context, Violation

_WARNING = "커밋 메시지가 규칙에 안 맞아요."
_CONSEQUENCE = "기록을 읽기 어려워지고, pr-convention 검사가 실패할 수 있어요."


def check_commit_message(cmd: Command, ctx: Context) -> Violation | None:
    if cmd.subcommand != "commit":
        return None
    if cmd.message is None:
        return None
    if is_valid_commit_message(cmd.message):
        return None

    return Violation(
        rule_id="R06",
        title="커밋 메시지 규칙 위반",
        severity="low",
        facts={"message": cmd.message},
        guide_id="r06_commit_message",
        allow_run=True,
        warning=_WARNING,
        consequence=_CONSEQUENCE,
    )
