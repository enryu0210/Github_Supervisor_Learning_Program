from collections.abc import Callable
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


@dataclass
class Event:
    id: str
    schema_version: int
    occurred_at: str
    source: str
    repo: str
    member: str
    rule_id: str
    severity: str
    action: str
    command_summary: str
    branch: str
    pr_number: int | None = None
    explanation: str | None = None
    llm_used: bool = False
    related_event_id: str | None = None


@dataclass
class ViolationSnapshot:
    """가이드 시작 시점에 얼려 둔 위반 정보. 가이드 진행 중 context가 바뀌어도
    (예: R01 가이드 중 switch -c로 브랜치가 바뀜) 이 값은 그대로 유지한다."""

    rule_id: str
    severity: str
    branch: str
    guide_id: str
    facts: dict
    event_id: str | None = None
    command_summary: str = ""
    title: str = ""


@dataclass
class Explanation:
    text: str
    llm_used: bool


@dataclass
class GuideStep:
    instruction: str
    hint: str
    answer: str
    expect: Callable[[Command, Context, ViolationSnapshot], bool] | None = None


@dataclass
class Scenario:
    guide_id: str
    title: str
    summary: str
    steps: list[GuideStep]


@dataclass
class GuideState:
    queue: list[ViolationSnapshot]
    step_index: int = 0
    hint_count: int = 0


class GuideAction(Enum):
    NONE = "none"
    EXEC_AND_ADVANCE = "exec_and_advance"
    EXEC_AND_REMIND = "exec_and_remind"
    FALLTHROUGH = "fallthrough"


@dataclass
class GuideOutcome:
    action: GuideAction
    message: str | None = None
