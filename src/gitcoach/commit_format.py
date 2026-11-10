import re

_AREA = "cli|watcher|web|db|infra|docs"
_TYPE = "feat|fix|docs|test|chore|ci|refactor"
COMMIT_MESSAGE_RE = re.compile(rf"^({_TYPE})\(({_AREA})\): .+$")


def is_valid_commit_message(message: str) -> bool:
    return bool(COMMIT_MESSAGE_RE.match(message))
