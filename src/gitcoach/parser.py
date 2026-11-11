import re

from gitcoach.models import Command

_VALUE_FLAGS: dict[str, set[str]] = {
    "commit": {"-m", "--message"},
}

_SHORT_MESSAGE_FLAG_RE = re.compile(r"-[a-zA-Z]*m.*")


def parse(argv: list[str]) -> Command:
    if not argv:
        return Command(subcommand="", flags=[], positionals=[])

    subcommand, *rest = argv
    value_flags = _VALUE_FLAGS.get(subcommand, set())

    flags: list[str] = []
    positionals: list[str] = []
    message: str | None = None

    i = 0
    while i < len(rest):
        token = rest[i]
        if token in value_flags:
            message = rest[i + 1] if i + 1 < len(rest) else None
            i += 2
            continue
        if subcommand == "commit" and token.startswith("--message="):
            message = token.split("=", 1)[1]
            i += 1
            continue
        # `-am "msg"`, `-mmsg`처럼 짧은 플래그를 붙여 쓰는 경우: m 앞은 플래그, 뒤는 메시지
        if (
            subcommand == "commit"
            and _SHORT_MESSAGE_FLAG_RE.fullmatch(token)
            and token not in value_flags
        ):
            head, _, attached = token.partition("m")
            if head != "-":
                flags.append(head)
            if attached:
                message = attached
                i += 1
            else:
                message = rest[i + 1] if i + 1 < len(rest) else None
                i += 2
            continue
        if token.startswith("-"):
            flags.append(token)
        else:
            positionals.append(token)
        i += 1

    remote = positionals[0] if subcommand == "push" and positionals else None
    refspec = positionals[1] if subcommand == "push" and len(positionals) > 1 else None

    return Command(subcommand, flags, positionals, remote, refspec, message)
