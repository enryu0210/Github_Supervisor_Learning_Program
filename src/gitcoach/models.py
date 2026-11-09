from dataclasses import dataclass
from enum import Enum


@dataclass
class Command:
    subcommand: str
    flags: list[str]
    positionals: list[str]
    remote: str | None = None
    refspec: str | None = None
    message: str | None = None


@dataclass
class Context:
    current_branch: str
    push_branch: str | None
    staged_files: list[str]
    protected_branches: list[str]
    interactive: bool


@dataclass
class Violation:
    rule_id: str
    title: str
    severity: str
    facts: dict
    guide_id: str
    allow_run: bool
    warning: str
    consequence: str


class Choice(Enum):
    RUN = "1"
    GUIDE = "2"
    CANCEL = "q"
