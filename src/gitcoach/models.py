from dataclasses import dataclass


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
